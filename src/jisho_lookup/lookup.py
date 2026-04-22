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
