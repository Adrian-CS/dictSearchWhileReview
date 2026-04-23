# -*- coding: utf-8 -*-
"""Integración con el Reviewer.

Dos flujos:
  1) RUN   — atajo rápido: inserta todas las acepciones automáticamente,
             usando el par de idioma global y, si no encuentra nada,
             re-intentando con el par auto-detectado (si está activado).
  2) PICK  — atajo con popup: abre un diálogo con:
               * combo de campo destino
               * radios Sustituir / Añadir
               * combo de par de idioma (recarga en vivo)
               * lista de acepciones (multi-selección opcional)

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
from typing import List, Optional, Tuple

from aqt import mw, gui_hooks
from aqt.utils import tooltip
from aqt.operations import QueryOp

from . import lang
from . import lookup
from . import picker_dialog
from .i18n import tr


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
            tooltip(tr("reviewer.select_first"), period=2500)
            return (True, None)
        _run_lookup_async(selected)
        return (True, None)

    if message.startswith(PYCMD_PICK):
        selected = message[len(PYCMD_PICK):].strip()
        if not selected:
            tooltip(tr("reviewer.select_first"), period=2500)
            return (True, None)
        _run_picker_async(selected)
        return (True, None)

    return handled


# ---------------------------------------------------------------------------
# Pipeline RUN — inserción automática (con fallback auto-detect)


def _run_lookup_async(selected: str) -> None:
    config = _current_config()

    def worker(_col) -> Tuple[str, str, str, str]:
        html, source, used_pair = lookup.do_lookup_auto(selected, config)
        return (selected, html, source, used_pair)

    def on_done(result: Tuple[str, str, str, str]) -> None:
        query, html, source, used_pair = result
        if not html:
            if config.get("show_tooltip_on_error", True):
                tooltip(tr("reviewer.not_found", query=query), period=3000)
            return
        _write_to_current_card(
            query, html, source, config, used_pair=used_pair
        )

    op = QueryOp(parent=mw, op=worker, success=on_done)
    op.with_progress(label=tr("reviewer.searching")).run_in_background()


# ---------------------------------------------------------------------------
# Pipeline PICK — diálogo popup de selección


def _run_picker_async(selected: str) -> None:
    config = _current_config()
    global_pair = lang.normalize_pair(config.get("language_pair"))

    # Si el usuario tiene activado el auto-fallback, aplicamos la detección
    # también al abrir el popup: da igual qué par global tengas, si el
    # texto es claramente de otro idioma abrimos ya apuntando al par que
    # sí tiene sentido. El combo sigue disponible para cambiar a mano.
    if bool(config.get("language_pair_auto_fallback", True)):
        initial_pair = lang.auto_detect_pair(selected, global_pair=global_pair)
    else:
        initial_pair = global_pair

    def worker(_col) -> Tuple[str, List[dict], str]:
        choices, header = lookup.collect_choices(selected, config, pair=initial_pair)
        return (selected, choices, header)

    def on_done(result: Tuple[str, List[dict], str]) -> None:
        query, choices, header = result

        # Construimos el callback de recarga para cambiar idioma en vivo.
        def reload_fn(pair_id: str) -> Tuple[List[dict], str]:
            try:
                return lookup.collect_choices(query, _current_config(), pair=pair_id)
            except Exception:
                return [], ""

        # Campos candidatos (según la tarjeta actual)
        field_candidates: List[str] = []
        initial_field: Optional[str] = None
        reviewer = mw.reviewer
        if reviewer is not None and reviewer.card is not None:
            note = reviewer.card.note()
            field_candidates = lookup.available_field_candidates(note, config)
            initial_field = lookup.pick_target_field(note, config)

        initial_mode = (
            "append"
            if bool(config.get("append_mode", False))
            and not bool(config.get("overwrite_existing", False))
            else "overwrite"
        )

        multi = bool(config.get("picker_multi_select", True))

        if not choices:
            # Aun así abrimos el diálogo para permitir cambiar de idioma.
            if config.get("show_tooltip_on_error", True):
                tooltip(
                    tr("reviewer.not_found_picker", query=query),
                    period=2500,
                )

        bundle = picker_dialog.show_picker(
            choices,
            header=header or query,
            multi_select=multi,
            field_candidates=field_candidates,
            initial_field=initial_field,
            initial_mode=initial_mode,
            initial_pair=initial_pair,
            initial_include_pos=bool(
                config.get("include_parts_of_speech", True)
            ),
            reload_fn=reload_fn,
            parent=mw,
        )
        if not bundle:
            return

        picked = bundle["picked"]
        chosen_field = bundle["field"]
        chosen_mode = bundle["mode"]
        chosen_pair = bundle["pair"]
        chosen_include_pos = bool(bundle.get("include_pos", True))

        html = lookup.format_picked_choices(
            picked,
            config,
            pair=chosen_pair,
            include_pos=chosen_include_pos,
        )
        if not html:
            return

        sources = {c.get("source", "") for c in picked}
        if len(sources) == 1:
            src = next(iter(sources))
        else:
            src = "mixed"

        _write_to_current_card(
            query,
            html,
            src,
            config,
            used_pair=chosen_pair,
            override_field=chosen_field,
            override_mode=chosen_mode,
        )

    op = QueryOp(parent=mw, op=worker, success=on_done)
    op.with_progress(label=tr("reviewer.searching_picker")).run_in_background()


# ---------------------------------------------------------------------------
# Escritura al campo


def _write_to_current_card(
    query: str,
    html: str,
    source: str,
    config: dict,
    *,
    used_pair: Optional[str] = None,
    override_field: Optional[str] = None,
    override_mode: Optional[str] = None,  # "overwrite" | "append" | None
) -> None:
    reviewer = mw.reviewer
    if reviewer is None or reviewer.card is None:
        return
    card = reviewer.card
    note = card.note()

    # 1) Campo
    if override_field and override_field in note.keys():
        field = override_field
    else:
        field = lookup.pick_target_field(note, config)

    if field is None:
        model = note.note_type() or {}
        model_name = model.get("name", "?") if isinstance(model, dict) else "?"
        available = ", ".join(note.keys())
        tooltip(
            tr("reviewer.no_field", model=model_name, fields=available),
            period=5500,
        )
        return

    # 2) Modo de escritura
    if override_mode is not None:
        overwrite = override_mode == "overwrite"
        append = override_mode == "append"
    else:
        overwrite = bool(config.get("overwrite_existing", False))
        append = bool(config.get("append_mode", False))

    current = note[field] or ""

    if current.strip() and not overwrite and not append:
        tooltip(
            tr("reviewer.field_has_content", field=field),
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
            "jisho": tr("source.jisho"),
            "wiktionary": tr("source.wiktionary"),
            "local": tr("source.local"),
            "mixed": tr("source.mixed"),
            "varios": tr("source.mixed"),
        }
        origin = origin_map.get(source, source or "?")
        pair_suffix = ""
        if used_pair:
            pair_suffix = f" · {lang.pair_label(used_pair)}"
        tooltip(
            tr(
                "reviewer.success",
                query=query,
                field=field,
                origin=origin,
                pair_suffix=pair_suffix,
            ),
            period=2500,
        )

    # Refrescar la vista.
    #
    # Anki cachea el HTML renderizado en `card._render_output`. Si sólo
    # llamamos `_showQuestion` / `_showAnswer` volveremos a ver el
    # contenido viejo. Hay que invalidar el caché y recargar la carta
    # desde la BD para forzar un render nuevo con los campos actualizados.
    try:
        card._render_output = None  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        card.load()
    except Exception:
        pass

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
        tooltip(tr("reviewer.not_reviewing"), period=2500)
        return
    reviewer = mw.reviewer
    if reviewer is None or reviewer.card is None:
        tooltip(tr("reviewer.no_card"), period=2500)
        return

    def got(sel: str) -> None:
        sel = (sel or "").strip()
        if not sel:
            tooltip(tr("reviewer.select_first"), period=2500)
            return
        callback(sel)

    try:
        reviewer.web.evalWithCallback("window.getSelection().toString();", got)
    except Exception:
        tooltip(tr("reviewer.no_read"), period=2500)


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
