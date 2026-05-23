# -*- coding: utf-8 -*-
"""Diálogo para añadir definiciones en bulk a un mazo (solo diccionarios locales)."""

from __future__ import annotations

import re
from typing import List

from aqt import mw
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QCheckBox,
    QRadioButton,
    QApplication,
)

from . import lookup, yomitan_reader
from .i18n import tr


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


class BulkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("bulk.window_title"))
        self.resize(480, 500)
        self._running = False
        self._cancel_flag = False
        self._build_ui()
        self._populate_decks()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Deck
        deck_row = QHBoxLayout()
        deck_row.addWidget(QLabel(tr("bulk.deck")))
        self.deck_combo = QComboBox()
        self.deck_combo.currentIndexChanged.connect(self._on_deck_changed)
        deck_row.addWidget(self.deck_combo, 1)
        layout.addLayout(deck_row)

        # Source field (word)
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel(tr("bulk.source_field")))
        self.src_combo = QComboBox()
        src_row.addWidget(self.src_combo, 1)
        layout.addLayout(src_row)

        # Target field (definition)
        tgt_row = QHBoxLayout()
        tgt_row.addWidget(QLabel(tr("bulk.target_field")))
        self.tgt_combo = QComboBox()
        tgt_row.addWidget(self.tgt_combo, 1)
        layout.addLayout(tgt_row)

        # Write mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(tr("bulk.mode")))
        self.radio_append = QRadioButton(tr("picker.append"))
        self.radio_overwrite = QRadioButton(tr("picker.overwrite"))
        self.radio_append.setChecked(True)
        mode_row.addWidget(self.radio_append)
        mode_row.addWidget(self.radio_overwrite)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        # Skip cards that already have content
        self.skip_check = QCheckBox(tr("bulk.skip_existing"))
        self.skip_check.setChecked(True)
        layout.addWidget(self.skip_check)

        # Progress bar (hidden until started)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Log
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(120)
        layout.addWidget(self.log_edit)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.start_btn = QPushButton(tr("bulk.start"))
        self.start_btn.clicked.connect(self._on_start)
        self.cancel_btn = QPushButton(tr("common.cancel"))
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    # ---------------------------------------------------------------- logic

    def _populate_decks(self) -> None:
        self.deck_combo.clear()
        try:
            pairs = sorted(mw.col.decks.all_names_and_ids(), key=lambda x: x[0])
        except Exception:
            pairs = []
        for name, did in pairs:
            self.deck_combo.addItem(name, did)
        if pairs:
            self._on_deck_changed()

    def _on_deck_changed(self) -> None:
        deck_name = self.deck_combo.currentText()
        if not deck_name:
            return
        escaped = deck_name.replace('"', '\\"')
        try:
            note_ids = list(mw.col.find_notes(f'"deck:{escaped}"'))
        except Exception:
            note_ids = []
        fields = self._collect_fields(note_ids)

        prev_src = self.src_combo.currentText()
        prev_tgt = self.tgt_combo.currentText()

        self.src_combo.clear()
        self.tgt_combo.clear()
        for f in fields:
            self.src_combo.addItem(f)
            self.tgt_combo.addItem(f)

        if prev_src in fields:
            self.src_combo.setCurrentText(prev_src)
        if prev_tgt in fields:
            self.tgt_combo.setCurrentText(prev_tgt)
        elif len(fields) > 1 and not prev_tgt:
            self.tgt_combo.setCurrentIndex(1)

    def _collect_fields(self, note_ids: List[int]) -> List[str]:
        seen: List[str] = []
        seen_set: set = set()
        for nid in note_ids[:100]:
            try:
                note = mw.col.get_note(nid)
                for f in note.keys():
                    if f not in seen_set:
                        seen_set.add(f)
                        seen.append(f)
            except Exception:
                continue
        return seen

    def _on_cancel(self) -> None:
        if self._running:
            self._cancel_flag = True
        else:
            self.reject()

    def _on_start(self) -> None:
        if self._running:
            return

        deck_name = self.deck_combo.currentText()
        src_field = self.src_combo.currentText()
        tgt_field = self.tgt_combo.currentText()
        if not deck_name or not src_field or not tgt_field:
            return

        overwrite = self.radio_overwrite.isChecked()
        skip_existing = self.skip_check.isChecked()

        config = mw.addonManager.getConfig(__name__.split(".")[0]) or {}
        enabled_dicts = config.get("enabled_local_dicts") or []
        max_senses = int(config.get("max_senses") or 3)
        include_reading = bool(config.get("include_reading", True))

        escaped = deck_name.replace('"', '\\"')
        try:
            note_ids = list(mw.col.find_notes(f'"deck:{escaped}"'))
        except Exception:
            note_ids = []

        if not note_ids:
            self._log(tr("bulk.no_notes"))
            return

        self._running = True
        self._cancel_flag = False
        self.start_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(note_ids))
        self.progress.setValue(0)
        self.log_edit.clear()
        self._log(tr("bulk.starting", total=len(note_ids)))
        QApplication.processEvents()

        self._run_bulk(
            note_ids, src_field, tgt_field,
            overwrite, skip_existing, enabled_dicts, max_senses, include_reading,
        )

    def _run_bulk(
        self,
        note_ids: List[int],
        src_field: str,
        tgt_field: str,
        overwrite: bool,
        skip_existing: bool,
        enabled_dicts: List[str],
        max_senses: int,
        include_reading: bool,
    ) -> None:
        mgr = lookup.get_dict_manager(enabled=enabled_dicts if enabled_dicts else None)

        found = skipped = not_found = 0

        for i, nid in enumerate(note_ids):
            if self._cancel_flag:
                self._log(tr("bulk.cancelled"))
                break

            try:
                note = mw.col.get_note(nid)
            except Exception:
                skipped += 1
                continue

            note_keys = note.keys()
            if src_field not in note_keys or tgt_field not in note_keys:
                skipped += 1
                self.progress.setValue(i + 1)
                continue

            word = _strip_html(note[src_field])
            if not word:
                skipped += 1
                self.progress.setValue(i + 1)
                continue

            existing = note[tgt_field].strip()
            if existing and skip_existing:
                skipped += 1
                self.progress.setValue(i + 1)
                continue

            word_clean = lookup.normalize_query(word)
            local = mgr.lookup(word_clean)

            if not local:
                not_found += 1
                self.progress.setValue(i + 1)
                if i % 50 == 0:
                    QApplication.processEvents()
                continue

            html = yomitan_reader.format_local_entries(
                local, max_senses=max_senses, include_reading=include_reading
            )
            if not html:
                not_found += 1
                self.progress.setValue(i + 1)
                continue

            if existing and not overwrite:
                note[tgt_field] = existing + "<br>" + html
            else:
                note[tgt_field] = html

            try:
                mw.col.update_note(note)
            except Exception:
                try:
                    note.flush()
                except Exception:
                    pass

            found += 1
            self.progress.setValue(i + 1)
            if i % 50 == 0:
                QApplication.processEvents()

        self._log(tr("bulk.done", found=found, not_found=not_found, skipped=skipped))
        self._running = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setText(tr("common.ok"))

    def _log(self, text: str) -> None:
        self.log_edit.append(text)
        QApplication.processEvents()


def open_bulk_dialog() -> None:
    dlg = BulkDialog(mw)
    dlg.exec()
