# -*- coding: utf-8 -*-
"""Internacionalización / Internationalization / 国際化.

Detecta el idioma de la UI de Anki (`anki.lang.current_lang`, con
fallbacks razonables) y devuelve la traducción apropiada. Soporta
inglés, español y japonés; cualquier otro idioma cae a inglés.

Uso:

    from .i18n import tr
    label = tr("common.ok")
    msg   = tr("reviewer.success", query="空", field="Back", origin="Jisho")

Los strings se agrupan por claves con puntos (`categoría.nombre`). Para
añadir un nuevo string, edita `_STRINGS` más abajo.

El nombre propio "Jisho Lookup" se mantiene en los tres idiomas porque
es una marca; sólo se traducen subtítulos y descripciones.
"""

from __future__ import annotations

from typing import Dict


_SUPPORTED = ("en", "es", "ja")
_LANG_CACHE: str = ""


def _detect_lang() -> str:
    """Devuelve 'en' | 'es' | 'ja' según la UI de Anki.

    Anki expone el idioma de varias formas según la versión:
      * `anki.lang.current_lang()` — 2.1.45+
      * `anki.lang.currentLang` — versiones antiguas
      * `mw.pm.meta["defaultLang"]` — fallback vía profile manager
    """
    global _LANG_CACHE
    if _LANG_CACHE:
        return _LANG_CACHE
    raw = ""
    try:  # 2.1.45+
        from anki.lang import current_lang  # type: ignore
        raw = str(current_lang() or "")
    except Exception:
        try:
            from anki.lang import currentLang  # type: ignore
            raw = str(currentLang or "")
        except Exception:
            try:
                from aqt import mw  # type: ignore
                meta = getattr(getattr(mw, "pm", None), "meta", None) or {}
                raw = str(meta.get("defaultLang") or "")
            except Exception:
                raw = ""
    # Normaliza: 'es_ES', 'es-MX', 'ja_JP' -> 'es' / 'ja'
    base = raw.replace("-", "_").split("_")[0].lower().strip()
    if base not in _SUPPORTED:
        base = "en"
    _LANG_CACHE = base
    return base


def current_lang() -> str:
    """Idioma activo (cacheado)."""
    return _detect_lang()


def reset_lang_cache() -> None:
    """Fuerza la re-detección en el próximo `tr()`. Útil en tests."""
    global _LANG_CACHE
    _LANG_CACHE = ""


def tr(key: str, **kwargs: object) -> str:
    """Devuelve la traducción de `key` en el idioma activo.

    Si la clave no existe se devuelve la propia clave (útil para
    detectar strings sin traducir durante desarrollo). Si falta la
    traducción en el idioma activo pero existe en inglés, se usa
    inglés como fallback.
    """
    lang = _detect_lang()
    row = _STRINGS.get(key)
    if row is None:
        return key
    text = row.get(lang) or row.get("en") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


# ---------------------------------------------------------------------------
# Catálogo de strings
#
# Claves organizadas por módulo / categoría. Cada entrada lleva sus tres
# traducciones. Si alguna falta en su momento se mostrará el inglés.


