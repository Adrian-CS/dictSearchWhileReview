#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera un ZIP en formato Yomitan indexado por palabras en espanol,
con resultados ordenados por relevancia y frecuencia:

  Prioridad 0  -- la palabra espanola ES la primera glosa completa
  Prioridad 1  -- la palabra espanola ES alguna otra glosa completa
  Prioridad 2  -- la palabra espanola ESTA en la primera glosa
  Prioridad 3  -- la palabra espanola ESTA en alguna otra glosa
  (dentro de cada prioridad: mas frecuente en japones primero)

Uso:
    python make_es_ja_dict.py JMdict_spanish.zip [--out DEST.zip] [--top N]

    --top N   Maximo de entradas japonesas por lema espanol (default: 15)

Coloca el ZIP resultante en src/jisho_lookup/dictionaries/ y reinicia Anki.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple


_STOP_WORDS = {
    "de", "del", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "y", "e", "o", "u", "a", "en", "con", "por", "para", "que", "se",
    "su", "al", "lo", "no", "ni", "si", "es", "son", "ser", "estar",
    "como", "mas", "muy", "tambien", "pero", "sin", "sobre", "entre",
    "este", "esta", "esto", "ese", "esa", "eso", "mi", "tu", "nos",
    "os", "les", "le", "me", "te", "ha", "he", "han", "haber", "hay",
    "algo", "algun", "alguna", "cada", "todo", "toda", "todos", "todas",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPLIT_RE = re.compile(r"[\s;,/\(\)\[\]]+")


# ---------------------------------------------------------------------------
# Helpers de texto

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _strip_accents(text: str) -> str:
    """Elimina diacriticos: actividad -> actividad, accion -> accion."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _key_variants(word: str) -> List[str]:
    """Devuelve la palabra normalizada y, si difiere, tambien sin acentos."""
    w = _nfc(word.strip().lower())
    ws = _strip_accents(w)
    return list(dict.fromkeys([w, ws]))   # dedup manteniendo orden


def _word_set(text: str) -> Set[str]:
    """Conjunto de palabras significativas de un texto."""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    parts = {p.strip() for p in _SPLIT_RE.split(cleaned) if p.strip()}
    # incluimos versiones sin acento
    expanded: Set[str] = set()
    for p in parts:
        if len(p) > 1 and p not in _STOP_WORDS:
            expanded.add(p)
            expanded.add(_strip_accents(p))
    return expanded


# ---------------------------------------------------------------------------
# Lectura del ZIP fuente (JMdict Spanish)

def _extract_text(node) -> List[str]:
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
# Prioridad de match

def _match_priority(key: str, glosses: List[str]) -> int:
    """
    Que tan bien encaja `key` (espanol, ya en minuscula) con las glosas
    de una entrada japonesa.

    0 = key ES la primera glosa (match exacto)
    1 = key ES alguna otra glosa (match exacto, no primera)
    2 = key APARECE como palabra en la primera glosa
    3 = key APARECE como palabra en alguna otra glosa
    99 = no match (no deberia ocurrir, pero por si acaso)
    """
    if not glosses:
        return 99
    first_lower = _nfc(glosses[0].strip().lower())
    if first_lower == key or _strip_accents(first_lower) == key:
        return 0
    for gloss in glosses[1:]:
        gloss_lower = _nfc(gloss.strip().lower())
        if gloss_lower == key or _strip_accents(gloss_lower) == key:
            return 1
    if key in _word_set(glosses[0]):
        return 2
    for gloss in glosses[1:]:
        if key in _word_set(gloss):
            return 3
    return 99


# ---------------------------------------------------------------------------
# Construccion del indice inverso

# {es_word: {(expr_ja, read_ja): (priority, score)}}
ReverseIdx = Dict[str, Dict[Tuple[str, str], Tuple[int, int]]]


def _update(acc: ReverseIdx, key: str, expr: str, read: str,
            score: int, priority: int) -> None:
    if not key or priority >= 99:
        return
    pair = (expr, read)
    existing = acc[key].get(pair)
    if existing is None:
        acc[key][pair] = (priority, score)
    else:
        prev_p, prev_s = existing
        # Menor prioridad (numero mas bajo) gana; empate -> mayor frecuencia
        if priority < prev_p or (priority == prev_p and score > prev_s):
            acc[key][pair] = (priority, score)


def build_reverse_index(entries: List[list]) -> ReverseIdx:
    acc: ReverseIdx = defaultdict(dict)

    for row in entries:
        try:
            expr = (row[0] or "").strip()
            read = (row[1] or "").strip()
            score = int(row[4]) if len(row) > 4 else 0
            glossary_raw = row[5] if len(row) > 5 else []
        except (IndexError, TypeError, ValueError):
            continue
        if not expr:
            continue

        glosses = _flatten_glossary(glossary_raw)
        if not glosses:
            continue

        # Indexar por cada glosa (completa) y por cada palabra de cada glosa
        for gloss in glosses:
            # Clave: glosa completa normalizada
            for key in _key_variants(gloss):
                if len(key) > 1 and key not in _STOP_WORDS:
                    p = _match_priority(key, glosses)
                    _update(acc, key, expr, read, score, p)

            # Clave: palabras individuales de la glosa
            for word in _word_set(gloss):
                if len(word) > 1:
                    p = _match_priority(word, glosses)
                    _update(acc, word, expr, read, score, p)

    return acc


# ---------------------------------------------------------------------------
# Generacion del ZIP Yomitan

def build_term_rows(reverse: ReverseIdx, top: int = 15) -> List[list]:
    rows: List[list] = []
    for es_word, scored in reverse.items():
        if not scored:
            continue
        # Ordenar: (prioridad ASC, frecuencia DESC)
        best = sorted(scored.items(), key=lambda x: (x[1][0], -x[1][1]))[:top]

        glossary: List[str] = []
        for (expr, read), (prio, _score) in best:
            if read and read != expr:
                glossary.append(f"{expr} [{read}]")
            else:
                glossary.append(expr)

        rows.append([
            es_word,   # expression  -- palabra espanola
            "",        # reading
            "",        # definition_tags
            "",        # deinflection_rules
            0,         # score
            glossary,
            0,         # sequence
            "",        # term_tags
        ])
    return rows


def write_zip(rows: List[list], out_path: str, title: str) -> None:
    index = {
        "title": title,
        "format": 3,
        "revision": "3",
        "sequenced": False,
        "author": "jisho-lookup-addon",
        "description": (
            "Reverse index ES->JA from JMdict Spanish. "
            "Results sorted by gloss-position priority and word frequency."
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_in", help="JMdict_spanish.zip de entrada")
    parser.add_argument("--out", help="Ruta de salida (por defecto <stem>_reversed.zip)")
    parser.add_argument("--top", type=int, default=15,
                        help="Max entradas japonesas por lema (default: 15)")
    args = parser.parse_args()

    in_path = args.zip_in
    if not os.path.isfile(in_path):
        print(f"ERROR: no existe {in_path}", file=sys.stderr)
        return 1

    stem = os.path.splitext(os.path.basename(in_path))[0]
    out_path = args.out or os.path.join(
        os.path.dirname(in_path) or ".", stem + "_reversed.zip"
    )

    print(f"Leyendo {in_path}...")
    entries = read_entries(in_path)
    print(f"  {len(entries):,} entradas japonesas.")

    print(f"Construyendo indice inverso (top {args.top}, con prioridad de glosa)...")
    reverse = build_reverse_index(entries)
    print(f"  {len(reverse):,} lemas espanoles indexados.")

    print("Generando filas term_bank...")
    rows = build_term_rows(reverse, top=args.top)

    print(f"Escribiendo {out_path}...")
    write_zip(rows, out_path, stem + " (ES->JA reversed)")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Listo. {len(rows):,} entradas ({size_kb:.0f} KB).")

    # Copiar automaticamente a la carpeta de diccionarios del proyecto
    dicts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "src", "jisho_lookup", "dictionaries"
    )
    if os.path.isdir(dicts_dir):
        dest = os.path.join(dicts_dir, os.path.basename(out_path))
        shutil.copy2(out_path, dest)
        print(f"\nCopiado a: {dest}")
        print("Reinicia Anki o pulsa 'Reload list' en la config del add-on.")
    else:
        print(f"\nCopia {out_path} en tu carpeta dictionaries/ y reinicia Anki.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
