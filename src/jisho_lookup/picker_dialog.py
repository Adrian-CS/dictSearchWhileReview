# -*- coding: utf-8 -*-
"""Diálogo Qt: elegir acepciones + campo destino + modo + idioma."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QAbstractItemView,
    Qt,
    QKeySequence,
    QShortcut,
)

try:
    from aqt import mw as _mw  # para taskman (background threading)
except Exception:  # pragma: no cover - fuera de Anki
    _mw = None

from . import lang
from .i18n import tr


# El callback de recarga recibe un pair_id y devuelve (choices, header).
ReloadFn = Callable[[str], Tuple[List[dict], str]]


class PickerResult:
    __slots__ = ("picked", "field", "mode", "pair", "include_pos")

    def __init__(
        self,
        picked: List[dict],
        field: str,
        mode: str,
        pair: str,
        include_pos: bool,
    ):
        self.picked = picked
        self.field = field
        self.mode = mode
        self.pair = pair
        self.include_pos = include_pos

    def as_dict(self) -> dict:
        return {
            "picked": self.picked,
            "field": self.field,
            "mode": self.mode,
            "pair": self.pair,
            "include_pos": self.include_pos,
        }


class DefinitionPicker(QDialog):
    """Lista de definiciones con:
      - combo de campo destino
      - radios overwrite / append
      - combo de par de idioma (recarga en vivo)
      - selección simple o múltiple de acepciones
    """

    def __init__(
        self,
        choices: List[dict],
        *,
        header: str = "",
        multi_select: bool = True,
        field_candidates: Optional[List[str]] = None,
        initial_field: Optional[str] = None,
        initial_mode: str = "overwrite",  # "overwrite" | "append"
        initial_pair: str = lang.DEFAULT_PAIR,
        initial_include_pos: bool = True,
        reload_fn: Optional[ReloadFn] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._choices: List[dict] = list(choices)
        self._selected_indices: List[int] = []
        self._reload_fn = reload_fn
        self._current_pair = lang.normalize_pair(initial_pair)
        self._include_pos = bool(initial_include_pos)

        self.setWindowTitle(tr("picker.window_title"))
        self.resize(680, 520)

        root = QVBoxLayout(self)

        # -------------------------------------------------- cabecera
        self._header_label = QLabel()
        self._header_label.setTextFormat(Qt.TextFormat.RichText)
        self._set_header(header)
        root.addWidget(self._header_label)

        # -------------------------------------------------- fila superior
        top = QHBoxLayout()

        # Campo destino
        top.addWidget(QLabel(tr("picker.field")))
        self.field_combo = QComboBox()
        cands = list(field_candidates or [])
        for f in cands:
            self.field_combo.addItem(f)
        if initial_field and initial_field in cands:
            self.field_combo.setCurrentText(initial_field)
        elif cands:
            self.field_combo.setCurrentIndex(0)
        self.field_combo.setMinimumWidth(180)
        top.addWidget(self.field_combo)

        top.addSpacing(12)

        # Modo
        self.mode_group = QButtonGroup(self)
        self.radio_overwrite = QRadioButton(tr("picker.overwrite"))
        self.radio_append = QRadioButton(tr("picker.append"))
        self.mode_group.addButton(self.radio_overwrite)
        self.mode_group.addButton(self.radio_append)
        if initial_mode == "append":
            self.radio_append.setChecked(True)
        else:
            self.radio_overwrite.setChecked(True)
        top.addWidget(self.radio_overwrite)
        top.addWidget(self.radio_append)

        top.addStretch(1)

        # Toggle POS (anotaciones gramaticales) — sobreescribe el global
        # sólo para esta invocación del popup.
        self.pos_check = QCheckBox(tr("picker.pos"))
        self.pos_check.setToolTip(tr("picker.pos_tooltip"))
        self.pos_check.setChecked(self._include_pos)
        self.pos_check.toggled.connect(self._on_pos_toggled)
        top.addWidget(self.pos_check)

        top.addSpacing(12)

        # Idioma
        top.addWidget(QLabel(tr("picker.language")))
        self.lang_combo = QComboBox()
        self._pair_ids: List[str] = lang.all_pair_ids()
        for pid in self._pair_ids:
            self.lang_combo.addItem(lang.pair_label(pid), pid)
        if self._current_pair in self._pair_ids:
            self.lang_combo.setCurrentIndex(self._pair_ids.index(self._current_pair))
        self.lang_combo.setMinimumWidth(180)
        self.lang_combo.currentIndexChanged.connect(self._on_pair_changed)
        top.addWidget(self.lang_combo)

        root.addLayout(top)

        # -------------------------------------------------- hint
        self._hint = QLabel()
        self._hint.setTextFormat(Qt.TextFormat.RichText)
        self._set_hint(multi_select)
        root.addWidget(self._hint)

        # -------------------------------------------------- lista
        self.list_widget = QListWidget(self)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setUniformItemSizes(False)
        self.list_widget.setWordWrap(True)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
            if multi_select
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_widget.itemDoubleClicked.connect(self._on_accept)
        root.addWidget(self.list_widget, 1)

        self._populate_list(self._choices)

        # -------------------------------------------------- botones
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton(tr("common.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton(tr("picker.insert"))
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_accept)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_ok)
        root.addLayout(row)

        # Enter también confirma
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self._on_accept)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self._on_accept)

    # ------------------------------------------------------------------
    def _set_header(self, header: str) -> None:
        if header:
            self._header_label.setText(
                f"<div style='font-size:18px'>{_esc(header)}</div>"
            )
            self._header_label.setVisible(True)
        else:
            self._header_label.setText("")
            self._header_label.setVisible(False)

    def _set_hint(self, multi_select: bool) -> None:
        msg = tr("picker.hint_multi") if multi_select else tr("picker.hint_single")
        self._hint.setText(f"<small style='color:#888'>{_esc(msg)}</small>")

    def _populate_list(self, choices: List[dict]) -> None:
        self.list_widget.clear()
        self._choices = list(choices)
        for idx, c in enumerate(self._choices):
            label = _format_row(c, include_pos=self._include_pos)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(c.get("text") or "")
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    # ------------------------------------------------------------------
    def _on_pos_toggled(self, checked: bool) -> None:
        """Re-renderiza las filas sin volver a pedir datos.

        Memoriza también la selección actual (por índice) para restaurarla
        tras el repintado, así al alternar el checkbox no se pierde lo
        que el usuario ya había marcado.
        """
        self._include_pos = bool(checked)
        selected = sorted(
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.list_widget.selectedItems()
        )
        current = self.list_widget.currentRow()
        self._populate_list(self._choices)
        # Restaurar selección
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            idx = it.data(Qt.ItemDataRole.UserRole)
            if idx in selected:
                it.setSelected(True)
        if 0 <= current < self.list_widget.count():
            self.list_widget.setCurrentRow(current)

    # ------------------------------------------------------------------
    def _on_pair_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._pair_ids):
            return
        new_pair = self._pair_ids[idx]
        if new_pair == self._current_pair:
            return
        self._current_pair = new_pair
        if self._reload_fn is None:
            return

        # Placeholder mientras cargamos (la petición HTTP puede tardar).
        self._set_header(tr("picker.loading_pair", pair=lang.pair_label(new_pair)))
        self.list_widget.clear()
        busy = QListWidgetItem(tr("picker.loading"))
        busy.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list_widget.addItem(busy)

        fn = self._reload_fn

        def task():
            try:
                return fn(new_pair)
            except Exception:
                return [], ""

        def on_done(fut) -> None:
            # Si el usuario cambió otra vez de idioma mientras esperábamos,
            # descartamos este resultado.
            if self._current_pair != new_pair:
                return
            try:
                choices, header = fut.result()
            except Exception:
                choices, header = [], ""
            self._set_header(header or "")
            if choices:
                self._populate_list(choices)
            else:
                self.list_widget.clear()
                empty = QListWidgetItem(tr("picker.no_results"))
                empty.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list_widget.addItem(empty)
                self._choices = []

        if _mw is not None and hasattr(_mw, "taskman"):
            _mw.taskman.run_in_background(task, on_done)
        else:
            # Fallback síncrono (fuera de Anki, tests, etc.)
            try:
                choices, header = task()
            except Exception:
                choices, header = [], ""
            self._set_header(header or "")
            self._populate_list(choices or [])

    # ------------------------------------------------------------------
    def _on_accept(self, *_):
        self._selected_indices = sorted(
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.list_widget.selectedItems()
        )
        if not self._selected_indices:
            cur = self.list_widget.currentRow()
            if cur >= 0:
                self._selected_indices = [cur]
        if not self._selected_indices:
            self.reject()
            return
        self.accept()

    # ------------------------------------------------------------------
    def result_bundle(self) -> PickerResult:
        picked = [
            self._choices[i]
            for i in self._selected_indices
            if 0 <= i < len(self._choices)
        ]
        field = self.field_combo.currentText() if self.field_combo.count() else ""
        mode = "append" if self.radio_append.isChecked() else "overwrite"
        return PickerResult(
            picked=picked,
            field=field,
            mode=mode,
            pair=self._current_pair,
            include_pos=self._include_pos,
        )


# ----------------------------------------------------------------------
def _format_row(choice: dict, *, include_pos: bool = True) -> str:
    """Formato visible de cada fila.

    Prefijo con la palabra + lectura cuando existen, para que en pares
    como `en→ja` cada fila se lea como "空き【あき】 [n] space, room…",
    y no como "[n] space, room, gap" (que parece circular cuando se
    buscó precisamente la palabra 'space').

    `include_pos` controla si se muestra la etiqueta `[Noun]`, `[Verb]`,
    etc. Se suele pasar desde el estado del checkbox del diálogo.
    """
    pos = choice.get("pos") or ""
    text = choice.get("text") or ""
    source = choice.get("source") or ""
    word = choice.get("word") or ""
    reading = choice.get("reading") or ""

    head = ""
    if word:
        head = word
        if reading and reading != word:
            head += f" 【{reading}】"
        head += "   "

    bits = []
    if include_pos and pos:
        bits.append(f"[{pos}]")
    if text:
        bits.append(text)
    row = head + " ".join(bits)
    if source:
        row = f"{row}   ({source})"
    return row


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def show_picker(
    choices: List[dict],
    *,
    header: str = "",
    multi_select: bool = True,
    field_candidates: Optional[List[str]] = None,
    initial_field: Optional[str] = None,
    initial_mode: str = "overwrite",
    initial_pair: str = lang.DEFAULT_PAIR,
    initial_include_pos: bool = True,
    reload_fn: Optional[ReloadFn] = None,
    parent=None,
) -> Optional[dict]:
    """Abre el diálogo. Devuelve un dict con
    ``{picked, field, mode, pair, include_pos}`` o ``None`` si el
    usuario cancela.

    El diálogo permite cancelar sin elegir, pero también permite cambiar
    de idioma (vía `reload_fn`) aunque la búsqueda inicial no diera
    resultados. Si `choices` está vacío y no hay `reload_fn`, devuelve None.
    """
    if not choices and reload_fn is None:
        return None
    dlg = DefinitionPicker(
        choices,
        header=header,
        multi_select=multi_select,
        field_candidates=field_candidates,
        initial_field=initial_field,
        initial_mode=initial_mode,
        initial_pair=initial_pair,
        initial_include_pos=initial_include_pos,
        reload_fn=reload_fn,
        parent=parent,
    )
    if dlg.exec() == QDialog.DialogCode.Accepted:
        bundle = dlg.result_bundle()
        if not bundle.picked:
            return None
        return bundle.as_dict()
    return None
