# -*- coding: utf-8 -*-
"""Orquestador: recibe una palabra, busca definición, escribe al campo."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from . import jisho_client, yomitan_reader


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


# Normaliza la selección: quita signos de puntuación japoneses comunes
_TRIM_CHARS = "。、！？「」『』（）【】［］〈〉《》,.!?()[] \t\r\n\u3000"


def normalize_query(text: str) -> str:
    if not text:
        return ""
    # strip de puntuación en extremos
    cleaned = text.strip(_TRIM_CHARS)
    # si tras limpiar queda vacío, devolver original sin saltos de línea
    return cleaned or text.strip()


def do_lookup(query: str, config: dict) -> Tuple[str, str]:
    """Devuelve (html_resultado, fuente). html vacío si nada encontrado.

    `fuente` ∈ {"jisho", "local", ""}. Usado sólo para mensajes de UI.
    """
    query = normalize_query(query)
    if not query:
        return "", ""

    strategy = (config.get("strategy") or "jisho_then_local").lower()
    timeout = float(config.get("jisho_timeout_seconds") or 6)
    max_senses = int(config.get("max_senses") or 3)
    include_reading = bool(config.get("include_reading", True))
    include_pos = bool(config.get("include_parts_of_speech", True))
    enabled_dicts = config.get("enabled_local_dicts") or []

    # 1) Jisho
    if strategy in ("jisho_then_local", "jisho_only"):
        entries = jisho_client.search(query, timeout=timeout)
        if entries:
            html = jisho_client.format_entries(
                entries,
                max_senses=max_senses,
                include_reading=include_reading,
                include_parts_of_speech=include_pos,
            )
            if html:
                return html, "jisho"
        if strategy == "jisho_only":
            return "", ""

    # 2) Diccionarios locales
    if strategy in ("jisho_then_local", "local_only"):
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


def collect_choices(query: str, config: dict) -> Tuple[List[dict], str]:
    """Recopila TODAS las acepciones candidatas para el picker.

    Devuelve `(choices, header_info)`:
      choices: lista de dicts tal como los produce
               `jisho_client.entries_to_choices` /
               `yomitan_reader.entries_to_choices`.
      header_info: string corto para mostrar en el título del diálogo
               ej: "食べる 【たべる】" si la primera entrada Jisho lo da.

    Respeta la misma estrategia que `do_lookup`.
    """
    query = normalize_query(query)
    if not query:
        return [], ""

    strategy = (config.get("strategy") or "jisho_then_local").lower()
    timeout = float(config.get("jisho_timeout_seconds") or 6)
    enabled_dicts = config.get("enabled_local_dicts") or []

    choices: List[dict] = []
    header_word = ""
    header_reading = ""

    if strategy in ("jisho_then_local", "jisho_only"):
        entries = jisho_client.search(query, timeout=timeout)
        if entries:
            jc = jisho_client.entries_to_choices(entries)
            choices.extend(jc)
            # Información de cabecera
            if entries[0].word:
                header_word = entries[0].word
            if entries[0].reading:
                header_reading = entries[0].reading

    if strategy in ("jisho_then_local", "local_only"):
        mgr = get_dict_manager(enabled=enabled_dicts if enabled_dicts else None)
        local = mgr.lookup(query)
        if local:
            lc = yomitan_reader.entries_to_choices(local)
            choices.extend(lc)
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


def format_picked_choices(choices: List[dict], config: dict) -> str:
    """HTML final para el campo, a partir de una selección del picker."""
    if not choices:
        return ""

    include_reading = bool(config.get("include_reading", True))

    # Cabecera a partir de la primera opción
    first = choices[0]
    word = first.get("word") or ""
    reading = first.get("reading") or ""

    parts: List[str] = []
    head: List[str] = []
    if word:
        head.append(f"<b>{_esc_html(word)}</b>")
    if include_reading and reading and reading != word:
        head.append(f"【{_esc_html(reading)}】")
    if head:
        parts.append("".join(head))

    items = "".join(c.get("html") or "" for c in choices)
    if items:
        parts.append("<ol style='margin:4px 0 0 18px;padding:0'>" + items + "</ol>")

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
