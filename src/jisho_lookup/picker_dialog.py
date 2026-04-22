# -*- coding: utf-8 -*-
"""Diálogo Qt: mostrar lista de acepciones y devolver las elegidas."""

from __future__ import annotations

from typing import List, Optional

from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QAbstractItemView,
    Qt,
    QKeySequence,
    QShortcut,
)


class DefinitionPicker(QDialog):
    """Lista de definiciones con multi-selección opcional."""

    def __init__(
        self,
        choices: List[dict],
        *,
        header: str = "",
        multi_select: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._choices = choices
        self._selected_indices: List[int] = []

        self.setWindowTitle("Jisho Lookup — Elegir definición")
        self.resize(620, 480)

        layout = QVBoxLayout(self)

        if header:
            lbl = QLabel(f"<div style='font-size:18px'>{_esc(header)}</div>")
            layout.addWidget(lbl)

        hint = (
            "Selecciona una o varias acepciones (Ctrl/Shift+clic). "
            "Enter para insertar, Esc para cancelar."
            if multi_select
            else "Selecciona una acepción. Enter para insertar, Esc para cancelar."
        )
        layout.addWidget(QLabel(f"<small style='color:#888'>{hint}</small>"))

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
        layout.addWidget(self.list_widget, 1)

        # Poblar
        for idx, c in enumerate(choices):
            label = _format_row(c)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            # Tooltip con el HTML que se insertará (útil para preview)
            item.setToolTip(c.get("text") or "")
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

        # Botones
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Insertar")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_accept)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_ok)
        layout.addLayout(row)

        # Enter también confirma aunque el foco esté en la lista
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self._on_accept)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self._on_accept)

    # ------------------------------------------------------------------
    def _on_accept(self, *_):
        self._selected_indices = sorted(
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.list_widget.selectedItems()
        )
        if not self._selected_indices:
            # fallback al elemento actual
            cur = self.list_widget.currentRow()
            if cur >= 0:
                self._selected_indices = [cur]
        if not self._selected_indices:
            self.reject()
            return
        self.accept()

    def selected_choices(self) -> List[dict]:
        return [self._choices[i] for i in self._selected_indices if 0 <= i < len(self._choices)]


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
        # fuente al final, entre paréntesis
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
    parent=None,
) -> Optional[List[dict]]:
    """Abre el diálogo. Devuelve la lista de opciones elegidas o None si
    el usuario cancela / no hay opciones."""
    if not choices:
        return None
    dlg = DefinitionPicker(
        choices,
        header=header,
        multi_select=multi_select,
        parent=parent,
    )
    if dlg.exec() == QDialog.DialogCode.Accepted:
        picked = dlg.selected_choices()
        return picked or None
    return None
