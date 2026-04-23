# -*- coding: utf-8 -*-
"""Jisho Lookup — Anki add-on (2.1.60+).

Selecciona una palabra japonesa en el reviewer, pulsa el atajo (Ctrl+S por
defecto) y el add-on busca la definición en Jisho (o en diccionarios locales
Yomichan/Yomitan como fallback) y la inserta en un campo configurable de la
tarjeta actual.
"""

from __future__ import annotations

from aqt import mw
from aqt.qt import QAction, QKeySequence

from . import reviewer
from . import config_dialog
from .i18n import tr


def _on_open_config() -> None:
    config_dialog.open_config_dialog()
    reviewer.reload_shortcut()


def _on_run_now() -> None:
    reviewer.run_from_menu()


def _on_pick_now() -> None:
    reviewer.pick_from_menu()


def _build_menu() -> None:
    # "Jisho Lookup" se mantiene en los tres idiomas (marca).
    menu = mw.form.menuTools.addMenu(tr("common.addon_name"))

    act_run = QAction(tr("menu.run_now"), mw)
    act_run.setShortcut(QKeySequence("Ctrl+Shift+J"))
    act_run.triggered.connect(_on_run_now)
    menu.addAction(act_run)

    act_pick = QAction(tr("menu.pick_now"), mw)
    act_pick.setShortcut(QKeySequence("Ctrl+Shift+K"))
    act_pick.triggered.connect(_on_pick_now)
    menu.addAction(act_pick)

    menu.addSeparator()

    act_conf = QAction(tr("menu.config"), mw)
    act_conf.triggered.connect(_on_open_config)
    menu.addAction(act_conf)


def _on_config_from_addon_manager():
    _on_open_config()
    return True


# --------------------------------------------------------------------- init

reviewer.setup()
_build_menu()

mw.addonManager.setConfigAction(__name__, _on_config_from_addon_manager)
