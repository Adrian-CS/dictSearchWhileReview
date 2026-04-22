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
    QAbstractItemView,
    Qt,
    QKeySequence,
    QShortcut,
)

from . import lang


# El callback de recarga recibe un pair_id y devuelve (choices, header).
ReloadFn = Callable[[str], Tuple[List[dict], str]]


class PickerResult:
    __slots__ = ("picked", "field", "mode", "pair")

    def __init__(self, picked: List[dict], field: str, mode: str, pair: str):
        self.picked = picked
        self.field = field
        self.mode = mode
        self.pair = pair

    def as_dict(self) -> dict:
        return {
            "picked": self.picked,
            "field": self.field,
            "mode": self.mode,
            "pair": self.pair,
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
        reload_fn: Optional[ReloadFn] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._choices: List[dict] = list(choices)
        self._selected_indices: List[int] = []
        self._reload_fn = reload_fn
        self._current_pair = lang.normalize_pair(initial_pair)

        self.setWindowTitle("Jisho Lookup — Elegir definición")
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
        top.addWidget(QLabel("Campo:"))
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
        self.radio_overwrite = QRadioButton("Sustituir")
        self.radio_append = QRadioButton("Añadir")
        self.mode_group.addButton(self.radio_overwrite)
        self.mode_group.addButton(self.radio_append)
        if initial_mode == "append":
            self.radio_append.setChecked(True)
        else:
            self.radio_overwrite.setChecked(True)
        top.addWidget(self.radio_overwrite)
        top.addWidget(self.radio_append)

        top.addStretch(1)

        # Idioma
        top.addWidget(QLabel("Idioma:"))
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
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Insertar")
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
        msg = (
            "Selecciona una o varias acepciones (Ctrl/Shift+clic). "
            "Enter para insertar, Esc para cancelar."
            if multi_select
            else "Selecciona una acepción. Enter para insertar, Esc para cancelar."
        )
        self._hint.setText(f"<small style='color:#888'>{_esc(msg)}</small>")

    def _populate_list(self, choices: List[dict]) -> None:
        self.list_widget.clear()
        self._choices = list(choices)
        for idx, c in enumerate(self._choices):
            label = _format_row(c)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(c.get("text") or "")
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

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
        try:
            choices, header = self._reload_fn(new_pair)
        except Exception:
            choices, header = [], ""
        self._set_header(header)
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
            picked=picked, field=field, mode=mode, pair=self._current_pair
        )


# ----------------------------------------------------------------------
def _format_row(choice: dict) -> str:
    """Formato visible de cada fila."""
    pos = choice.get("pos") or ""
    text = choice.get("text") or ""
    source = choice.get("source") or ""
    bits = []
    if pos:
        bits.append(f"[{pos}]")
    bits.append(text)
    row = " ".join(bits)
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
    reload_fn: Optional[ReloadFn] = None,
    parent=None,
) -> Optional[dict]:
    """Abre el diálogo. Devuelve un dict con
    ``{picked, field, mode, pair}`` o ``None`` si el usuario cancela.

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
        reload_fn=reload_fn,
        parent=parent,
    )
    if dlg.exec() == QDialog.DialogCode.Accepted:
        bundle = dlg.result_bundle()
        if not bundle.picked:
            return None
        return bundle.as_dict()
    return None
