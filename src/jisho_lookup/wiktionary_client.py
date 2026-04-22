# -*- coding: utf-8 -*-
"""Cliente HTTP para la API REST de Wiktionary.

Usamos el endpoint público:
    https://{host}.wiktionary.org/api/rest_v1/page/definition/{word}

Donde `host` es el código del idioma del **wiki** (donde se aloja la página)
y la respuesta viene agrupada por el **idioma de la palabra** (también código
ISO). Por ejemplo, para obtener la definición en inglés de la palabra
española "casa" consultamos `en.wiktionary.org/.../casa` y leemos la sección
`"es"` (el idioma de la palabra). Para la definición en español de la
palabra inglesa "house" consultamos `es.wiktionary.org/.../house` y leemos
la sección `"en"`.

La API es pública pero puede fallar o rate-limitar; devolvemos `None` en
caso de error y el orquestador cae a diccionarios locales.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import List, Optional


_TAG_RE = re.compile(r"<[^>]+>")


class WiktEntry:
    __slots__ = ("word", "part_of_speech", "definitions", "examples_per_def")

    def __init__(
        self,
        word: str,
        part_of_speech: str,
        definitions: List[str],
        examples_per_def: List[List[str]] | None = None,
    ):
        self.word = word
        self.part_of_speech = part_of_speech
        self.definitions = definitions
        self.examples_per_def = examples_per_def or [[] for _ in definitions]


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return _TAG_RE.sub("", s).strip()


def _host_for_pair(src: str, tgt: str) -> str:
    """Wiki donde buscar. Elegimos el wiki del idioma *destino* (tgt) porque
    su sección sobre la palabra suele incluir la definición en ese idioma.

    En Wiktionary todos los wikis incluyen palabras de cualquier idioma con
    definiciones en su idioma nativo, así que:
      es→en ⇒ en.wiktionary (def. en inglés de palabras en español)
      en→es ⇒ es.wiktionary (def. en español de palabras en inglés)
      en→en ⇒ en.wiktionary
      es→es ⇒ es.wiktionary
    """
    return tgt or "en"


def search(
    query: str,
    src: str,
    tgt: str,
    *,
    timeout: float = 6.0,
) -> Optional[List[WiktEntry]]:
    """Consulta Wiktionary. Devuelve la lista de entradas o None si falla."""
    query = (query or "").strip()
    if not query:
        return None

    host = _host_for_pair(src, tgt)
    url = (
        f"https://{host}.wiktionary.org/api/rest_v1/page/definition/"
        + urllib.parse.quote(query, safe="")
    )
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AnkiJishoLookup/1.2 (+https://github.com/)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    # `payload` es { "<lang_code>": [ { partOfSpeech, language, definitions: [...] }, ... ] }
    # Queremos la sección correspondiente al idioma *origen* (src), que es
    # el idioma de la propia palabra.
    section = payload.get(src)
    if not section and src == "en":
        # algunas entradas vienen agrupadas bajo "other"
        section = payload.get("other")
    if not isinstance(section, list):
        return None

    out: List[WiktEntry] = []
    for block in section:
        if not isinstance(block, dict):
            continue
        pos = _strip_html(block.get("partOfSpeech") or "")
        defs_raw = block.get("definitions") or []
        defs: List[str] = []
        examples: List[List[str]] = []
        for d in defs_raw:
            if not isinstance(d, dict):
                continue
            text = _strip_html(d.get("definition") or "")
            if not text:
                continue
            defs.append(text)
            ex_list = []
            for ex in d.get("examples") or []:
                ex_clean = _strip_html(ex)
                if ex_clean:
                    ex_list.append(ex_clean)
            examples.append(ex_list)
        if defs:
            out.append(
                WiktEntry(
                    word=query,
                    part_of_speech=pos,
                    definitions=defs,
                    examples_per_def=examples,
                )
            )
    return out or None


def format_entries(
    entries: List[WiktEntry],
    *,
    max_senses: int = 3,
    include_reading: bool = True,  # compat con la firma de jisho
    include_parts_of_speech: bool = True,
) -> str:
    """Convierte las entradas en HTML limpio apto para un campo de Anki."""
    if not entries:
        return ""

    # Tomamos todos los bloques (cada uno es un part-of-speech) y los
    # combinamos. Limitamos el total de acepciones a `max_senses` si >0.
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
        for idx, dfn in enumerate(entry.definitions):
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
    """Aplana las entradas en opciones para el picker.

    Cada opción representa una sola definición (una línea):
        {
          "source":  "wiktionary",
          "word":    "casa",
          "reading": "",
          "pos":     "Noun",
          "text":    "A building for human habitation",
          "html":    "<li>...</li>"
        }
    """
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
