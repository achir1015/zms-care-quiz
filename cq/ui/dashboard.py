"""首頁：題庫總數、我的成績、成長小圖、各單元題庫數、快速開始。"""
import datetime as dt

import flet as ft

from .. import rocdate
from . import theme as T
from .qview import line_chart

I = ft.Icons


def greet():
    h = dt.datetime.now().hour
    return "早安" if h < 11 else "午安" if h < 14 else "下午好" if h < 18 else "晚安"


class Dashboard(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        app = ctx.app
        u = b.user
        comp = b.company()
        s = b.bank_stats()
        t = s["total"]
        g = b.growth() if b.can("QUIZ", 1) else {"history": [], "units": [], "summary": {}}
        gs = g["summary"]
        hist = g["history"]
        hero = ft.Container(ft.Row([
            ft.Column([ft.Text("%s，%s" % (u["name"], greet()), size=24, weight=ft.FontWeight.W_800,
                               color=ft.Colors.WHITE),
                       ft.Text((comp.get("name") or "") + "　照顧服務員單一級技術士學科測驗練習", size=14,
                               color="#DCE6F5"),
                       ft.Row([hero_chip(I.CALENDAR_TODAY, rocdate.show(rocdate.today())),
                               hero_chip(I.LIBRARY_BOOKS, "題庫 %d 題" % t["usable"]),
                               hero_chip(I.EDIT_NOTE, "每次 %d 題" % (comp.get("quiz_size") or 100)),
                               hero_chip(I.FLAG, "及格 %d 分" % (comp.get("pass_score") or 60))], spacing=8, wrap=True),
                       ft.Row([T.btn("開始模擬測驗", I.PLAY_ARROW, lambda e: self.quick("MOCK"), bgcolor=T.GOLD),
                               T.btn("錯題複習", I.REPLAY, lambda e: self.quick("WRONG"), bgcolor="#2B5BA0")]
                              if b.can("QUIZ", 1) else [], spacing=10)],
                      spacing=8, expand=True),
            ft.Image(src="icon.png", width=110, height=110)]), padding=24, border_radius=20,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                       colors=[T.SIDEBAR_TOP, "#1E4D8C", "#0F766E"]))
        ks = T.kpis([
            T.kpi("總題庫數", str(t["usable"]), I.LIBRARY_BOOKS, "blue", "可出題",
                  lambda e: app.go("stats") if b.can("BANK", 1) else None),
            T.kpi("練習次數", str(gs.get("count", 0)), I.ASSIGNMENT_TURNED_IN, "teal", "我的紀錄",
                  lambda e: app.go("growth")),
            T.kpi("最近一次", "%g 分" % gs.get("last", 0), I.SCHEDULE, "amber",
                  T.show(hist[-1]["finished_at"]) if hist else "還沒練習", lambda e: app.go("growth")),
            T.kpi("最高分", "%g 分" % gs.get("best", 0), I.EMOJI_EVENTS, "violet", "平均 %g" % gs.get("avg", 0),
                  lambda e: app.go("growth")),
            T.kpi("待複習錯題", str(gs.get("wrong", 0)), I.REPLAY, "rose", "最近答錯的題目",
                  lambda e: self.quick("WRONG"))])
        chart = T.card(ft.Column([
            ft.Row([T.icon_tile(I.SHOW_CHART, "teal", 34), ft.Text("我的分數成長", size=16, weight=ft.FontWeight.W_700,
                                                                    expand=True),
                    T.btn("看全部", I.CHEVRON_RIGHT, lambda e: app.go("growth"), kind="ghost")]),
            line_chart([float(h["score"]) for h in hist[-15:]],
                       [rocdate.show(h["finished_at"].date())[4:] for h in hist[-15:]], width=560, height=220,
                       pass_line=int(comp.get("pass_score") or 60)) if hist else
            T.empty_state(I.SHOW_CHART, "還沒有成績", "按「開始模擬測驗」做第一份 100 題")], spacing=8),
            padding=18, expand=3)
        top = max([x["usable"] for x in s["units"]] or [1]) or 1
        units = T.card(ft.Column([
            ft.Row([T.icon_tile(I.CATEGORY, "violet", 34), ft.Text("各單元題庫數", size=16, weight=ft.FontWeight.W_700)]),
            ft.Column([ft.Row([ft.Text("%s %s" % (x["code"], x["name"]), size=13, width=170, max_lines=1),
                               ft.Container(ft.Container(bgcolor=T.ACCENT if x["grp"] == "CARE" else "#8B5CF6",
                                                         width=max(2, 150 * x["usable"] / top), height=10,
                                                         border_radius=5), width=156),
                               ft.Text(str(x["usable"]), size=13, weight=ft.FontWeight.W_700)], spacing=8)
                       for x in s["units"] if x["usable"]] or [T.muted("尚未匯入題庫", 13)], spacing=7)],
            spacing=10), padding=18, expand=2)
        super().__init__([hero, ks, ft.Row([chart, units], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START,
                                           data="split")], spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)

    def quick(self, mode):
        aid = self.ctx.guard(self.ctx.books.start_quiz, mode)
        if aid:
            self.ctx.app.go("quiz", aid=aid)


def hero_chip(icon, text):
    return ft.Container(ft.Row([ft.Icon(icon, size=14, color="#DCE6F5"), ft.Text(text, size=12, color="#DCE6F5")],
                               spacing=4, tight=True), bgcolor="#22FFFFFF", border_radius=20,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4))
