#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera un ZIP en formato Yomitan donde el índice son palabras en español
y las definiciones son las expresiones japonesas correspondientes del JMdict.

Uso:
    python make_es_ja_dict.py JMdict_spanish.zip
    # Genera: JMdict_spanish_reversed.zip

Copia el ZIP resultante en src/jisho_lookup/dictionaries/ (o en la
carpeta equivalente del add-on instalado) y úsalo con el par es→ja
en modo local.
"""

from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from typing import Dict, List, Tuple


# Palabras vacías que no merece la pena indexar por separado.
_STOP_WORDS = {
    "de", "del", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "y", "e", "o", "u", "a", "en", "con", "por", "para", "que", "se",
    "su", "al", "lo", "no", "ni", "si", "es", "son", "ser", "estar",
    "como", "más", "muy", "también", "pero", "sin", "sobre", "entre",
    "este", "esta", "esto", "ese", "esa", "eso", "aquel", "aquella",
    "mi", "tu", "nos", "os", "les", "le", "me", "te",
    "ha", "he", "han", "haber", "hay", "algo", "algún", "alguna",
}

_PUNCT_RE = re.compile(r"[^\w\sáéíóúñüÁÉÍÓÚÑÜ]", re.UNICODE)
_SPLIT_RE = re.compile(r"[\s;,/·•()\[\]「」【】]+")


# ---------------------------------------------------------------------------
# Parseo del ZIP fuente

def _extract_text(node) -> List[str]:
    """Extrae texto de structured-content de Yomitan (recursivo)."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        out: List[str] = []
        for item in node:
            out.extend(_extract_text(item))
        return out
    if isinstance(node, dict):
        if "text" in node:
            return [str(node["text"])]
        if "content" in node:
            return _extract_text(node["content"])
    return []


def _flatten_glossary(raw) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                t = item.get("type", "")
                if t == "structured-content":
                    out.extend(_extract_text(item.get("content", "")))
                elif "text" in item:
                    out.append(str(item["text"]))
    return [s.strip() for s in out if s.strip()]


def read_entries(zip_path: str) -> List[list]:
    entries: List[list] = []
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(z.namelist()):
            if name.startswith("term_bank_") and name.endswith(".json"):
                data = json.loads(z.read(name).decode("utf-8", errors="replace"))
                entries.extend(data)
    return entries


# ---------------------------------------------------------------------------
# Construcción del índice inverso

def _words(gloss: str) -> List[str]:
    """Palabras individuales de una glosa, sin stop words ni muy cortas."""
    cleaned = _PUNCT_RE.sub(" ", gloss)
    parts = [p.strip().lower() for p in _SPLIT_RE.split(cleaned) if p.strip()]
    return [p for p in parts if len(p) > 1 and p not in _STOP_WORDS]


def build_reverse_index(
    entries: List[list],
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Devuelve {palabra_española: [(expresión_ja, lectura_ja), ...]}

    Cada entrada japonesa se indexa bajo:
      - La glosa española completa (normalizada a minúsculas).
      - Cada palabra individual de la glosa (sin stop words).
    """
    # Usamos dict ordenado para preservar el orden de inserción y deduplicar.
    acc: Dict[str, Dict[Tuple[str, str], None]] = defaultdict(dict)

    for row in entries:
        try:
            expr = (row[0] or "").strip()
            read = (row[1] or "").strip()
            glossary_raw = row[5] if len(row) > 5 else []
        except (IndexError, TypeError):
            continue

        if not expr:
            continue

        glosses = _flatten_glossary(glossary_raw)
        for gloss in glosses:
            if not gloss:
                continue
            # Glosa completa → útil cuando la búsqueda es una frase.
            full = gloss.strip().lower()
            if full:
                acc[full][(expr, read)] = None
            # Palabras individuales → búsqueda por palabra suelta.
            for word in _words(gloss):
                acc[word][(expr, read)] = None

    return {k: list(v.keys()) for k, v in acc.items()}


# ---------------------------------------------------------------------------
# Generación del ZIP Yomitan

def build_term_rows(reverse: Dict[str, List[Tuple[str, str]]]) -> List[list]:
    rows: List[list] = []
    for es_word, ja_pairs in reverse.items():
        if not ja_pairs:
            continue
        glossary: List[str] = []
        for expr, read in ja_pairs[:40]:   # máx 40 entradas por lema
            if read and read != expr:
                glossary.append(f"{expr} 【{read}】")
            else:
                glossary.append(expr)
        rows.append([
            es_word,   # expression  — palabra española
            "",        # reading
            "",        # definition_tags
            "",        # deinflection_rules
            0,         # score
            glossary,  # glosas → lista de palabras japonesas
            0,         # sequence
            "",        # term_tags
        ])
    return rows


def write_zip(rows: List[list], out_path: str, title: str) -> None:
    index = {
        "title": title,
        "format": 3,
        "revision": "1",
        "sequenced": False,
        "author": "jisho-lookup-addon",
        "description": (
            "Índice inverso ES→JA generado desde JMdict Spanish. "
            "Busca una palabra en español y obtiene las expresiones "
            "japonesas equivalentes."
        ),
    }
    chunk = 10_000
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.json", json.dumps(index, ensure_ascii=False))
        for i, start in enumerate(range(0, len(rows), chunk), 1):
            z.writestr(
                f"term_bank_{i}.json",
                json.dumps(rows[start : start + chunk], ensure_ascii=False),
            )


# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    in_path = sys.argv[1]
    if not os.path.isfile(in_path):
        print(f"ERROR: no existe {in_path}", file=sys.stderr)
        return 1

    stem = os.path.splitext(os.path.basename(in_path))[0]
    out_path = os.path.join(os.path.dirname(in_path) or ".", stem + "_reversed.zip")
    title = stem + " (ES→JA reversed)"

    print(f"Leyendo {in_path}...")
    entries = read_entries(in_path)
    print(f"  {len(entries):,} entradas.")

    print("Construyendo indice inverso ES->JA...")
    reverse = build_reverse_index(entries)
    print(f"  {len(reverse):,} lemas espanoles indexados.")

    print("Generando filas de term_bank...")
    rows = build_term_rows(reverse)

    print(f"Escribiendo {out_path}...")
    write_zip(rows, out_path, title)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Listo. {len(rows):,} entradas  ({size_kb:.0f} KB)")
    print(f"\nCopia {out_path} en src/jisho_lookup/dictionaries/ y reinicia Anki.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
