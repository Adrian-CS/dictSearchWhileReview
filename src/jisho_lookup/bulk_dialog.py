# -*- coding: utf-8 -*-
"""Diálogo para añadir definiciones en bulk a un mazo."""

from __future__ import annotations

import re
import time
from typing import List

from aqt import mw
from aqt.qt import (
    QButtonGroup,
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
    QSpinBox,
    QApplication,
)

from . import lang, lookup
from .i18n import tr

# Pausa entre peticiones online para no saturar Jisho/Wiktionary.
_ONLINE_DELAY_S = 0.5


_ANKI_BRACKET_RE = re.compile(r"\[[^\]]*\]")


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = _ANKI_BRACKET_RE.sub("", text)
    return text.strip()


class BulkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("bulk.window_title"))
        self.resize(500, 540)
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

        # Language pair
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("picker.language")))
        self.lang_combo = QComboBox()
        for pid in lang.all_pair_ids():
            self.lang_combo.addItem(lang.pair_label(pid), pid)
        lang_row.addWidget(self.lang_combo, 1)
        layout.addLayout(lang_row)

        # Strategy
        strat_row = QHBoxLayout()
        strat_row.addWidget(QLabel(tr("config.strategy")))
        self.radio_local = QRadioButton(tr("config.strategy.local_only"))
        self.radio_online = QRadioButton(tr("config.strategy.online_then_local"))
        self.radio_local.setChecked(True)
        self._strat_group = QButtonGroup(self)
        self._strat_group.addButton(self.radio_local)
        self._strat_group.addButton(self.radio_online)
        strat_row.addWidget(self.radio_local)
        strat_row.addWidget(self.radio_online)
        strat_row.addStretch(1)
        layout.addLayout(strat_row)

        # Write mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(tr("bulk.mode")))
        self.radio_append = QRadioButton(tr("picker.append"))
        self.radio_overwrite = QRadioButton(tr("picker.overwrite"))
        self.radio_append.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.radio_append)
        self._mode_group.addButton(self.radio_overwrite)
        mode_row.addWidget(self.radio_append)
        mode_row.addWidget(self.radio_overwrite)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        # Max definitions per word
        senses_row = QHBoxLayout()
        senses_row.addWidget(QLabel(tr("bulk.max_senses")))
        self.senses_spin = QSpinBox()
        self.senses_spin.setRange(1, 20)
        self.senses_spin.setValue(3)
        self.senses_spin.setFixedWidth(60)
        senses_row.addWidget(self.senses_spin)
        senses_row.addStretch(1)
        layout.addLayout(senses_row)

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
        self.log_edit.setMinimumHeight(100)
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
            for deck in sorted(mw.col.decks.all_names_and_ids(), key=lambda d: d.name):
                self.deck_combo.addItem(deck.name, deck.id)
        except Exception:
            pass

        # Set language pair to global default
        config = mw.addonManager.getConfig(__name__.split(".")[0]) or {}
        default_pair = lang.normalize_pair(config.get("language_pair"))
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == default_pair:
                self.lang_combo.setCurrentIndex(i)
                break

        if self.deck_combo.count() > 0:
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

        pair_id = self.lang_combo.currentData()
        use_online = self.radio_online.isChecked()
        overwrite = self.radio_overwrite.isChecked()
        skip_existing = self.skip_check.isChecked()

        config = mw.addonManager.getConfig(__name__.split(".")[0]) or {}
        # Override strategy and max_senses to match the user's bulk choices.
        bulk_config = dict(config)
        bulk_config["strategy"] = "jisho_then_local" if use_online else "local_only"
        bulk_config["max_senses"] = self.senses_spin.value()

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
            pair_id, overwrite, skip_existing, bulk_config,
        )

    def _run_bulk(
        self,
        note_ids: List[int],
        src_field: str,
        tgt_field: str,
        pair_id: str,
        overwrite: bool,
        skip_existing: bool,
        config: dict,
    ) -> None:
        # Show which local dicts are loaded so the user can diagnose problems.
        try:
            enabled = config.get("enabled_local_dicts") or []
            mgr = lookup.get_dict_manager(enabled=enabled if enabled else None)
            dict_names = [d.name for d in mgr.dicts] if mgr.dicts else []
            if not dict_names:
                # discover() may not have run yet
                mgr.discover()
                dict_names = [d.name for d in mgr.dicts]
            if dict_names:
                self._log(f"Dicts: {', '.join(dict_names)}")
            else:
                self._log("No local dicts found in dictionaries/ folder.")
        except Exception:
            pass

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

            html, source, _ = lookup.do_lookup(
                lookup.normalize_query(word), config, pair=pair_id
            )

            # Rate-limit online sources to avoid being blocked.
            if source in ("jisho", "wiktionary"):
                time.sleep(_ONLINE_DELAY_S)

            if not html:
                not_found += 1
                self._log(f"  ✗ {word}")
                self.progress.setValue(i + 1)
                QApplication.processEvents()
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
            if i % 20 == 0:
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
