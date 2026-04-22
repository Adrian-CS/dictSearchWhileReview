# -*- coding: utf-8 -*-
"""Lector de diccionarios en formato Yomichan / Yomitan.

Cada diccionario es un ZIP que contiene:
  - index.json           -> metadatos
  - term_bank_*.json     -> arrays de entradas
  - term_meta_bank_*.json (opcional, frecuencias)
  - kanji_bank_*.json (opcional)

Formato de cada entrada en term_bank_*.json (array posicional):
  [expression, reading, definition_tags, deinflection_rules,
   score, glossary, sequence, term_tags]

`glossary` suele ser una lista de strings o de dicts de "structured content".
Aquí lo normalizamos a HTML/texto plano para poder volcarlo en un campo.
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Tuple


class LocalEntry:
    __slots__ = ("expression", "reading", "glossary", "source")

    def __init__(self, expression: str, reading: str, glossary: List[str], source: str):
        self.expression = expression
        self.reading = reading
        self.glossary = glossary
        self.source = source


class LocalDictionary:
    """Un diccionario Yomitan cargado en memoria."""

    def __init__(self, name: str, zip_path: str):
        self.name = name
        self.zip_path = zip_path
        # índice: clave (expression o reading) -> lista de entradas
        self._index: Dict[str, List[LocalEntry]] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        try:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                for name in zf.namelist():
                    base = os.path.basename(name)
                    if not base.startswith("term_bank_") or not base.endswith(".json"):
                        continue
                    try:
                        with zf.open(name) as f:
                            data = json.loads(f.read().decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                    for row in data or []:
                        entry = _row_to_entry(row, source=self.name)
                        if entry is None:
                            continue
                        if entry.expression:
                            self._index.setdefault(entry.expression, []).append(entry)
                        if entry.reading and entry.reading != entry.expression:
                            self._index.setdefault(entry.reading, []).append(entry)
        except (zipfile.BadZipFile, FileNotFoundError, OSError):
            pass
        self._loaded = True

    def lookup(self, term: str) -> List[LocalEntry]:
        self.load()
        return list(self._index.get(term, []))


class DictionaryManager:
    """Agrupa varios diccionarios locales y consulta contra todos."""

    def __init__(self, dicts_dir: str, enabled: Optional[List[str]] = None):
        self.dicts_dir = dicts_dir
        # enabled es una lista de nombres sin .zip; si está vacía -> todos
        self.enabled = set(enabled or [])
        self.dicts: List[LocalDictionary] = []

    def discover(self) -> List[LocalDictionary]:
        self.dicts = []
        if not os.path.isdir(self.dicts_dir):
            return self.dicts
        for fn in sorted(os.listdir(self.dicts_dir)):
            if not fn.lower().endswith(".zip"):
                continue
            name = fn[:-4]
            if self.enabled and name not in self.enabled:
                continue
            path = os.path.join(self.dicts_dir, fn)
            self.dicts.append(LocalDictionary(name=name, zip_path=path))
        return self.dicts

    def available_names(self) -> List[str]:
        """Lista los nombres de todos los ZIPs encontrados (sin filtrar)."""
        if not os.path.isdir(self.dicts_dir):
            return []
        return sorted(
            fn[:-4]
            for fn in os.listdir(self.dicts_dir)
            if fn.lower().endswith(".zip")
        )

    def lookup(self, term: str) -> List[LocalEntry]:
        term = (term or "").strip()
        if not term:
            return []
        if not self.dicts:
            self.discover()
        results: List[LocalEntry] = []
        for d in self.dicts:
            results.extend(d.lookup(term))
        return results


# ----------------------------------------------------------------------
# Helpers


def _row_to_entry(row, *, source: str) -> Optional[LocalEntry]:
    try:
        expression = row[0] or ""
        reading = row[1] or ""
        glossary_raw = row[5] if len(row) > 5 else []
    except Exception:
        return None

    glossary = _flatten_glossary(glossary_raw)
    if not glossary:
        return None
    return LocalEntry(
        expression=expression,
        reading=reading,
        glossary=glossary,
        source=source,
    )


def _flatten_glossary(glossary) -> List[str]:
    """Aplana el formato 'structured-content' de Yomitan a texto plano."""
    out: List[str] = []
    if isinstance(glossary, list):
        for item in glossary:
            out.extend(_flatten_item(item))
    else:
        out.extend(_flatten_item(glossary))
    # limpiar espacios redundantes
    return [re.sub(r"\s+", " ", s).strip() for s in out if s and s.strip()]


def _flatten_item(item) -> List[str]:
    if item is None:
        return []
    if isinstance(item, str):
        return [item]
    if isinstance(item, (int, float)):
        return [str(item)]
    if isinstance(item, dict):
        t = item.get("type")
        if t in ("text", None) and "text" in item:
            return [str(item["text"])]
        if t == "structured-content":
            return _flatten_item(item.get("content"))
        if t == "image":
            return []
        # contenedor genérico
        content = item.get("content")
        if content is not None:
            return _flatten_item(content)
        return []
    if isinstance(item, list):
        out: List[str] = []
        for sub in item:
            out.extend(_flatten_item(sub))
        return out
    return [str(item)]


def format_local_entries(
    entries: Iterable[LocalEntry],
    *,
    max_senses: int = 3,
    include_reading: bool = True,
) -> str:
    entries = list(entries)
    if not entries:
        return ""

    # Agrupar por (expression, reading, source) para no duplicar
    seen: Dict[Tuple[str, str, str], LocalEntry] = {}
    for e in entries:
        key = (e.expression, e.reading, e.source)
        if key not in seen:
            seen[key] = e

    parts: List[str] = []
    first = next(iter(seen.values()))

    head: List[str] = []
    if first.expression:
        head.append(f"<b>{_esc(first.expression)}</b>")
    if include_reading and first.reading and first.reading != first.expression:
        head.append(f"【{_esc(first.reading)}】")
    if head:
        parts.append("".join(head))

    items: List[str] = []
    count = 0
    for e in seen.values():
        for g in e.glossary:
            items.append(
                f"<li>{_esc(g)} "
                f"<span style='color:#888;font-size:0.85em'>"
                f"— {_esc(e.source)}</span></li>"
            )
            count += 1
            if max_senses > 0 and count >= max_senses:
                break
        if max_senses > 0 and count >= max_senses:
            break

    if items:
        parts.append("<ol style='margin:4px 0 0 18px;padding:0'>" + "".join(items) + "</ol>")
    return "<div>" + "".join(parts) + "</div>"


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
