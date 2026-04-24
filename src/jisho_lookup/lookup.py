# -*- coding: utf-8 -*-
"""Orquestador: recibe una palabra, busca definición, escribe al campo.

Soporta varios pares de idioma (ver `lang.py`). El par se elige así:

* Para el **popup** (selector de definición) siempre viene explícito, elegido
  por el usuario en el combo del diálogo.
* Para el **atajo rápido** (`do_lookup_auto`), usa el par global configurado
  y, si no encuentra nada, re-intenta con el par auto-detectado a partir
  del texto (siempre que ese par sea distinto).
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from . import jisho_client, wiktionary_client, yomitan_reader
from . import lang


ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
DICTS_DIR = os.path.join(ADDON_DIR, "dictionaries")


_DICT_MANAGER: Optional[yomitan_reader.DictionaryManager] = None


def get_dict_manager(enabled: Optional[List[str]] = None) -> yomitan_reader.DictionaryManager:
    """Singleton perezoso del DictionaryManager."""
    global _DICT_MANAGER
    if _DICT_MANAGER is None or _DICT_MANAGER.enabled != set(enabled or []):
        _DICT_MANAGER = yomitan_reader.DictionaryManager(DICTS_DIR, enabled=enabled)
        _DICT_MANAGER.discover()
    return _DICT_MANAGER


def reset_dict_manager() -> None:
    global _DICT_MANAGER
    _DICT_MANAGER = None


# Normaliza la selección: quita signos de puntuación comunes (JP + latinos)
_TRIM_CHARS = (
    "。、！？「」『』（）【】［］〈〉《》"
    ",.!?;:()[]{}\"'«»¡¿"
    " \t\r\n\u3000"
)


def normalize_query(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip(_TRIM_CHARS)
    return cleaned or text.strip()


# ---------------------------------------------------------------------------
# Búsqueda por par concreto (sin auto-detect)


def do_lookup(query: str, config: dict, pair: Optional[str] = None) -> Tuple[str, str]:
    """Busca en el par `pair` (o el global si None).

    Devuelve (html_resultado, fuente). Fuentes posibles:
      "jisho" | "wiktionary" | "local" | ""
    """
    query = normalize_query(query)
    if not query:
        return "", ""

    pair_id = lang.normalize_pair(pair or config.get("language_pair"))
    src, tgt = lang.pair_parts(pair_id)
    strategy = (config.get("strategy") or "jisho_then_local").lower()
    online_sources = lang.sources_for_pair(pair_id)

    jisho_timeout = float(config.get("jisho_timeout_seconds") or 6)
    wikt_timeout = float(config.get("wiktionary_timeout_seconds") or 6)
    max_senses = int(config.get("max_senses") or 3)
    include_reading = bool(config.get("include_reading", True))
    include_pos = bool(config.get("include_parts_of_speech", True))
    enabled_dicts = config.get("enabled_local_dicts") or []

    want_online = strategy in ("jisho_then_local", "jisho_only")
    want_local = strategy in ("jisho_then_local", "local_only")

    # 1) Fuente online según par
    if want_online:
        if "jisho" in online_sources:
            entries = jisho_client.search(query, timeout=jisho_timeout)
            if entries:
                if src == "en" and tgt == "ja":
                    # en→ja: las english_definitions de Jisho repiten la
                    # query en inglés (ej. "space, room" como glosa de 空き
                    # cuando el usuario ha buscado "space"). Reutilizamos
                    # format_picked_choices, que oculta ese texto. Como el
                    # texto queda oculto, dos "sentidos" de la misma
                    # palabra se renderizan idénticos — así que también
                    # deduplicamos por (palabra, lectura). Tomamos hasta
                    # `max_senses` candidatos distintos.
                    all_choices = jisho_client.entries_to_choices(entries)
                    seen: set = set()
                    choices: List[dict] = []
                    for c in all_choices:
                        key = (c.get("word") or "", c.get("reading") or "")
                        if key in seen:
                            continue
                        seen.add(key)
                        choices.append(c)
                        if len(choices) >= max(1, max_senses):
                            break
                    html = format_picked_choices(
                        choices,
                        config,
                        pair=pair_id,
                        include_pos=include_pos,
                        include_reading=include_reading,
                    )
                else:
                    html = jisho_client.format_entries(
                        entries,
                        max_senses=max_senses,
                        include_reading=include_reading,
                        include_parts_of_speech=include_pos,
                    )
                if html:
                    return html, "jisho"
        if "wiktionary" in online_sources:
            wentries = wiktionary_client.search(
                query, src=src, tgt=tgt, timeout=wikt_timeout
            )
            if wentries:
                # Modo traducciones (trans-blocks de Wiktionary): una entry
                # por palabra target con glosa en el idioma source. Toda
                # esta ruta se renderiza con `format_picked_choices`,
                # dedupando por palabra y dejando que `hide_text` oculte
                # la glosa redundante (el source == la palabra del query).
                # Aplica a `en→{ja, es, ko}` y `es→ja`.
                #
                # Modo definiciones (REST, parser `{{lengua|…}}`): glosas
                # directamente en el idioma target. Se renderiza con el
                # clásico `format_entries`. Aplica a `ja→es` y similares.
                is_translation = any(
                    getattr(e, "is_translation", False) for e in wentries
                )
                if is_translation:
                    all_choices = wiktionary_client.entries_to_choices(wentries)
                    seen: set = set()
                    choices: List[dict] = []
                    for c in all_choices:
                        key = (c.get("word") or "", c.get("reading") or "")
                        if key in seen:
                            continue
                        seen.add(key)
                        choices.append(c)
                        if len(choices) >= max(1, max_senses):
                            break
                    html = format_picked_choices(
                        choices,
                        config,
                        pair=pair_id,
                        include_pos=include_pos,
                        include_reading=include_reading,
                    )
                else:
                    html = wiktionary_client.format_entries(
                        wentries,
                        max_senses=max_senses,
                        include_reading=include_reading,
                        include_parts_of_speech=include_pos,
                    )
                if html:
                    return html, "wiktionary"
        if strategy == "jisho_only":
            return "", ""

    # 2) Diccionarios locales (sólo para pares con componente japonés, ya que
    # los diccionarios Yomichan/Yomitan actuales son JP↔EN). Igualmente
    # intentamos por si el usuario ha cargado algo útil.
    if want_local:
        mgr = get_dict_manager(enabled=enabled_dicts if enabled_dicts else None)
        local = mgr.lookup(query)
        if local:
            html = yomitan_reader.format_local_entries(
                local,
                max_senses=max_senses,
                include_reading=include_reading,
            )
            if html:
                return html, "local"

    return "", ""


def do_lookup_auto(query: str, config: dict) -> Tuple[str, str, str]:
    """Variante para el atajo rápido con routing por lengua detectada.

    Comportamiento con `language_pair_auto_fallback = True` (default):

    * Detectamos la lengua del texto seleccionado y obtenemos el par
      lógico para ese source (`lang.auto_detect_pair`).
    * Si el *source* detectado difiere del *source* del par global, el
      par detectado toma prioridad. Esto evita que, con global `ja→en`,
      seleccionar "space" en la carta vuelva definiciones **como si**
      el texto fuera japonés (Jisho cruza entre idiomas y devolvía
      `空き` con sus glosas inglesas, que es lo que el usuario ya tiene
      en la carta). Ahora esa selección se enruta por `en→ja` y entra
      en la rama `hide_text` de `format_picked_choices`.
    * Si el global falla y el detectado difiere, intentamos el
      detectado como segundo paso (y viceversa).

    Con `language_pair_auto_fallback = False` se respeta estrictamente
    el par global, sin detección.

    Devuelve (html, fuente, pair_id_usado).
    """
    global_pair = lang.normalize_pair(config.get("language_pair"))
    auto_enabled = bool(config.get("language_pair_auto_fallback", True))

    if not auto_enabled:
        html, source = do_lookup(query, config, pair=global_pair)
        return html, source, global_pair

    detected = lang.auto_detect_pair(query, global_pair=global_pair)

    g_src, _ = lang.pair_parts(global_pair)
    d_src, _ = lang.pair_parts(detected)

    # Si el texto parece claramente de otra lengua (source distinto),
    # el par detectado es más fiable. En caso contrario, el global
    # refleja mejor la preferencia del usuario (ej. ja→en vs es→en
    # cuando el target del global sería distinto al del detectado).
    if d_src != g_src:
        primary, secondary = detected, global_pair
    else:
        primary, secondary = global_pair, detected

    html, source = do_lookup(query, config, pair=primary)
    if html:
        return html, source, primary

    if secondary != primary:
        html, source = do_lookup(query, config, pair=secondary)
        if html:
            return html, source, secondary

    return "", "", primary


# ---------------------------------------------------------------------------
# Recolección de "choices" para el picker


def collect_choices(
    query: str, config: dict, pair: Optional[str] = None
) -> Tuple[List[dict], str]:
    """Recopila TODAS las acepciones candidatas para el picker.

    Devuelve `(choices, header_info)`.
    """
    query = normalize_query(query)
    if not query:
        return [], ""

    pair_id = lang.normalize_pair(pair or config.get("language_pair"))
    src, tgt = lang.pair_parts(pair_id)
    strategy = (config.get("strategy") or "jisho_then_local").lower()
    online_sources = lang.sources_for_pair(pair_id)

    jisho_timeout = float(config.get("jisho_timeout_seconds") or 6)
    wikt_timeout = float(config.get("wiktionary_timeout_seconds") or 6)
    enabled_dicts = config.get("enabled_local_dicts") or []

    want_online = strategy in ("jisho_then_local", "jisho_only")
    want_local = strategy in ("jisho_then_local", "local_only")

    choices: List[dict] = []
    header_word = ""
    header_reading = ""

    if want_online:
        if "jisho" in online_sources:
            entries = jisho_client.search(query, timeout=jisho_timeout)
            if entries:
                choices.extend(jisho_client.entries_to_choices(entries))
                if entries[0].word:
                    header_word = entries[0].word
                if entries[0].reading:
                    header_reading = entries[0].reading
        if "wiktionary" in online_sources:
            wentries = wiktionary_client.search(
                query, src=src, tgt=tgt, timeout=wikt_timeout
            )
            if wentries:
                choices.extend(wiktionary_client.entries_to_choices(wentries))
                if not header_word and wentries[0].word:
                    header_word = wentries[0].word

    if want_local:
        mgr = get_dict_manager(enabled=enabled_dicts if enabled_dicts else None)
        local = mgr.lookup(query)
        if local:
            choices.extend(yomitan_reader.entries_to_choices(local))
            if not header_word:
                header_word = local[0].expression
            if not header_reading:
                header_reading = local[0].reading

    header_bits: List[str] = []
    if header_word:
        header_bits.append(header_word)
    if header_reading and header_reading != header_word:
        header_bits.append(f"【{header_reading}】")
    header_info = " ".join(header_bits) if header_bits else query

    return choices, header_info


def format_picked_choices(
    choices: List[dict],
    config: dict,
    *,
    pair: Optional[str] = None,
    include_pos: Optional[bool] = None,
    include_reading: Optional[bool] = None,
) -> str:
    """HTML final para el campo, a partir de una selección del picker.

    Reglas de formato:

    * Si todas las opciones comparten la misma palabra (caso típico en
      `ja→en`, el usuario elige varias acepciones del mismo verbo), se
      emite una cabecera única y una lista con las acepciones.
    * Si las opciones abarcan palabras distintas (caso típico en
      `en→ja`, el usuario elige 空き y スペース como traducciones de
      "space"), se prepende la palabra+lectura a cada item y se omite
      la cabecera.

    Parámetros `include_pos` e `include_reading` permiten sobreescribir
    los valores globales del config (por ejemplo para que el popup
    decida en vivo si añadir las anotaciones gramaticales). Si se pasan
    como `None`, se cae al valor del config.

    Cuando el *src* del par es inglés y el *tgt* es japonés (`en→ja`),
    se omite el texto de la glosa: esa glosa son las
    `english_definitions` de Jisho (están en inglés) y repetirlas en
    el campo equivale a copiar de vuelta el query original.
    """
    if not choices:
        return ""

    if include_pos is None:
        include_pos = bool(config.get("include_parts_of_speech", True))
    if include_reading is None:
        include_reading = bool(config.get("include_reading", True))

    pair_id = lang.normalize_pair(pair or config.get("language_pair"))
    src, tgt = lang.pair_parts(pair_id)
    # Ocultamos la glosa cuando está en un idioma que el usuario ya lee
    # con fluidez (es decir, el idioma del *source* del par). Todos los
    # backends de traducciones de Wiktionary (y los `english_definitions`
    # de Jisho en `en→*`) ponen la glosa en ese idioma source:
    # * `en→{ja, es, ko}`  — glosa inglesa (Jisho o en.wiktionary).
    # * `es→ja`            — glosa española de es.wiktionary.
    # El usuario acaba de seleccionar esa palabra en la carta, así que
    # repetirla como "definición" sólo genera ruido. La palabra target
    # (+ lectura + POS opcional) es lo único valioso para insertar.
    hide_text = (src == "en") or (src == "es" and tgt == "ja")

    def _item_inner(c: dict) -> str:
        pos = c.get("pos") or ""
        text = c.get("text") or ""
        source = c.get("source") or ""
        bits: List[str] = []
        if include_pos and pos:
            bits.append(
                f"<span style='color:#888;font-size:0.9em'>"
                f"[{_esc_html(pos)}]</span>"
            )
        if not hide_text and text:
            bits.append(_esc_html(text))
        if source.startswith("local:"):
            bits.append(
                f"<span style='color:#888;font-size:0.85em'>"
                f"— {_esc_html(source[len('local:'):])}</span>"
            )
        return " ".join(bits)

    words = {(c.get("word") or "", c.get("reading") or "") for c in choices}
    single_word = len(words) == 1

    parts: List[str] = []

    if single_word:
        w, r = next(iter(words))
        head: List[str] = []
        if w:
            head.append(f"<b>{_esc_html(w)}</b>")
        if include_reading and r and r != w:
            head.append(f"【{_esc_html(r)}】")

        # Cuando ocultamos la glosa, lo que queda de cada item sería sólo
        # "[POS]" (y opcionalmente "— diccionario" si viene de un ZIP).
        # Con una sola palabra, una lista con varios "[Noun]" repetidos es
        # ruido sin información: integramos las POSes únicas en la cabecera
        # y omitimos el `<ol>`. Mantenemos el listado sólo si hay alguna
        # anotación de diccionario local, que sí es información útil.
        has_source_annot = any(
            (c.get("source") or "").startswith("local:") for c in choices
        )
        if hide_text and not has_source_annot:
            if include_pos:
                seen_pos: set = set()
                pos_bits: List[str] = []
                for c in choices:
                    p = c.get("pos") or ""
                    if p and p not in seen_pos:
                        seen_pos.add(p)
                        pos_bits.append(p)
                if pos_bits:
                    head.append(
                        "<span style='color:#888;font-size:0.9em'>["
                        + ", ".join(_esc_html(p) for p in pos_bits)
                        + "]</span>"
                    )
            if head:
                parts.append(" ".join(head))
        else:
            if head:
                parts.append("".join(head))
            items_html: List[str] = []
            for c in choices:
                inner = _item_inner(c)
                if inner:
                    items_html.append(f"<li>{inner}</li>")
            if items_html:
                parts.append(
                    "<ol style='margin:4px 0 0 18px;padding:0'>"
                    + "".join(items_html)
                    + "</ol>"
                )
    else:
        items_html: List[str] = []
        for c in choices:
            w = c.get("word") or ""
            r = c.get("reading") or ""
            inner = _item_inner(c)
            prefix_bits: List[str] = []
            if w:
                prefix_bits.append(f"<b>{_esc_html(w)}</b>")
            if include_reading and r and r != w:
                prefix_bits.append(f"【{_esc_html(r)}】")
            prefix = "".join(prefix_bits)
            if prefix and inner:
                full = prefix + " " + inner
            else:
                full = prefix or inner
            if full:
                items_html.append(f"<li>{full}</li>")
        if items_html:
            parts.append(
                "<ol style='margin:4px 0 0 18px;padding:0'>"
                + "".join(items_html)
                + "</ol>"
            )

    return "<div>" + "".join(parts) + "</div>"


def _esc_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def pick_target_field(note, config: dict) -> Optional[str]:
    """Decide qué campo rellenar en `note` según `note_type_field_map`.

    Usa el mapeo específico del notetype si existe, si no `_default`.
    Devuelve el nombre del campo o None.
    """
    try:
        model = note.note_type() or {}
    except Exception:
        model = getattr(note, "model", lambda: {})() or {}

    model_name = model.get("name", "") if isinstance(model, dict) else ""
    fieldmap = config.get("note_type_field_map") or {}

    candidates: List[str] = []
    if model_name and model_name in fieldmap:
        candidates = list(fieldmap[model_name] or [])
    if not candidates:
        candidates = list(fieldmap.get("_default") or [])

    note_fields = {f: True for f in note.keys()}
    for name in candidates:
        if name in note_fields:
            return name
    return None


def available_field_candidates(note, config: dict) -> List[str]:
    """Devuelve la lista ordenada de candidatos válidos para el picker.

    El diálogo permite cambiar manualmente el campo destino; mostramos
    primero los candidatos definidos en `note_type_field_map` y después
    el resto de campos de la tarjeta.
    """
    try:
        model = note.note_type() or {}
    except Exception:
        model = getattr(note, "model", lambda: {})() or {}

    model_name = model.get("name", "") if isinstance(model, dict) else ""
    fieldmap = config.get("note_type_field_map") or {}

    preferred: List[str] = []
    if model_name and model_name in fieldmap:
        preferred.extend(fieldmap[model_name] or [])
    preferred.extend(fieldmap.get("_default") or [])

    note_fields = list(note.keys())
    present = [f for f in preferred if f in note_fields]
    rest = [f for f in note_fields if f not in present]
    # dedup preservando orden
    seen = set()
    out: List[str] = []
    for name in present + rest:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out