_STRINGS: Dict[str, Dict[str, str]] = {
    # ------------------------------------------------------------- comunes
    "common.ok": {"en": "OK", "es": "OK", "ja": "OK"},
    "common.cancel": {"en": "Cancel", "es": "Cancelar", "ja": "キャンセル"},
    "common.save": {"en": "Save", "es": "Guardar", "ja": "保存"},
    "common.addon_name": {
        "en": "Jisho Lookup",
        "es": "Jisho Lookup",
        "ja": "Jisho Lookup",
    },

    # ------------------------------------------------------------- menú
    "menu.run_now": {
        "en": "Search selection now (quick)",
        "es": "Buscar selección ahora (rápido)",
        "ja": "選択した語をいま検索(クイック)",
    },
    "menu.pick_now": {
        "en": "Pick definition (popup)…",
        "es": "Elegir definición (popup)…",
        "ja": "定義を選択(ポップアップ)…",
    },
    "menu.config": {
        "en": "Configuration…",
        "es": "Configuración…",
        "ja": "設定…",
    },

    # ------------------------------------------------------------- pares
    "pair.ja_en": {
        "en": "Japanese → English",
        "es": "Japonés → Inglés",
        "ja": "日本語 → 英語",
    },
    "pair.en_ja": {
        "en": "English → Japanese",
        "es": "Inglés → Japonés",
        "ja": "英語 → 日本語",
    },
    "pair.es_en": {
        "en": "Spanish → English",
        "es": "Español → Inglés",
        "ja": "スペイン語 → 英語",
    },
    "pair.en_es": {
        "en": "English → Spanish",
        "es": "Inglés → Español",
        "ja": "英語 → スペイン語",
    },

    # ------------------------------------------------------------- picker
    "picker.window_title": {
        "en": "Jisho Lookup — Pick definition",
        "es": "Jisho Lookup — Elegir definición",
        "ja": "Jisho Lookup — 定義を選択",
    },
    "picker.field": {"en": "Field:", "es": "Campo:", "ja": "フィールド:"},
    "picker.overwrite": {
        "en": "Replace", "es": "Sustituir", "ja": "置き換え"
    },
    "picker.append": {"en": "Append", "es": "Añadir", "ja": "追記"},
    "picker.pos": {"en": "Grammar", "es": "Gramática", "ja": "品詞"},
    "picker.pos_tooltip": {
        "en": (
            "Include part-of-speech tags ([Noun], [Verb]…) both in the "
            "list and in the inserted definition."
        ),
        "es": (
            "Incluir anotaciones de categoría gramatical "
            "([Noun], [Verb]…) tanto en la lista como en la definición "
            "insertada."
        ),
        "ja": (
            "品詞タグ([Noun]、[Verb]など)を一覧と挿入される定義の両方に含める。"
        ),
    },
    "picker.language": {"en": "Language:", "es": "Idioma:", "ja": "言語:"},
    "picker.hint_multi": {
        "en": (
            "Pick one or several senses (Ctrl/Shift+click). "
            "Enter to insert, Esc to cancel."
        ),
        "es": (
            "Selecciona una o varias acepciones (Ctrl/Shift+clic). "
            "Enter para insertar, Esc para cancelar."
        ),
        "ja": (
            "意味を一つ以上選択(Ctrl/Shift+クリック)。"
            "Enterで挿入、Escでキャンセル。"
        ),
    },
    "picker.hint_single": {
        "en": "Pick a sense. Enter to insert, Esc to cancel.",
        "es": "Selecciona una acepción. Enter para insertar, Esc para cancelar.",
        "ja": "意味を一つ選択。Enterで挿入、Escでキャンセル。",
    },
    "picker.loading_pair": {
        "en": "Searching in {pair}…",
        "es": "Buscando en {pair}…",
        "ja": "{pair} で検索中…",
    },
    "picker.loading": {
        "en": "Loading definitions…",
        "es": "Cargando definiciones…",
        "ja": "定義を読み込み中…",
    },
    "picker.no_results": {
        "en": "(no results)",
        "es": "(sin resultados)",
        "ja": "(該当なし)",
    },
    "picker.insert": {"en": "Insert", "es": "Insertar", "ja": "挿入"},

    # ------------------------------------------------------------- config
    "config.window_title": {
        "en": "Jisho Lookup — Configuration",
        "es": "Jisho Lookup — Configuración",
        "ja": "Jisho Lookup — 設定",
    },
    "config.shortcut": {
        "en": "Quick shortcut:",
        "es": "Atajo rápido:",
        "ja": "クイックショートカット:",
    },
    "config.picker_shortcut": {
        "en": "Picker shortcut:",
        "es": "Atajo picker:",
        "ja": "選択ショートカット:",
    },
    "config.strategy": {
        "en": "Strategy:", "es": "Estrategia:", "ja": "方式:"
    },
    "config.strategy.online_then_local": {
        "en": "Online → Local (fallback)",
        "es": "Online → Local (fallback)",
        "ja": "オンライン→ローカル(フォールバック)",
    },
    "config.strategy.local_only": {
        "en": "Local only", "es": "Solo local", "ja": "ローカルのみ"
    },
    "config.strategy.online_only": {
        "en": "Online only", "es": "Solo online", "ja": "オンラインのみ"
    },
    "config.language_pair": {
        "en": "Default language pair:",
        "es": "Par de idioma (por defecto):",
        "ja": "既定の言語ペア:",
    },
    "config.auto_fallback": {
        "en": (
            "Auto-detect language if the default pair returns nothing "
            "(quick shortcut only)"
        ),
        "es": (
            "Auto-detectar idioma si el par por defecto no da resultados "
            "(sólo en el atajo rápido)"
        ),
        "ja": (
            "既定のペアで見つからない場合は言語を自動検出"
            "(クイックショートカットのみ)"
        ),
    },
    "config.include_reading": {
        "en": "Include reading",
        "es": "Incluir lectura",
        "ja": "読み仮名を含める",
    },
    "config.include_pos": {
        "en": "Include grammar tags",
        "es": "Incluir categorías gramaticales",
        "ja": "品詞タグを含める",
    },
    "config.overwrite": {
        "en": "Overwrite existing field",
        "es": "Sobrescribir campo existente",
        "ja": "既存のフィールドを上書き",
    },
    "config.append": {
        "en": "Append to the end (don't replace)",
        "es": "Añadir al final (no reemplazar)",
        "ja": "末尾に追記(置き換えない)",
    },
    "config.multi_select": {
        "en": "Picker: multi-select",
        "es": "Picker: multi-selección",
        "ja": "選択画面:複数選択",
    },
    "config.fieldmap_title": {
        "en": (
            "<b>Field mapping per note type</b><br>"
            "<small>Enter comma-separated field names. The first existing "
            "one in the card will be used. Row <i>{default_key}</i> is "
            "the fallback.</small>"
        ),
        "es": (
            "<b>Mapeo de campos por tipo de nota</b><br>"
            "<small>Escribe nombres de campo separados por comas. "
            "Se usará el primero que exista en la tarjeta. "
            "La fila <i>{default_key}</i> es el fallback.</small>"
        ),
        "ja": (
            "<b>ノートタイプごとのフィールドマッピング</b><br>"
            "<small>カンマ区切りでフィールド名を入力。カードに存在する"
            "最初のフィールドが使われます。<i>{default_key}</i> 行は"
            "フォールバック。</small>"
        ),
    },
    "config.col.notetype": {
        "en": "Note type",
        "es": "Tipo de nota",
        "ja": "ノートタイプ",
    },
    "config.col.fields": {
        "en": "Fields (comma-separated)",
        "es": "Campos (coma-separados)",
        "ja": "フィールド(カンマ区切り)",
    },
    "config.btn.add_row": {
        "en": "Add note type…",
        "es": "Añadir tipo de nota…",
        "ja": "ノートタイプを追加…",
    },
    "config.btn.del_row": {
        "en": "Delete row",
        "es": "Eliminar fila",
        "ja": "行を削除",
    },
    "config.dicts_title": {
        "en": (
            "<b>Local dictionaries (Yomichan/Yomitan ZIPs)</b><br>"
            "<small>Folder: <code>{folder}</code></small>"
        ),
        "es": (
            "<b>Diccionarios locales (ZIP Yomichan/Yomitan)</b><br>"
            "<small>Carpeta: <code>{folder}</code></small>"
        ),
        "ja": (
            "<b>ローカル辞書(Yomichan/Yomitan の ZIP)</b><br>"
            "<small>フォルダ:<code>{folder}</code></small>"
        ),
    },
    "config.col.active": {"en": "Active", "es": "Activo", "ja": "有効"},
    "config.col.dict": {
        "en": "Dictionary", "es": "Diccionario", "ja": "辞書"
    },
    "config.btn.reload": {
        "en": "Reload list",
        "es": "Recargar lista",
        "ja": "リストを再読み込み",
    },
    "config.add_notetype_title": {
        "en": "Pick a note type",
        "es": "Elegir tipo de nota",
        "ja": "ノートタイプを選択",
    },
    "config.notetype_label": {
        "en": "Note type:",
        "es": "Tipo de nota:",
        "ja": "ノートタイプ:",
    },
    "config.cannot_delete_default": {
        "en": "You can't delete the _default row.",
        "es": "No puedes eliminar la fila _default.",
        "ja": "_default 行は削除できません。",
    },
    "config.no_dicts": {
        "en": (
            "(no ZIP detected — copy files into the 'dictionaries/' folder)"
        ),
        "es": (
            "(ningún ZIP detectado — copia archivos en la carpeta "
            "'dictionaries/')"
        ),
        "ja": (
            "(ZIP が見つかりません — 'dictionaries/' フォルダに追加してください)"
        ),
    },

    # ------------------------------------------------------------- reviewer
    "reviewer.select_first": {
        "en": "Jisho Lookup: select a word with the mouse first.",
        "es": "Jisho Lookup: selecciona primero una palabra con el ratón.",
        "ja": "Jisho Lookup:まずマウスで語を選択してください。",
    },
    "reviewer.searching": {
        "en": "Searching definition…",
        "es": "Buscando definición…",
        "ja": "定義を検索中…",
    },
    "reviewer.searching_picker": {
        "en": "Searching senses…",
        "es": "Buscando acepciones…",
        "ja": "意味を検索中…",
    },
    "reviewer.not_found": {
        "en": "Jisho Lookup: nothing found for <b>{query}</b>.",
        "es": "Jisho Lookup: nada encontrado para <b>{query}</b>.",
        "ja": "Jisho Lookup:<b>{query}</b> が見つかりませんでした。",
    },
    "reviewer.not_found_picker": {
        "en": (
            "Jisho Lookup: nothing found for <b>{query}</b>. "
            "Try switching language in the popup."
        ),
        "es": (
            "Jisho Lookup: nada encontrado para <b>{query}</b>. "
            "Prueba a cambiar de idioma en el popup."
        ),
        "ja": (
            "Jisho Lookup:<b>{query}</b> が見つかりませんでした。"
            "ポップアップで言語を変えてみてください。"
        ),
    },
    "reviewer.no_field": {
        "en": (
            "Jisho Lookup: no field configured for <b>{model}</b>.<br>"
            "Available fields: {fields}.<br>"
            "Open Tools → Jisho Lookup → Configuration."
        ),
        "es": (
            "Jisho Lookup: sin campo configurado para <b>{model}</b>.<br>"
            "Campos disponibles: {fields}.<br>"
            "Abre Herramientas → Jisho Lookup → Configuración."
        ),
        "ja": (
            "Jisho Lookup:<b>{model}</b> のフィールド設定がありません。<br>"
            "利用可能なフィールド:{fields}。<br>"
            "ツール → Jisho Lookup → 設定 を開いてください。"
        ),
    },
    "reviewer.field_has_content": {
        "en": (
            "Jisho Lookup: <b>{field}</b> already has content. "
            "Enable 'overwrite' or 'append' in the configuration "
            "(or use the popup to choose a mode)."
        ),
        "es": (
            "Jisho Lookup: <b>{field}</b> ya tiene contenido. "
            "Activa 'sobrescribir' o 'añadir al final' en la configuración "
            "(o usa el popup para elegir modo)."
        ),
        "ja": (
            "Jisho Lookup:<b>{field}</b> には既に内容があります。"
            "設定で「上書き」または「追記」を有効にするか、"
            "ポップアップでモードを選んでください。"
        ),
    },
    "reviewer.success": {
        "en": (
            "Jisho Lookup: <b>{query}</b> → field <b>{field}</b> "
            "({origin}{pair_suffix})."
        ),
        "es": (
            "Jisho Lookup: <b>{query}</b> → campo <b>{field}</b> "
            "({origin}{pair_suffix})."
        ),
        "ja": (
            "Jisho Lookup:<b>{query}</b> → フィールド <b>{field}</b> "
            "({origin}{pair_suffix})。"
        ),
    },
    "reviewer.not_reviewing": {
        "en": "Jisho Lookup: you must be reviewing a card.",
        "es": "Jisho Lookup: debes estar revisando una tarjeta.",
        "ja": "Jisho Lookup:カードを復習中である必要があります。",
    },
    "reviewer.no_card": {
        "en": "Jisho Lookup: no active card.",
        "es": "Jisho Lookup: no hay tarjeta activa.",
        "ja": "Jisho Lookup:有効なカードがありません。",
    },
    "reviewer.no_read": {
        "en": "Jisho Lookup: couldn't read the selection.",
        "es": "Jisho Lookup: no se pudo leer la selección.",
        "ja": "Jisho Lookup:選択を読み取れませんでした。",
    },

    # Origen de la definición (se muestra entre paréntesis en success)
    "source.jisho": {"en": "Jisho", "es": "Jisho", "ja": "Jisho"},
    "source.wiktionary": {
        "en": "Wiktionary", "es": "Wiktionary", "ja": "Wiktionary"
    },
    "source.local": {
        "en": "local dictionary",
        "es": "diccionario local",
        "ja": "ローカル辞書",
    },
    "source.mixed": {
        "en": "mixed sources",
        "es": "mezcla de fuentes",
        "ja": "複数のソース",
    },
}
