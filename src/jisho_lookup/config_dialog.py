# -*- coding: utf-8 -*-
"""Diálogo Qt para mapear note types a campos y activar diccionarios locales."""

from __future__ import annotations

import os
from typing import Dict, List

from aqt import mw
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QMessageBox,
    QComboBox,
    Qt,
)

from . import lookup
from . import lang
from .i18n import tr


DEFAULT_KEY = "_default"


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("config.window_title"))
        self.resize(720, 540)

        self.config = mw.addonManager.getConfig(__name__.split(".")[0]) or {}
        self._build_ui()
        self._load_from_config()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Atajos (RUN + PICK)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("config.shortcut")))
        self.shortcut_edit = QLineEdit()
        self.shortcut_edit.setPlaceholderText("Ctrl+S")
        self.shortcut_edit.setMaximumWidth(140)
        row.addWidget(self.shortcut_edit)

        row.addSpacing(12)
        row.addWidget(QLabel(tr("config.picker_shortcut")))
        self.picker_shortcut_edit = QLineEdit()
        self.picker_shortcut_edit.setPlaceholderText("Ctrl+Shift+S")
        self.picker_shortcut_edit.setMaximumWidth(160)
        row.addWidget(self.picker_shortcut_edit)

        row.addSpacing(12)
        row.addWidget(QLabel(tr("config.strategy")))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem(tr("config.strategy.online_then_local"), "jisho_then_local")
        self.strategy_combo.addItem(tr("config.strategy.local_only"), "local_only")
        self.strategy_combo.addItem(tr("config.strategy.online_only"), "jisho_only")
        row.addWidget(self.strategy_combo)
        row.addStretch(1)
        layout.addLayout(row)

        # Idioma por defecto + auto-fallback
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("config.language_pair")))
        self.lang_combo = QComboBox()
        for pid in lang.all_pair_ids():
            self.lang_combo.addItem(lang.pair_label(pid), pid)
        lang_row.addWidget(self.lang_combo)

        self.auto_fallback_cb = QCheckBox(tr("config.auto_fallback"))
        lang_row.addSpacing(12)
        lang_row.addWidget(self.auto_fallback_cb)
        lang_row.addStretch(1)
        layout.addLayout(lang_row)

        # Opciones booleanas
        opts = QHBoxLayout()
        self.include_reading_cb = QCheckBox(tr("config.include_reading"))
        self.include_pos_cb = QCheckBox(tr("config.include_pos"))
        self.overwrite_cb = QCheckBox(tr("config.overwrite"))
        self.append_cb = QCheckBox(tr("config.append"))
        self.picker_multi_cb = QCheckBox(tr("config.multi_select"))
        for cb in (self.include_reading_cb, self.include_pos_cb, self.overwrite_cb,
                   self.append_cb, self.picker_multi_cb):
            opts.addWidget(cb)
        opts.addStretch(1)
        layout.addLayout(opts)

        # Tabla de mapeo notetype -> campos
        layout.addWidget(QLabel(
            tr("config.fieldmap_title", default_key=DEFAULT_KEY)
        ))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([
            tr("config.col.notetype"), tr("config.col.fields")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(tr("config.btn.add_row"))
        self.add_btn.clicked.connect(self._on_add_row)
        self.del_btn = QPushButton(tr("config.btn.del_row"))
        self.del_btn.clicked.connect(self._on_del_row)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Diccionarios locales
        layout.addWidget(QLabel(
            tr("config.dicts_title", folder=lookup.DICTS_DIR)
        ))
        self.dict_table = QTableWidget(0, 2)
        self.dict_table.setHorizontalHeaderLabels([
            tr("config.col.active"), tr("config.col.dict")
        ])
        self.dict_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dict_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.dict_table, 1)

        dict_row = QHBoxLayout()
        self.reload_btn = QPushButton(tr("config.btn.reload"))
        self.reload_btn.clicked.connect(self._reload_dicts)
        dict_row.addWidget(self.reload_btn)
        dict_row.addStretch(1)
        layout.addLayout(dict_row)

        # OK / Cancelar
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.ok_btn = QPushButton(tr("common.save"))
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton(tr("common.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.ok_btn)
        layout.addLayout(bottom)

    # --------------------------------------------------------------- state
    def _load_from_config(self) -> None:
        self.shortcut_edit.setText(str(self.config.get("shortcut") or "Ctrl+S"))
        self.picker_shortcut_edit.setText(str(self.config.get("picker_shortcut") or "Ctrl+Shift+S"))
        strat = (self.config.get("strategy") or "jisho_then_local").lower()
        idx = max(0, self.strategy_combo.findData(strat))
        self.strategy_combo.setCurrentIndex(idx)

        pair = lang.normalize_pair(self.config.get("language_pair"))
        pidx = max(0, self.lang_combo.findData(pair))
        self.lang_combo.setCurrentIndex(pidx)
        self.auto_fallback_cb.setChecked(
            bool(self.config.get("language_pair_auto_fallback", True))
        )

        self.include_reading_cb.setChecked(bool(self.config.get("include_reading", True)))
        self.include_pos_cb.setChecked(bool(self.config.get("include_parts_of_speech", True)))
        self.overwrite_cb.setChecked(bool(self.config.get("overwrite_existing", False)))
        self.append_cb.setChecked(bool(self.config.get("append_mode", False)))
        self.picker_multi_cb.setChecked(bool(self.config.get("picker_multi_select", True)))

        fieldmap: Dict[str, List[str]] = dict(self.config.get("note_type_field_map") or {})
        # asegurar _default siempre presente
        if DEFAULT_KEY not in fieldmap:
            fieldmap[DEFAULT_KEY] = ["Significado", "Meaning"]

        for nt, fields in fieldmap.items():
            self._append_row(nt, ", ".join(fields or []))

        self._reload_dicts()

    def _reload_dicts(self) -> None:
        self.dict_table.setRowCount(0)
        mgr = lookup.get_dict_manager()
        names = mgr.available_names()
        enabled = set(self.config.get("enabled_local_dicts") or [])
        # si la lista está vacía interpretamos "todos activos"
        all_active = not enabled
        for name in names:
            r = self.dict_table.rowCount()
            self.dict_table.insertRow(r)
            cb = QCheckBox()
            cb.setChecked(all_active or name in enabled)
            # envolver en widget con layout centrado
            self.dict_table.setCellWidget(r, 0, cb)
            self.dict_table.setItem(r, 1, QTableWidgetItem(name))
            self.dict_table.item(r, 1).setFlags(Qt.ItemFlag.ItemIsEnabled)
        if not names:
            r = self.dict_table.rowCount()
            self.dict_table.insertRow(r)
            self.dict_table.setItem(r, 1, QTableWidgetItem(tr("config.no_dicts")))

    # --------------------------------------------------------------- rows
    def _append_row(self, notetype: str, fields: str) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(notetype))
        self.table.setItem(r, 1, QTableWidgetItem(fields))

    def _on_add_row(self) -> None:
        models = []
        try:
            models = [m["name"] for m in mw.col.models.all()]
        except Exception:
            pass
        # diálogo sencillo con combo
        picker = QDialog(self)
        picker.setWindowTitle(tr("config.add_notetype_title"))
        v = QVBoxLayout(picker)
        v.addWidget(QLabel(tr("config.notetype_label")))
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(models)
        v.addWidget(combo)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton(tr("common.ok"))
        ok.clicked.connect(picker.accept)
        cancel = QPushButton(tr("common.cancel"))
        cancel.clicked.connect(picker.reject)
        row.addWidget(cancel)
        row.addWidget(ok)
        v.addLayout(row)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        name = combo.currentText().strip()
        if not name:
            return
        self._append_row(name, "Significado, Meaning")

    def _on_del_row(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            key = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            if key == DEFAULT_KEY:
                QMessageBox.information(
                    self,
                    tr("common.addon_name"),
                    tr("config.cannot_delete_default"),
                )
                continue
            self.table.removeRow(r)

    # --------------------------------------------------------------- save
    def _on_save(self) -> None:
        fieldmap: Dict[str, List[str]] = {}
        for r in range(self.table.rowCount()):
            key_item = self.table.item(r, 0)
            val_item = self.table.item(r, 1)
            if not key_item:
                continue
            key = key_item.text().strip()
            if not key:
                continue
            raw = val_item.text() if val_item else ""
            fields = [p.strip() for p in raw.split(",") if p.strip()]
            if fields:
                fieldmap[key] = fields
        if DEFAULT_KEY not in fieldmap:
            fieldmap[DEFAULT_KEY] = ["Significado", "Meaning"]

        # diccionarios activos
        enabled_dicts: List[str] = []
        total_rows = self.dict_table.rowCount()
        for r in range(total_rows):
            cb = self.dict_table.cellWidget(r, 0)
            item = self.dict_table.item(r, 1)
            if cb is None or item is None:
                continue
            if cb.isChecked():
                enabled_dicts.append(item.text())
        # si todos están marcados, guardamos lista vacía = "todos"
        all_names = lookup.get_dict_manager().available_names()
        if set(enabled_dicts) == set(all_names):
            enabled_dicts = []

        new_conf = dict(self.config)
        new_conf.update({
            "shortcut": self.shortcut_edit.text().strip() or "Ctrl+S",
            "picker_shortcut": self.picker_shortcut_edit.text().strip() or "Ctrl+Shift+S",
            "picker_multi_select": self.picker_multi_cb.isChecked(),
            "strategy": self.strategy_combo.currentData(),
            "language_pair": self.lang_combo.currentData() or lang.DEFAULT_PAIR,
            "language_pair_auto_fallback": self.auto_fallback_cb.isChecked(),
            "include_reading": self.include_reading_cb.isChecked(),
            "include_parts_of_speech": self.include_pos_cb.isChecked(),
            "overwrite_existing": self.overwrite_cb.isChecked(),
            "append_mode": self.append_cb.isChecked(),
            "note_type_field_map": fieldmap,
            "enabled_local_dicts": enabled_dicts,
        })
        mw.addonManager.writeConfig(__name__.split(".")[0], new_conf)
        lookup.reset_dict_manager()
        self.accept()


def open_config_dialog() -> None:
    dlg = ConfigDialog(parent=mw)
    dlg.exec()
