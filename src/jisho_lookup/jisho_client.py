# -*- coding: utf-8 -*-
"""Cliente HTTP para la API no oficial de Jisho (jisho.org/api/v1/search/words).

La API es pública y gratuita; sin embargo puede caer, rate-limitar o cambiar.
Por eso toda llamada devuelve `None` en caso de error y el `lookup.py` hace
fallback a los diccionarios locales Yomichan/Yomitan.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import List, Optional


JISHO_ENDPOINT = "https://jisho.org/api/v1/search/words"


class JishoEntry:
    __slots__ = ("word", "reading", "senses")

    def __init__(self, word: str, reading: str, senses: List[dict]):
        self.word = word
        self.reading = reading
        self.senses = senses


def _pick_japanese(data: dict) -> tuple[str, str]:
    japanese = data.get("japanese") or []
    if not japanese:
        return "", ""
    first = japanese[0]
    word = first.get("word") or first.get("reading") or ""
    reading = first.get("reading") or ""
    return word, reading


def search(query: str, timeout: float = 6.0) -> Optional[List[JishoEntry]]:
    """Consulta Jisho. Devuelve la lista de entradas o `None` si hubo error."""
    query = (query or "").strip()
    if not query:
        return None
    try:
        url = JISHO_ENDPOINT + "?" + urllib.parse.urlencode({"keyword": query})
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AnkiJishoLookup/1.0 (+https://github.com/)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception:
        return None

    if payload.get("meta", {}).get("status") != 200:
        return None

    out: List[JishoEntry] = []
    for item in payload.get("data", []) or []:
        word, reading = _pick_japanese(item)
        senses = item.get("senses") or []
        out.append(JishoEntry(word=word, reading=reading, senses=senses))
    return out


def format_entries(
    entries: List[JishoEntry],
    *,
    max_senses: int = 3,
    include_reading: bool = True,
    include_parts_of_speech: bool = True,
) -> str:
    """Convierte las entradas en HTML limpio adecuado para un campo de Anki."""
    if not entries:
        return ""

    parts: List[str] = []
    top = entries[0]

    header_bits: List[str] = []
    if top.word:
        header_bits.append(f"<b>{_esc(top.word)}</b>")
    if include_reading and top.reading and top.reading != top.word:
        header_bits.append(f"【{_esc(top.reading)}】")
    if header_bits:
        parts.append("".join(header_bits))

    senses = top.senses[: max_senses if max_senses > 0 else len(top.senses)]
    items: List[str] = []
    for idx, sense in enumerate(senses, 1):
        definitions = sense.get("english_definitions") or []
        if not definitions:
            continue
        line = ", ".join(_esc(d) for d in definitions)
        if include_parts_of_speech:
            pos = sense.get("parts_of_speech") or []
            if pos:
                line = (
                    f"<span style='color:#888;font-size:0.9em'>[{_esc(', '.join(pos))}]</span> "
                    + line
                )
        items.append(f"<li>{line}</li>")

    if items:
        parts.append("<ol style='margin:4px 0 0 18px;padding:0'>" + "".join(items) + "</ol>")

    return "<div>" + "".join(parts) + "</div>"


def entries_to_choices(entries: List[JishoEntry]) -> List[dict]:
    """Aplana las entradas en una lista de "opciones" para el picker.

    Itera **todas** las entradas devueltas por Jisho (no sólo la primera).
    Esto es clave para `en→ja`: Jisho devuelve una entrada por cada palabra
    japonesa candidata (空き, スペース, 場所…), cada una con sus acepciones en
    inglés. Mostrarlas todas convierte el picker en una lista de candidatos
    de traducción, no en una lista de matices de una sola palabra.

    Cada opción representa una acepción individual de una entrada:
        {
          "source":  "jisho",
          "word":    "食べる",
          "reading": "たべる",
          "pos":     "Ichidan verb, Transitive verb",
          "text":    "to eat, to consume",     # texto mostrado al usuario
          "html":    "<li>...</li>"            # fragmento listo para insertar
        }
    """
    choices: List[dict] = []
    if not entries:
        return choices

    for entry in entries:
        for sense in entry.senses or []:
            defs = sense.get("english_definitions") or []
            if not defs:
                continue
            pos_list = sense.get("parts_of_speech") or []
            pos = ", ".join(pos_list)
            text = ", ".join(defs)

            html_parts: List[str] = []
            if pos:
                html_parts.append(
                    f"<span style='color:#888;font-size:0.9em'>[{_esc(pos)}]</span> "
                )
            html_parts.append(_esc(text))
            html = "<li>" + "".join(html_parts) + "</li>"

            choices.append(
                {
                    "source": "jisho",
                    "word": entry.word,
                    "reading": entry.reading,
                    "pos": pos,
                    "text": text,
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
