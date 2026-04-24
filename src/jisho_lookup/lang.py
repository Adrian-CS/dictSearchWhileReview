# -*- coding: utf-8 -*-
"""Pares de idiomas soportados y auto-detección por script Unicode."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# Pares soportados. Clave: "src_tgt" (códigos ISO-639-1).
# Nota: el label visible se obtiene vía `i18n.tr("pair.<pair_id>")` para que
# se traduzca al idioma de la UI de Anki; aquí sólo guardamos la estructura.
PAIRS: Dict[str, dict] = {
    # Japonés ↔ inglés (Jisho)
    "ja_en": {"src": "ja", "tgt": "en"},
    "en_ja": {"src": "en", "tgt": "ja"},
    # Español ↔ inglés (en.wiktionary REST + Translations)
    "es_en": {"src": "es", "tgt": "en"},
    "en_es": {"src": "en", "tgt": "es"},
    # Japonés ↔ español (es.wiktionary)
    "ja_es": {"src": "ja", "tgt": "es"},
    "es_ja": {"src": "es", "tgt": "ja"},
    # Coreano ↔ inglés (en.wiktionary REST + Translations)
    "ko_en": {"src": "ko", "tgt": "en"},
    "en_ko": {"src": "en", "tgt": "ko"},
    # Coreano → japonés (sólo diccionarios locales Yomitan)
    "ko_ja": {"src": "ko", "tgt": "ja"},
}

DEFAULT_PAIR = "ja_en"


def all_pair_ids() -> List[str]:
    return list(PAIRS.keys())


def pair_label(pair_id: str) -> str:
    """Etiqueta traducida del par. Cae al propio id si no hay traducción."""
    try:
        from . import i18n  # import local para evitar ciclos en tests
    except Exception:
        return pair_id
    key = f"pair.{pair_id}"
    label = i18n.tr(key)
    return label if label != key else pair_id


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


def _has_hangul(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (
            0xAC00 <= cp <= 0xD7AF      # Hangul Syllables
            or 0x1100 <= cp <= 0x11FF   # Hangul Jamo
            or 0x3130 <= cp <= 0x318F   # Hangul Compatibility Jamo
            or 0xA960 <= cp <= 0xA97F   # Hangul Jamo Extended-A
            or 0xD7B0 <= cp <= 0xD7FF   # Hangul Jamo Extended-B
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
    """Devuelve 'ja', 'ko', 'en' o 'es' según el texto. Default: 'en'.

    Orden de comprobación:
      1. Hangul → 'ko'. Se prueba antes que CJK porque algunas palabras
         coreanas pueden mezclar hanja con hangul; si hay al menos una
         sílaba hangul, la palabra es coreana.
      2. CJK (hiragana/katakana/kanji) → 'ja'.
      3. Marcas de español (¿¡áéíóúñ) → 'es'.
      4. Latino → 'en'.
    """
    if not text:
        return "en"
    if _has_hangul(text):
        return "ko"
    if _has_cjk(text):
        return "ja"
    if _has_spanish_markers(text):
        return "es"
    if _is_mostly_latin(text):
        return "en"
    return "en"


def auto_detect_pair(text: str, global_pair: str = DEFAULT_PAIR) -> str:
    """Detecta el par más probable a partir del texto.

    Heurística: detectamos el *source* (ja/en/es/ko). El *target* lo tomamos
    de `global_pair` si la combinación existe; si no, aplicamos un default
    razonable.

    Reglas por source:
      * `ja` → preferimos el tgt del par global si es en/es; si no, 'en'.
      * `ko` → preferimos el tgt del par global si es en/ja; si no, 'en'.
      * `es` → preferimos el tgt del par global si es en/ja; si no, 'en'.
      * `en` → preferimos el tgt del par global si es ja/es/ko; si el par
        global tenía 'en' como tgt, invertimos hacia su src (ja/es/ko); si
        nada aplica, caemos a 'ja' (default histórico).
    """
    src = detect_source(text)

    # Target preferido: el del par global si sigue siendo válido
    try:
        g_src, g_tgt = pair_parts(global_pair)
    except Exception:
        g_src, g_tgt = ("ja", "en")

    if src == "ja":
        tgt = g_tgt if g_tgt in ("en", "es") else "en"
    elif src == "ko":
        tgt = g_tgt if g_tgt in ("en", "ja") else "en"
    elif src == "es":
        tgt = g_tgt if g_tgt in ("en", "ja") else "en"
    else:  # src == "en"
        if g_tgt in ("ja", "es", "ko"):
            tgt = g_tgt
        elif g_src in ("ja", "es", "ko"):
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
    """Qué fuentes online aplican a cada par. Local siempre es fallback.

    Mapa actual:
      * ja↔en         → Jisho
      * es↔en, ko↔en  → Wiktionary (en.wiktionary REST / Translations)
      * ja↔es         → Wiktionary (es.wiktionary: secciones `{{lengua|ja}}`
                        y Traducciones con `{{t|ja|…}}`)
      * ko→ja         → ninguno online; sólo diccionarios locales (Yomitan).
    """
    src, tgt = pair_parts(pair_id)
    if {src, tgt} == {"ja", "en"}:
        return ["jisho"]
    if {src, tgt} == {"es", "en"}:
        return ["wiktionary"]
    if {src, tgt} == {"ko", "en"}:
        return ["wiktionary"]
    if {src, tgt} == {"ja", "es"}:
        return ["wiktionary"]
    # ko↔ja y otros casos exóticos: sin backend online.
    return []


def normalize_pair(pair_id: Optional[str]) -> str:
    if pair_id and pair_id in PAIRS:
        return pair_id
    return DEFAULT_PAIR
