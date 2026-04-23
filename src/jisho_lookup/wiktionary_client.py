# -*- coding: utf-8 -*-
"""Cliente para Wiktionary con tres estrategias distintas según el par:

1. **REST** `page/definition/{word}` en `en.wiktionary.org` — para pares
   cuyo *target* es inglés (típicamente `es→en`). Devuelve JSON bien
   estructurado agrupado por idioma de la palabra. Ojo: este endpoint
   está activo **sólo en en.wiktionary**; los otros wikis devuelven 404.

2. **Action API** `action=parse&prop=wikitext` en `en.wiktionary.org`
   con extractor de la sub-sección `====Translations====` — para
   pares `en→{otro}` (típicamente `en→es`). Leemos los bloques
   `{{trans-top|gloss}} … {{trans-bottom}}` y de cada uno sacamos
   las plantillas `{{t|<lang>|palabra}}`, `{{t+|...}}`, `{{t-|...}}`.
   Funciona porque en.wiktionary mantiene listas de traducciones
   muy completas para prácticamente cualquier palabra inglesa, cosa
   que es.wiktionary no hace (y que por eso intentar parsear allí
   la sección `{{lengua|en}}` da casi siempre vacío).

3. **Action API** `action=parse&prop=wikitext` en
   `{host}.wiktionary.org` buscando la sección `== {{lengua|<src>}} ==`
   y extrayendo definiciones `;N:` — usado como fallback y para
   pares exóticos sin inglés.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import List, Optional


_TAG_RE = re.compile(r"<[^>]+>")
_UA = "AnkiJishoLookup/1.2 (+https://github.com/Adrian-CS/dictSearchWhileReview)"


class WiktEntry:
    __slots__ = ("word", "part_of_speech", "definitions")

    def __init__(
        self,
        word: str,
        part_of_speech: str,
        definitions: List[str],
    ):
        self.word = word
        self.part_of_speech = part_of_speech
        self.definitions = definitions


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return _TAG_RE.sub("", s).strip()


# ---------------------------------------------------------------------------
# Dispatcher


def search(
    query: str,
    src: str,
    tgt: str,
    *,
    timeout: float = 6.0,
) -> Optional[List[WiktEntry]]:
    """Consulta Wiktionary. Elige el backend apropiado según el par."""
    query = (query or "").strip()
    if not query:
        return None
    if tgt == "en":
        return _search_rest_en(query, src_lang=src, timeout=timeout)
    if src == "en":
        # en→{otro}: el path fiable es leer la sección Translations de
        # en.wiktionary. Si no hay Translations útiles, caemos al
        # parser genérico de `{{lengua|en}}` en el wiki del target
        # (suele dar poco, pero no cuesta intentar).
        result = _search_translations_en_wiki(query, target_lang=tgt, timeout=timeout)
        if result:
            return result
    return _search_parse_wiki(query, src_lang=src, wiki_host=tgt, timeout=timeout)


# ---------------------------------------------------------------------------
# Backend REST (en.wiktionary.org)


def _search_rest_en(
    query: str, *, src_lang: str, timeout: float
) -> Optional[List[WiktEntry]]:
    url = (
        "https://en.wiktionary.org/api/rest_v1/page/definition/"
        + urllib.parse.quote(query, safe="")
    )
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _UA, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    section = payload.get(src_lang)
    if not section and src_lang == "en":
        section = payload.get("other")
    if not isinstance(section, list):
        return None

    out: List[WiktEntry] = []
    for block in section:
        if not isinstance(block, dict):
            continue
        pos = _strip_html(block.get("partOfSpeech") or "")
        defs: List[str] = []
        for d in block.get("definitions") or []:
            if isinstance(d, dict):
                text = _strip_html(d.get("definition") or "")
                if text:
                    defs.append(text)
        if defs:
            out.append(
                WiktEntry(word=query, part_of_speech=pos, definitions=defs)
            )
    return out or None


# ---------------------------------------------------------------------------
# Backend para en→{otro}: lee Translations en en.wiktionary


# {{trans-top|gloss}} … {{trans-bottom}} (también acepta trans-top-also)
_TRANS_BLOCK_RE = re.compile(
    r"\{\{\s*trans-top(?:-also)?(?:\s*\|([^}]*))?\s*\}\}(.*?)\{\{\s*trans-bottom\s*\}\}",
    re.DOTALL | re.IGNORECASE,
)
# {{t|es|palabra}}, {{t+|es|palabra}}, {{t-|es|palabra}}, {{tt|es|…}}, {{tø|es|…}}
# Permitimos una letra opcional tras la t y opcionalmente un +/-.
# NOTA: se completa dinámicamente con el código de idioma, por eso no usamos
# `str.format` (las llaves `{{…}}` del wikitext chocarían con el formateador).
_T_TPL_PREFIX = r"\{\{\s*t[+\-]?[a-zø]?\s*\|\s*"
_T_TPL_SUFFIX = r"\s*\|\s*([^}|]+)(?:\|[^}]*)?\s*\}\}"
# ==English== abre un L2. Cortamos en el siguiente L2 (==OtroIdioma==).
_L2_HEADING_RE = re.compile(r"^==\s*([^=\n][^=\n]*?)\s*==\s*$", re.MULTILINE)


def _extract_english_section(wikitext: str) -> str:
    m = None
    for mm in _L2_HEADING_RE.finditer(wikitext):
        if mm.group(1).strip().lower() == "english":
            m = mm
            break
    if not m:
        return ""
    start = m.end()
    # Siguiente L2 = fin de la sección English
    nxt = None
    for mm in _L2_HEADING_RE.finditer(wikitext, pos=start):
        nxt = mm
        break
    end = nxt.start() if nxt else len(wikitext)
    return wikitext[start:end]


def _search_translations_en_wiki(
    query: str, *, target_lang: str, timeout: float
) -> Optional[List[WiktEntry]]:
    """Lee `en.wiktionary.org/wiki/<query>` y extrae traducciones a `target_lang`.

    Agrupa por POS de L3 (`===Noun===`, `===Verb===`…). Dentro de cada POS,
    cada bloque `{{trans-top|gloss}} … {{trans-bottom}}` aporta una
    "definición" con formato: `(gloss) palabra1, palabra2`.
    """
    wikitext = _fetch_wikitext("en", query, timeout)
    if not wikitext:
        return None

    en_section = _extract_english_section(wikitext)
    if not en_section:
        return None

    t_tpl_re = re.compile(
        _T_TPL_PREFIX + re.escape(target_lang) + _T_TPL_SUFFIX,
        re.IGNORECASE,
    )

    def harvest_block(body: str) -> List[str]:
        """Devuelve las palabras traducidas (únicas, preservando orden)."""
        words: List[str] = []
        seen = set()
        for wm in t_tpl_re.finditer(body):
            w = _clean_wikitext(wm.group(1))
            if w and w not in seen:
                seen.add(w)
                words.append(w)
        return words

    entries: List[WiktEntry] = []
    # Split por L3 (===POS===). Si no hay L3, tratamos todo como bloque único.
    pos_parts = re.split(
        r"^===\s*([^=]+?)\s*===\s*$", en_section, flags=re.MULTILINE
    )

    def ingest(pos_name: str, body: str) -> None:
        defs: List[str] = []
        for tm in _TRANS_BLOCK_RE.finditer(body):
            gloss = _clean_wikitext(tm.group(1) or "")
            words = harvest_block(tm.group(2) or "")
            if not words:
                continue
            joined = ", ".join(words)
            defs.append(f"({gloss}) {joined}" if gloss else joined)
        if defs:
            entries.append(
                WiktEntry(word=query, part_of_speech=pos_name, definitions=defs)
            )

    if len(pos_parts) <= 1:
        ingest("", en_section)
    else:
        # parts = [preámbulo, h1, c1, h2, c2, …]
        for i in range(1, len(pos_parts), 2):
            name = _clean_wikitext(pos_parts[i])
            content = pos_parts[i + 1] if i + 1 < len(pos_parts) else ""
            ingest(name, content)

    return entries or None


# ---------------------------------------------------------------------------
# Backend action API + wikitext parser (es.wiktionary.org principalmente)


def _fetch_wikitext(host: str, word: str, timeout: float) -> str:
    url = (
        f"https://{host}.wiktionary.org/w/api.php"
        "?action=parse"
        f"&page={urllib.parse.quote(word)}"
        "&prop=wikitext"
        "&format=json"
        "&redirects=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return ""
    parse = data.get("parse") or {}
    wt = parse.get("wikitext") or {}
    return wt.get("*") or ""


# Templates útiles en es.wiktionary
_TPL_PLM = re.compile(r"\{\{\s*plm\s*\|([^}|]+)(?:\|[^}]*)?\}\}", re.IGNORECASE)
_TPL_L = re.compile(r"\{\{\s*l\s*\|\s*\w+\s*\|\s*([^}|]+)(?:\|[^}]*)?\}\}", re.IGNORECASE)
_TPL_ANY = re.compile(r"\{\{[^{}]+\}\}")
_LINK_PIPE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_wikitext(s: str) -> str:
    # Expand templates que contienen texto útil
    s = _TPL_PLM.sub(r"\1", s)  # {{plm|espacio}} → espacio
    s = _TPL_L.sub(r"\1", s)     # {{l|es|espacio}} → espacio
    # Quita cualquier otra plantilla restante (varias pasadas por si anidan)
    prev = None
    while prev != s:
        prev = s
        s = _TPL_ANY.sub("", s)
    # Links wiki
    s = _LINK_PIPE.sub(r"\2", s)
    s = _LINK.sub(r"\1", s)
    # Bold/italic
    s = re.sub(r"'''([^']+)'''", r"\1", s)
    s = re.sub(r"''([^']+)''", r"\1", s)
    # Comentarios y tags HTML
    s = _HTML_COMMENT.sub("", s)
    s = _TAG_RE.sub("", s)
    # Espacios
    s = re.sub(r"\s+", " ", s).strip()
    # Puntuación final redundante
    return s.rstrip(".").strip()


# `== {{lengua|en}} ==` — secciones de L2 en es.wiktionary.
_LENGUA_SECTION_RE = re.compile(
    r"==\s*\{\{\s*lengua\s*\|\s*(\w+)\s*\}\}\s*==",
    re.IGNORECASE,
)

# Definición: `;1: texto`, `;1a: texto`, `; 2 : texto`…
_DEF_LINE_RE = re.compile(r"^\s*;\s*([0-9]+[a-z]?)\s*:\s*(.+?)\s*$", re.MULTILINE)


def _extract_defs(section_text: str) -> List[str]:
    out: List[str] = []
    for m in _DEF_LINE_RE.finditer(section_text):
        raw = m.group(2).splitlines()[0]
        cleaned = _clean_wikitext(raw)
        if cleaned:
            out.append(cleaned)
    return out


def _search_parse_wiki(
    query: str,
    *,
    src_lang: str,
    wiki_host: str,
    timeout: float,
) -> Optional[List[WiktEntry]]:
    wikitext = _fetch_wikitext(wiki_host, query, timeout)
    if not wikitext:
        return None

    # Localizar la sección `{{lengua|<src>}}`
    matches = list(_LENGUA_SECTION_RE.finditer(wikitext))
    if not matches:
        return None

    section_text = ""
    for i, m in enumerate(matches):
        if m.group(1).lower() == src_lang.lower():
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
            section_text = wikitext[start:end]
            break
    if not section_text:
        return None

    # Divide por L3 (`=== Sustantivo ===`, `=== Verbo ===`, …)
    parts = re.split(r"^===\s*([^=]+?)\s*===\s*$", section_text, flags=re.MULTILINE)
    entries: List[WiktEntry] = []

    if len(parts) <= 1:
        defs = _extract_defs(section_text)
        if defs:
            entries.append(WiktEntry(word=query, part_of_speech="", definitions=defs))
    else:
        # parts = [preámbulo, h1, c1, h2, c2, …]
        for i in range(1, len(parts), 2):
            pos = _clean_wikitext(parts[i])
            content = parts[i + 1] if i + 1 < len(parts) else ""
            defs = _extract_defs(content)
            if defs:
                entries.append(
                    WiktEntry(word=query, part_of_speech=pos, definitions=defs)
                )

    return entries or None


# ---------------------------------------------------------------------------
# Formateo de salida


def format_entries(
    entries: List[WiktEntry],
    *,
    max_senses: int = 3,
    include_reading: bool = True,  # compat con la firma de jisho
    include_parts_of_speech: bool = True,
    suppress_gloss: bool = False,  # compat — en Wiktionary nunca aplica
) -> str:
    """HTML limpio apto para insertar en un campo de Anki."""
    if not entries:
        return ""

    parts: List[str] = []
    first = entries[0]
    if first.word:
        parts.append(f"<b>{_esc(first.word)}</b>")

    remaining = max_senses if max_senses > 0 else -1
    for entry in entries:
        if remaining == 0:
            break
        items: List[str] = []
        pos = entry.part_of_speech
        for dfn in entry.definitions:
            if remaining == 0:
                break
            line = _esc(dfn)
            if include_parts_of_speech and pos:
                line = (
                    f"<span style='color:#888;font-size:0.9em'>[{_esc(pos)}]</span> "
                    + line
                )
            items.append(f"<li>{line}</li>")
            if remaining > 0:
                remaining -= 1
        if items:
            parts.append(
                "<ol style='margin:4px 0 0 18px;padding:0'>" + "".join(items) + "</ol>"
            )

    return "<div>" + "".join(parts) + "</div>"


def entries_to_choices(entries: List[WiktEntry]) -> List[dict]:
    """Aplana las entradas en opciones para el picker, una por definición."""
    choices: List[dict] = []
    if not entries:
        return choices

    for entry in entries:
        pos = entry.part_of_speech or ""
        for dfn in entry.definitions:
            if not dfn:
                continue
            html_parts: List[str] = []
            if pos:
                html_parts.append(
                    f"<span style='color:#888;font-size:0.9em'>[{_esc(pos)}]</span> "
                )
            html_parts.append(_esc(dfn))
            html = "<li>" + "".join(html_parts) + "</li>"

            choices.append(
                {
                    "source": "wiktionary",
                    "word": entry.word,
                    "reading": "",
                    "pos": pos,
                    "text": dfn,
                    "html": html,
                }
            )
    return choices


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
