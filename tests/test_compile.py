import importlib

import flet as ft


def test_ui_modules_import():
    for m in ("cq.ui.shell", "cq.ui.quizview", "cq.ui.bankview", "cq.ui.reports", "cq.ui.admin", "cq.ui.dashboard", "cq.ui.helpview"):
        importlib.import_module(m)


def test_menu_and_help_consistent():
    from cq.help_text import LESSONS, PAGES
    from cq.ui.shell import menu
    sids = {it[0] for g in menu() for it in g[3]}
    for lesson in LESSONS:
        for icon, tone, text, sid in lesson["steps"]:
            assert sid in sids, sid
            assert getattr(ft.Icons, icon)
    assert set(PAGES) <= sids
