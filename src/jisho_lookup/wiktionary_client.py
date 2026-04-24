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
from typing import List, Optional, Tuple


_TAG_RE = re.compile(r"<[^>]+>")
_UA = "AnkiJishoLookup/1.2 (+https://github.com/Adrian-CS/dictSearchWhileReview)"


class WiktEntry:
    """Una entrada de diccionario.

    Hay dos "formas" posibles según el backend que la produjo:

    * **Definiciones** (REST en.wiktionary o parser `{{lengua|…}}`): cada
      `definition` es una glosa completa en el idioma target. `gloss` y
      `translation_words` están vacíos. Ejemplo ja→es sobre `空`:
      `definitions = ["Cielo.", "Vacío."]`.

    * **Traducciones** (Translations de en.wiktionary o Traducciones de
      es.wiktionary): `gloss` es la glosa del bloque (en el idioma source),
      `translation_words` son las palabras capturadas en el idioma target,
      y `definitions` se rellena por retro-compatibilidad con la
      representación legacy `"(gloss) palabra1, palabra2"`. Ejemplo es→ja
      sobre `silla`: `gloss="[1] mueble para sentarse, con respaldo"`,
      `translation_words=["椅子"]`.

    Este desdoblamiento permite que el renderizador oculte la glosa
    cuando el par target→source la haría redundante (p. ej. en→ja,
    es→ja: la glosa está en el idioma que el usuario ya lee).
    """

    __slots__ = ("word", "part_of_speech", "definitions", "gloss", "translation_words")

    def __init__(
        self,
        word: str,
        part_of_speech: str,
        definitions: List[str],
        *,
        gloss: str = "",
        translation_words: Optional[List[str]] = None,
    ):
        self.word = word
        self.part_of_speech = part_of_speech
        self.definitions = definitions
        self.gloss = gloss
        self.translation_words = list(translation_words or [])

    @property
    def is_translation(self) -> bool:
        return bool(self.translation_words)


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
    """Consulta Wiktionary. Elige el backend apropiado según el par.

    Rutas soportadas:

    * `{src}→en`   (es, ko, ja…): REST `page/definition/` en en.wiktionary.
      Sólo hay REST en en.wiktionary y devuelve las glosas inglesas de las
      palabras de cualquier lengua si tienen entrada allí.
    * `en→{tgt}`   : parser de Translations en en.wiktionary (funciona para
      es, ko, ja… usando `{{t|<tgt>|…}}`).
    * `ja→es`      : parser genérico `{{lengua|ja}}` en es.wiktionary.
    * `es→ja`      : parser de Traducciones en es.wiktionary, extrayendo
      `{{t|ja|…}}` / `{{trad|ja|…}}` dentro de los bloques
      `{{trad-arriba}}…{{trad-abajo}}`.
    * Genérico      : parser `{{lengua|<src>}}` en `{tgt}.wiktionary.org`.
    """
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
    if src == "es" and tgt == "ja":
        # es→ja: leemos es.wiktionary y extraemos las Traducciones de la
        # sección `{{lengua|es}}`. Fallback genérico en ja.wiktionary
        # por si el término sólo existe en el wiki japonés.
        result = _search_translations_es_wiki(query, target_lang=tgt, timeout=timeout)
        if result:
            return result
        return _search_parse_wiki(query, src_lang=src, wiki_host=tgt, timeout=timeout)
    # ja→es y otros pares "no-inglés" → parser genérico {{lengua|src}}
    # en {tgt}.wiktionary (p. ej. es.wiktionary para ja→es).
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
# Aceptamos parámetros con nombre delante de la palabra: `1=espacio`,
# `t1=espacio`, etc. En `_strip_param_prefix` también se hace una segunda
# pasada por si el regex los dejó pegados.
_T_TPL_SUFFIX = (
    r"\s*\|\s*(?:[a-z]*\d*\s*=\s*)?"
    r"([^}|]+)"
    r"(?:\|[^}]*)?\s*\}\}"
)


# Plantillas de traducción en es.wiktionary:
#   {{t|ja|椅子}}                — traducción simple
#   {{t+|ja|椅子}}               — con link al wiki del target
#   {{trad|ja|椅子}}             — forma histórica; sigue viva en muchos artículos
#   {{trad|ja|1=椅子|tr=isu}}    — con parámetros con nombre
#   {{trad|ja|t1=椅子}}          — algunas plantillas usan `t1=`/`tr1=`
_TRAD_TPL_PREFIX_ES = r"\{\{\s*(?:t[+\-]?|trad)\s*\|\s*"
_TRAD_TPL_SUFFIX_ES = _T_TPL_SUFFIX


