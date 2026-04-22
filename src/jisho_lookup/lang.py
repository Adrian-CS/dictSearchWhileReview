# -*- coding: utf-8 -*-
"""Pares de idiomas soportados y auto-detección por script Unicode."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# Pares soportados. Clave: "src_tgt" (códigos ISO-639-1).
PAIRS: Dict[str, dict] = {
    "ja_en": {"label": "Japonés → Inglés",  "src": "ja", "tgt": "en"},
    "en_ja": {"label": "Inglés → Japonés",  "src": "en", "tgt": "ja"},
    "es_en": {"label": "Español → Inglés",  "src": "es", "tgt": "en"},
    "en_es": {"label": "Inglés → Español",  "src": "en", "tgt": "es"},
}

DEFAULT_PAIR = "ja_en"


def all_pair_ids() -> List[str]:
    return list(PAIRS.keys())


def pair_label(pair_id: str) -> str:
    return PAIRS.get(pair_id, {}).get("label", pair_id)


def pair_parts(pair_id: str) -> Tuple[str, str]:
    """Devuelve (src_lang, tgt_lang). Si el par no existe, cae al default."""
    p = PAIRS.get(pair_id) or PAIRS[DEFAULT_PAIR]
    return p["src"], p["tgt"]


# ---------------------------------------------------------------------------
# Detección de script


_SPANISH_CHARS = set("áéíóúüñÁÉÍÓÚÜÑ¿¡")


def _has_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (
            0x3040 <= cp <= 0x309F     # hiragana
            or 0x30A0 <= cp <= 0x30FF  # katakana
            or 0x4E00 <= cp <= 0x9FFF  # CJK Unified
            or 0x3400 <= cp <= 0x4DBF  # CJK Ext A
            or 0xF900 <= cp <= 0xFAFF  # CJK Compat Ideographs
            or 0x20000 <= cp <= 0x2A6DF  # CJK Ext B
        ):
            return True
    return False


def _has_spanish_markers(text: str) -> bool:
    return any(ch in _SPANISH_CHARS for ch in text)


def _is_mostly_latin(text: str) -> bool:
    """True si la mayor parte son letras A-Za-z o acentuados latinos."""
    letters = 0
    latin = 0
    for ch in text:
        if ch.isspace():
            continue
        if ch.isalpha():
            letters += 1
            cp = ord(ch)
            if cp < 0x0300 or 0x00C0 <= cp <= 0x024F:
                latin += 1
    return letters > 0 and latin / max(letters, 1) > 0.6


def detect_source(text: str) -> str:
    """Devuelve 'ja', 'en' o 'es' según el texto. Default: 'en'."""
    if not text:
        return "en"
    if _has_cjk(text):
        return "ja"
    if _has_spanish_markers(text):
        return "es"
    if _is_mostly_latin(text):
        return "en"
    return "en"


def auto_detect_pair(text: str, global_pair: str = DEFAULT_PAIR) -> str:
    """Detecta el par más probable a partir del texto.

    Heurística: detectamos el *source* (ja/en/es). El *target* lo tomamos de
    `global_pair` si es coherente; si no, usamos un default sensato:
      ja → en,  es → en,  en → el tgt de `global_pair` o 'ja'.
    """
    src = detect_source(text)

    # Target preferido: el del par global si sigue siendo válido
    try:
        g_src, g_tgt = pair_parts(global_pair)
    except Exception:
        g_src, g_tgt = ("ja", "en")

    if src == "ja":
        tgt = "en"
    elif src == "es":
        tgt = "en"
    else:  # src == "en"
        # Preferimos el target del par global si es ja/es. Si el par global
        # ya tiene 'en' como target (ej. es_en, ja_en) invertimos hacia el
        # source de ese par (es/ja) para mantener coherencia. Si nada
        # aplica, caemos a 'ja' como default histórico.
        if g_tgt in ("ja", "es"):
            tgt = g_tgt
        elif g_src in ("ja", "es"):
            tgt = g_src
        else:
            tgt = "ja"

    if src == tgt:
        # imposible — forzamos algo razonable
        tgt = "en" if src != "en" else "ja"

    pair_id = f"{src}_{tgt}"
    if pair_id not in PAIRS:
        return global_pair
    return pair_id


# ---------------------------------------------------------------------------
# Fuentes por par


def sources_for_pair(pair_id: str) -> List[str]:
    """Qué fuentes online aplican a cada par. Local siempre es fallback."""
    src, tgt = pair_parts(pair_id)
    if {src, tgt} == {"ja", "en"}:
        return ["jisho"]
    if {src, tgt} == {"es", "en"}:
        return ["wiktionary"]
    return []  # desconocido: solo local


def normalize_pair(pair_id: Optional[str]) -> str:
    if pair_id and pair_id in PAIRS:
        return pair_id
    return DEFAULT_PAIR
