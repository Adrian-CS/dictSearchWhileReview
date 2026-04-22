# -*- coding: utf-8 -*-
"""Integración con el Reviewer.

Dos flujos:
  1) RUN   — atajo rápido: inserta todas las acepciones automáticamente.
  2) PICK  — atajo con popup: abre un diálogo para elegir qué acepciones
             insertar (multi-select).

Por qué captura JS en vez de QShortcut:
  En Anki 2.1.50+ el reviewer usa QWebEngineView, que consume los eventos de
  teclado antes de que lleguen al event filter global. Un QShortcut ligado a
  `mw` NO se dispara mientras el webview tiene el foco (que es casi siempre
  durante la revisión, y SIEMPRE tras seleccionar texto con el ratón).
  Por eso instalamos un keydown listener en el propio WebView vía JS y nos
  comunicamos con Python mediante `pycmd(...)` + `webview_did_receive_js_message`.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from aqt import mw, gui_hooks
from aqt.utils import tooltip
from aqt.operations import QueryOp

from . import lookup
from . import picker_dialog


PYCMD_RUN = "jisho_lookup__run:"
PYCMD_PICK = "jisho_lookup__pick:"


# ---------------------------------------------------------------------------
# Config helpers


def _current_config() -> dict:
    return mw.addonManager.getConfig(__name__.split(".")[0]) or {}


def _parse_shortcut(shortcut: str) -> dict:
    """Convierte 'Ctrl+Shift+S' a {ctrl,shift,alt,meta,key}."""
    parts = [p.strip().lower() for p in (shortcut or "").split("+") if p.strip()]
    out = {"ctrl": False, "shift": False, "alt": False, "meta": False, "key": ""}
    for p in parts:
        if p in ("ctrl", "control"):
            out["ctrl"] = True
        elif p == "shift":
            out["shift"] = True
        elif p == "alt":
            out["alt"] = True
        elif p in ("meta", "cmd", "command", "win"):
            out["meta"] = True
        else:
            out["key"] = p
    return out


# ---------------------------------------------------------------------------
# JavaScript que escucha keydown dentro del WebView
# Soporta múltiples atajos con un `kind` asociado (run | pick).


_JS_TEMPLATE = r"""
(function() {
  window.__jishoLookupShortcuts = %(shortcuts_json)s;
  window.__jishoLookupPycmds    = %(pycmds_json)s;
  if (window.__jishoLookupInstalled) { return; }
  window.__jishoLookupInstalled = true;

  function matches(e, s) {
    if (!s || !s.key) return false;
    if (e.ctrlKey  !== s.ctrl)  return false;
    if (e.shiftKey !== s.shift) return false;
    if (e.altKey   !== s.alt)   return false;
    if (e.metaKey  !== s.meta)  return false;
    var k = (e.key || "").toLowerCase();
    return k === s.key;
  }

  document.addEventListener("keydown", function(e) {
    var all = window.__jishoLookupShortcuts || [];
    for (var i = 0; i < all.length; i++) {
      if (!matches(e, all[i])) continue;
      var sel = "";
      try { sel = (window.getSelection() || "").toString(); } catch (err) {}
      sel = (sel || "").trim();
      e.preventDefault();
      e.stopPropagation();
      var prefix = window.__jishoLookupPycmds[all[i].kind] || "";
      pycmd(prefix + sel);
      return;
    }
  }, true);
})();
"""


def _inject_listener(*_args, **_kwargs) -> None:
    """Inyecta / actualiza el listener JS en el webview del reviewer."""
    if mw.state != "review":
        return
    reviewer = mw.reviewer
    if reviewer is None or reviewer.web is None:
        return
    cfg = _current_config()

    run_sc = _parse_shortcut(cfg.get("shortcut") or "Ctrl+S")
    run_sc["kind"] = "run"
    pick_sc = _parse_shortcut(cfg.get("picker_shortcut") or "Ctrl+Shift+S")
    pick_sc["kind"] = "pick"

    shortcuts: List[dict] = []
    if run_sc["key"]:
        shortcuts.append(run_sc)
    if pick_sc["key"] and (pick_sc != run_sc):
        shortcuts.append(pick_sc)

    js = _JS_TEMPLATE % {
        "shortcuts_json": json.dumps(shortcuts),
        "pycmds_json": json.dumps({"run": PYCMD_RUN, "pick": PYCMD_PICK}),
    }
    try:
        reviewer.web.eval(js)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Bridge pycmd -> Python


def _on_js_message(handled: Tuple[bool, object], message: str, context):
    if not isinstance(message, str):
        return handled

    if message.startswith(PYCMD_RUN):
        selected = message[len(PYCMD_RUN):].strip()
        if not selected:
            tooltip("Jisho Lookup: selecciona primero una palabra con el ratón.", period=2500)
            return (True, None)
        _run_lookup_async(selected)
        return (True, None)

    if message.startswith(PYCMD_PICK):
        selected = message[len(PYCMD_PICK):].strip()
        if not selected:
            tooltip("Jisho Lookup: selecciona primero una palabra con el ratón.", period=2500)
            return (True, None)
        _run_picker_async(selected)
        return (True, None)

    return handled


# ---------------------------------------------------------------------------
# Pipeline RUN — inserción automática


def _run_lookup_async(selected: str) -> None:
    config = _current_config()

    def worker(_col) -> Tuple[str, str, str]:
        html, source = lookup.do_lookup(selected, config)
        return (selected, html, source)

    def on_done(result: Tuple[str, str, str]) -> None:
        query, html, source = result
        if not html:
            if config.get("show_tooltip_on_error", True):
                tooltip(f"Jisho Lookup: nada encontrado para <b>{query}</b>.", period=3000)
            return
        _write_to_current_card(query, html, source, config)

    op = QueryOp(parent=mw, op=worker, success=on_done)
    op.with_progress(label="Buscando definición…").run_in_background()


# ---------------------------------------------------------------------------
# Pipeline PICK — diálogo popup de selección


def _run_picker_async(selected: str) -> None:
    config = _current_config()

    def worker(_col) -> Tuple[str, List[dict], str]:
        choices, header = lookup.collect_choices(selected, config)
        return (selected, choices, header)

    def on_done(result: Tuple[str, List[dict], str]) -> None:
        query, choices, header = result
        if not choices:
            if config.get("show_tooltip_on_error", True):
                tooltip(f"Jisho Lookup: nada encontrado para <b>{query}</b>.", period=3000)
            return
        multi = bool(config.get("picker_multi_select", True))
        picked = picker_dialog.show_picker(
            choices,
            header=header or query,
            multi_select=multi,
            parent=mw,
        )
        if not picked:
            return
        html = lookup.format_picked_choices(picked, config)
        if not html:
            return
        # Fuente: si hay mezcla, mostrar 'mixto'; si no, usar la de la primera opción.
        sources = {c.get("source", "") for c in picked}
        if len(sources) == 1:
            src = next(iter(sources))
        else:
            src = "varios"
        _write_to_current_card(query, html, src, config)

    op = QueryOp(parent=mw, op=worker, success=on_done)
    op.with_progress(label="Buscando acepciones…").run_in_background()


# ---------------------------------------------------------------------------
# Escritura al campo


def _write_to_current_card(query: str, html: str, source: str, config: dict) -> None:
    reviewer = mw.reviewer
    if reviewer is None or reviewer.card is None:
        return
    card = reviewer.card
    note = card.note()

    field = lookup.pick_target_field(note, config)
    if field is None:
        model = note.note_type() or {}
        model_name = model.get("name", "(desconocido)") if isinstance(model, dict) else "(desconocido)"
        available = ", ".join(note.keys())
        tooltip(
            f"Jisho Lookup: sin campo configurado para <b>{model_name}</b>.<br>"
            f"Campos disponibles: {available}.<br>"
            "Abre Herramientas → Jisho Lookup → Configuración.",
            period=5500,
        )
        return

    current = note[field] or ""
    overwrite = bool(config.get("overwrite_existing", False))
    append = bool(config.get("append_mode", False))

    if current.strip() and not overwrite and not append:
        tooltip(
            f"Jisho Lookup: <b>{field}</b> ya tiene contenido. "
            "Activa 'sobrescribir' o 'añadir al final' en la configuración.",
            period=4000,
        )
        return

    if append and current.strip():
        note[field] = current + "<br>" + html
    else:
        note[field] = html

    try:
        mw.col.update_note(note)
    except Exception:
        try:
            note.flush()
        except Exception:
            pass

    if config.get("show_tooltip_on_success", True):
        origin_map = {
            "jisho": "Jisho",
            "local": "diccionario local",
            "varios": "mezcla de fuentes",
        }
        origin = origin_map.get(source, source or "?")
        tooltip(
            f"Jisho Lookup: <b>{query}</b> → campo <b>{field}</b> ({origin}).",
            period=2500,
        )

    # Refrescar la vista si ya se mostró la respuesta, para reflejar el nuevo contenido.
    try:
        if reviewer.state == "answer":
            reviewer._showAnswer()
        else:
            reviewer._showQuestion()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Acciones manuales (útiles para diagnóstico y como alternativa al atajo)


def _selection_or_tooltip(callback) -> None:
    if mw.state != "review":
        tooltip("Jisho Lookup: debes estar revisando una tarjeta.", period=2500)
        return
    reviewer = mw.reviewer
    if reviewer is None or reviewer.card is None:
        tooltip("Jisho Lookup: no hay tarjeta activa.", period=2500)
        return

    def got(sel: str) -> None:
        sel = (sel or "").strip()
        if not sel:
            tooltip("Jisho Lookup: selecciona una palabra con el ratón primero.", period=2500)
            return
        callback(sel)

    try:
        reviewer.web.evalWithCallback("window.getSelection().toString();", got)
    except Exception:
        tooltip("Jisho Lookup: no se pudo leer la selección.", period=2500)


def run_from_menu() -> None:
    """Lee selección y ejecuta la inserción automática (equivalente al atajo RUN)."""
    _selection_or_tooltip(_run_lookup_async)


def pick_from_menu() -> None:
    """Lee selección y abre el picker (equivalente al atajo PICK)."""
    _selection_or_tooltip(_run_picker_async)


# ---------------------------------------------------------------------------
# Instalación


def setup() -> None:
    gui_hooks.reviewer_did_show_question.append(_inject_listener)
    gui_hooks.reviewer_did_show_answer.append(_inject_listener)
    gui_hooks.webview_did_receive_js_message.append(_on_js_message)
    # Re-inyectar al volver al reviewer desde otro estado
    gui_hooks.state_did_change.append(
        lambda new_state, old_state: _inject_listener() if new_state == "review" else None
    )


def reload_shortcut() -> None:
    """Llamar tras guardar la config para aplicar atajos nuevos sin reiniciar."""
    _inject_listener()