# Prefijos de parámetros con nombre que a veces escapan al regex: `t1=`,
# `t2=`, `1=`, `tr=`, `tr1=`, etc. Se aplican como segunda defensa tras
# `_clean_wikitext` por si el captured group los trae pegados.
_PARAM_PREFIX_RE = re.compile(r"^\s*[A-Za-z]*\d*\s*=\s*")


def _strip_param_prefix(s: str) -> str:
    """Elimina un prefijo `<letras><dígitos>=` si quedó pegado al valor.

    Por ejemplo `t1=椅子` → `椅子`, `1=espacio` → `espacio`, `tr=isu` →
    `isu` (y ese último no queremos; se cuela en casos raros, pero al
    ser transliteración romaji, el filtro posterior la rechaza como
    candidato al no pertenecer al script esperado).
    """
    return _PARAM_PREFIX_RE.sub("", s).strip()


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

    Agrupa por POS de L3 (`===Noun===`, `===Verb===`…). Cada bloque
    `{{trans-top|gloss}} … {{trans-bottom}}` aporta una `WiktEntry` por
    cada palabra traducida, donde `word` es la palabra en `target_lang`,
    `gloss` es la glosa inglesa del bloque y `translation_words` contiene
    la propia palabra (necesario para `is_translation → True`).

    `definitions` se rellena con `"(gloss) palabra"` por retro-compat con
    el formato legacy (útil para el path `format_entries` cuando la glosa
    *sí* debe mostrarse, p. ej. `en→es`).
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

    entries: List[WiktEntry] = []
    seen_global: set = set()

    def push(word: str, pos: str, gloss: str) -> None:
        # Dedup por (pos, gloss, word) — el mismo par puede repetirse en
        # varios bloques (p. ej. {{trans-see}} apuntando a lo mismo).
        key = (pos, gloss, word)
        if not word or key in seen_global:
            return
        seen_global.add(key)
        defs = [f"({gloss}) {word}"] if gloss else [word]
        entries.append(
            WiktEntry(
                word=word,
                part_of_speech=pos,
                definitions=defs,
                gloss=gloss,
                translation_words=[word],
            )
        )

    def ingest(pos_name: str, body: str) -> None:
        for tm in _TRANS_BLOCK_RE.finditer(body):
            gloss = _strip_param_prefix(_clean_wikitext(tm.group(1) or ""))
            for w in _harvest_translations(tm.group(2) or "", t_tpl_re):
                push(w, pos_name, gloss)

    # Split por L3 (===POS===). Si no hay L3, tratamos todo como bloque único.
    pos_parts = re.split(
        r"^===\s*([^=]+?)\s*===\s*$", en_section, flags=re.MULTILINE
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
# Backend para es→{otro}: lee Traducciones en es.wiktionary


# {{trad-arriba|gloss}} … {{trad-abajo}}. A veces el gloss se pasa con
# `|leng=<src>`; lo ignoramos y nos quedamos con el primer parámetro.
_TRAD_BLOCK_RE = re.compile(
    r"\{\{\s*trad-arriba(?:\s*\|([^}]*))?\s*\}\}(.*?)\{\{\s*trad-abajo\s*\}\}",
    re.DOTALL | re.IGNORECASE,
)
# `=== {{lengua|es}} ===` en es.wiktionary marca la sección de la palabra
# en español. Hay variantes `== {{lengua|es}} ==` también.
_LENGUA_HEADING_ANY_RE = re.compile(
    r"^(={2,4})\s*\{\{\s*lengua\s*\|\s*(\w+)\s*\}\}\s*\1\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Heading genérico de wikitext: `=== X ===`, `==== X ====`, etc.
_HEADING_ANY_RE = re.compile(r"^(={3,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)

# Secciones que en es.wiktionary suelen estar entre la sección `{{lengua|es}}`
# y los verdaderos POS, y que NO deberían figurar como POS en la salida.
# p. ej. `=== Etimología 1 ===`, `=== Pronunciación ===`.
_SKIP_HEADING_RE = re.compile(
    r"^(?:"
    r"etimolog[ií]a(?:\s*\d+)?|"
    r"pronunciaci[oó]n|"
    r"traducciones|"
    r"referencias|"
    r"locuciones|"
    r"v[eé]ase\s+tambi[eé]n|"
    r"conjugaci[oó]n|"
    r"informaci[oó]n\s+adicional|"
    r"sin[oó]nimos|"
    r"ant[oó]nimos|"
    r"notas|"
    r"uso(?:s)?|"
    r"ortograf[ií]a"
    r")$",
    re.IGNORECASE,
)


def _extract_section_by_lengua(
    wikitext: str, lang_code: str
) -> str:
    """Extrae el contenido de la sección `{{lengua|<lang_code>}}`.

    Devuelve el texto desde el final del heading hasta la siguiente
    sección `{{lengua|…}}` del mismo nivel (o fin del texto).
    """
    target = lang_code.lower()
    hits = list(_LENGUA_HEADING_ANY_RE.finditer(wikitext))
    for i, m in enumerate(hits):
        if m.group(2).lower() != target:
            continue
        start = m.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(wikitext)
        return wikitext[start:end]
    return ""


def _walk_current_pos(section: str):
    """Itera `(current_pos, body_slice)` por cada trozo entre headings.

    `current_pos` es el nombre del heading más reciente que NO está en la
    lista `_SKIP_HEADING_RE`. Así `=== Etimología 1 ===` se salta y el
    siguiente `==== Sustantivo femenino ====` se recuerda como POS real.
    """
    current_pos = ""
    cursor = 0
    for m in _HEADING_ANY_RE.finditer(section):
        if cursor < m.start():
            yield current_pos, section[cursor:m.start()]
        heading = _clean_wikitext(m.group(2))
        if heading and not _SKIP_HEADING_RE.match(heading):
            current_pos = heading
        cursor = m.end()
    if cursor < len(section):
        yield current_pos, section[cursor:]


def _harvest_translations(body: str, tpl_re: "re.Pattern[str]") -> List[str]:
    """Aplica `tpl_re` sobre `body` y devuelve los candidatos únicos,
    en orden de aparición. Aplica `_clean_wikitext` + `_strip_param_prefix`
    a cada captura para quitar restos de plantillas/links/parámetros
    con nombre (`t1=`, `1=`, etc.).
    """
    words: List[str] = []
    seen = set()
    for wm in tpl_re.finditer(body):
        w = _clean_wikitext(wm.group(1))
        w = _strip_param_prefix(w)
        if w and w not in seen:
            seen.add(w)
            words.append(w)
    return words


def _search_translations_es_wiki(
    query: str, *, target_lang: str, timeout: float
) -> Optional[List[WiktEntry]]:
    """Para pares `es→X` (p. ej. `es→ja`): busca en es.wiktionary, localiza
    la sección `{{lengua|es}}` y extrae los `{{t|<target_lang>|…}}`
    dentro de los bloques `{{trad-arriba}}…{{trad-abajo}}`.

    El camino recorre toda la lengua-sección respetando la estructura
    real: hay artículos con `=== Etimología N ===` como L3 y el POS
    colgando de L4; si dividíamos sólo por L3 acabaríamos etiquetando
    los bloques como "Etimología 1". `_walk_current_pos` mantiene el
    POS correcto a la vista mientras itera.

    Cada bloque de traducciones produce una `WiktEntry` por palabra
    traducida, con `word=traducción`, `gloss=<glosa en español>` y
    `translation_words=[traducción]`. `definitions` se rellena como
    `"(gloss) traducción"` sólo para la ruta legacy (format_entries).
    """
    wikitext = _fetch_wikitext("es", query, timeout)
    if not wikitext:
        return None

    section = _extract_section_by_lengua(wikitext, "es")
    if not section:
        return None

    t_tpl_re = re.compile(
        _TRAD_TPL_PREFIX_ES + re.escape(target_lang) + _TRAD_TPL_SUFFIX_ES,
        re.IGNORECASE,
    )

    entries: List[WiktEntry] = []

    def push(word: str, pos: str, gloss: str) -> None:
        if not word:
            return
        defs = [f"({gloss}) {word}"] if gloss else [word]
        entries.append(
            WiktEntry(
                word=word,
                part_of_speech=pos,
                definitions=defs,
                gloss=gloss,
                translation_words=[word],
            )
        )

    for pos_name, body in _walk_current_pos(section):
        # 1) Bloques `{{trad-arriba}}…{{trad-abajo}}`.
        matched_spans: List[Tuple[int, int]] = []
        for tm in _TRAD_BLOCK_RE.finditer(body):
            gloss = _strip_param_prefix(_clean_wikitext(tm.group(1) or ""))
            # Algunos autores usan `{{trad-arriba|leng=es|texto}}`;
            # tras `_clean_wikitext` podría haber quedado sólo "es".
            # Si la glosa parece un código de idioma aislado, la
            # descartamos para que no aparezca como texto falso.
            if len(gloss) <= 3 and gloss.isalpha() and gloss.islower():
                gloss = ""
            words = _harvest_translations(tm.group(2) or "", t_tpl_re)
            for w in words:
                push(w, pos_name, gloss)
            matched_spans.append((tm.start(), tm.end()))

        # 2) Traducciones sueltas fuera de trad-arriba/abajo (artículos
        # donde alguien omitió el bloque). Buscamos en lo que queda tras
        # quitar los spans ya consumidos para no duplicar.
        if matched_spans:
            cursor = 0
            remaining_parts: List[str] = []
            for a, b in matched_spans:
                remaining_parts.append(body[cursor:a])
                cursor = b
            remaining_parts.append(body[cursor:])
            remaining = "\n".join(remaining_parts)
        else:
            remaining = body
        for w in _harvest_translations(remaining, t_tpl_re):
            push(w, pos_name, "")

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
    suppress_gloss: bool = False,
) -> str:
    """HTML limpio apto para insertar en un campo de Anki.

    Dos modos de render según el contenido:

    * **Modo definiciones** (REST / parser genérico): una cabecera con
      la palabra y luego una `<ol>` con todas las glosas por POS.
    * **Modo traducciones** (cada entry es una palabra en el idioma
      target con su `gloss` en el source): lista plana de
      `palabra (glosa) [POS]`. Con `suppress_gloss=True` se omite la
      glosa — usado por `format_picked_choices` para pares target→ja,
      pero aquí se expone por si alguna ruta quick-insert lo necesita.
    """
    if not entries:
        return ""

    # Modo traducciones si al menos una entrada es is_translation.
    if any(e.is_translation for e in entries):
        items: List[str] = []
        remaining = max_senses if max_senses > 0 else -1
        for entry in entries:
            if remaining == 0:
                break
            bits: List[str] = []
            if include_parts_of_speech and entry.part_of_speech:
                bits.append(
                    f"<span style='color:#888;font-size:0.9em'>"
                    f"[{_esc(entry.part_of_speech)}]</span>"
                )
            if entry.word:
                bits.append(f"<b>{_esc(entry.word)}</b>")
            if not suppress_gloss and entry.gloss:
                bits.append(f"({_esc(entry.gloss)})")
            if bits:
                items.append(f"<li>{' '.join(bits)}</li>")
                if remaining > 0:
                    remaining -= 1
        if not items:
            return ""
        return (
            "<div><ol style='margin:4px 0 0 18px;padding:0'>"
            + "".join(items)
            + "</ol></div>"
        )

    # Modo definiciones clásico.
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
    """Aplana las entradas en opciones para el picker.

    En **modo traducciones** (entry con `translation_words`), cada entry
    produce **una** opción cuyo `word` es la palabra traducida y cuyo
    `text` es la glosa en el idioma source. Esto permite que
    `format_picked_choices` oculte la glosa selectivamente con `hide_text`
    cuando el target es ja (en→ja, es→ja).

    En **modo definiciones**, una opción por cada string de `definitions`.
    """
    choices: List[dict] = []
    if not entries:
        return choices

    for entry in entries:
        pos = entry.part_of_speech or ""
        if entry.is_translation:
            html_parts: List[str] = []
            if pos:
                html_parts.append(
                    f"<span style='color:#888;font-size:0.9em'>"
                    f"[{_esc(pos)}]</span> "
                )
            if entry.word:
                html_parts.append(f"<b>{_esc(entry.word)}</b>")
            if entry.gloss:
                html_parts.append(f" ({_esc(entry.gloss)})")
            html = "<li>" + "".join(html_parts) + "</li>"
            choices.append(
                {
                    "source": "wiktionary",
                    "word": entry.word,
                    "reading": "",
                    "pos": pos,
                    "text": entry.gloss,
                    "html": html,
                }
            )
            continue

        for dfn in entry.definitions:
            if not dfn:
                continue
            html_parts = []
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
