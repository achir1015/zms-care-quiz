"""單元複習：依單元瀏覽題庫，先自己想答案，再按「看答案與解說」；選項一樣隨機換位置，避免背位置。"""
import flet as ft

from . import theme as T
from .qview import LETTERS, explain_box, rich, speak_text_of

I = ft.Icons


class Review(ft.Column):
    PER_PAGE = 10

    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        opts = b.quiz_options()
        self.names = b.unit_names()
        units = [u for u in opts["units"] if u["n"]]
        self.unit = T.dropdown("單元", [(u["code"], "%s %s（%d 題）" % (u["code"], u["name"], u["n"])) for u in units],
                               kw.get("unit") or (units[0]["code"] if units else ""), width=300, blank="全部單元",
                               filterable=False, on_select=lambda e: self.load())
        self.kw = T.field("關鍵字", "", width=180, prefix_icon=I.SEARCH, on_submit=lambda e: self.load())
        self.show_all = T.switch("直接顯示答案", False, on_change=lambda e: self.render())
        self.wrong = T.switch("只看我的錯題", False, on_change=lambda e: self.load())
        self.list = ft.Column(spacing=12)
        self.info = T.muted("", 13)
        self.items, self.opened, self.page_no = [], set(), 0
        super().__init__([
            T.page_header(I.MENU_BOOK, "單元複習", "依單元瀏覽題庫：先想答案，再看正確答案與 AI 解說（可朗讀）", "teal",
                          [T.btn("開始這個單元的練習", I.PLAY_ARROW, lambda e: self.practice(), kind="accent")]),
            ft.Row([self.unit, self.kw, self.show_all, self.wrong, self.info], wrap=True, spacing=14,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.list], spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)
        self.load(refresh=False)

    def load(self, refresh=True):
        self.items = self.ctx.books.review_items(self.unit.value or "", self.kw.value or "", bool(self.wrong.value))
        self.opened, self.page_no = set(), 0
        self.render(refresh)

    def render(self, refresh=True):
        n = len(self.items)
        pages = max(1, (n + self.PER_PAGE - 1) // self.PER_PAGE)
        self.page_no = max(0, min(self.page_no, pages - 1))
        part = self.items[self.page_no * self.PER_PAGE:(self.page_no + 1) * self.PER_PAGE]
        self.info.value = "共 %d 題　第 %d／%d 頁" % (n, self.page_no + 1, pages)
        rows = [self.card(it) for it in part] or [T.empty_state(I.MENU_BOOK, "沒有符合的題目")]
        if part:
            rows.append(ft.Row([
                T.btn("上一頁", I.CHEVRON_LEFT, lambda e: self.turn(-1), kind="outline", disabled=self.page_no == 0),
                T.muted("第 %d／%d 頁" % (self.page_no + 1, pages), 13),
                T.btn("下一頁", I.CHEVRON_RIGHT, lambda e: self.turn(1), kind="outline",
                      disabled=self.page_no >= pages - 1)], alignment=ft.MainAxisAlignment.CENTER, spacing=16))
        self.list.controls = rows
        if refresh:
            self.update()

    def turn(self, d):
        self.page_no += d
        self.render()
        self.ctx.page.run_task(self.scroll_to, offset=0, duration=0)

    def card(self, it):
        show = bool(self.show_all.value) or it["seq"] in self.opened
        opts = []
        for i, text in enumerate(it["options"], start=1):
            right = show and it["correct_pos"] == i
            row = [ft.Container(ft.Text(LETTERS[i - 1], size=14, weight=ft.FontWeight.W_800,
                                        color=ft.Colors.WHITE if right else T.TEXT), width=30, height=30,
                                border_radius=15, bgcolor=T.SUCCESS if right else "#EEF2F7",
                                alignment=ft.Alignment.CENTER),
                   rich(self.ctx, text, 15)]
            if right:
                row.append(ft.Icon(I.CHECK, color=T.SUCCESS))
            opts.append(ft.Container(ft.Row(row, spacing=12), padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                     border_radius=10, bgcolor="#E8F7EE" if right else "#FBFCFE",
                                     border=ft.Border.all(1, "#86D3A3" if right else "#DCE3EC")))
        answer = it["options"][it["correct_pos"] - 1]
        if show:
            foot = explain_box(self.ctx, it["explain"],
                               lambda it=it, a=answer: speak_text_of(it["stem"], a, it["explain"]))
        else:
            foot = ft.Row([T.btn("看答案與解說", I.VISIBILITY, lambda e, s=it["seq"]: self.reveal(s), kind="outline")])
        return ft.Container(ft.Column([
            ft.Row([ft.Container(ft.Text(it["bank_no"] or "#%d" % it["qid"], size=12, color=ft.Colors.WHITE,
                                         weight=ft.FontWeight.W_700), bgcolor=T.PRIMARY, border_radius=8,
                                 padding=ft.Padding.symmetric(horizontal=10, vertical=3)),
                    T.chip("%s %s" % (it["unit"], self.names.get(it["unit"], "")), "slate", size=11)], spacing=8),
            rich(self.ctx, it["stem"], 16, weight=ft.FontWeight.W_500),
            ft.Column(opts, spacing=8), foot], spacing=10), padding=18, bgcolor=T.CARD, border_radius=14,
            border=ft.Border.all(1, T.LINE))

    def reveal(self, seq):
        self.opened.add(seq)
        self.render()

    def practice(self):
        u = self.unit.value or ""
        aid = self.ctx.guard(self.ctx.books.start_quiz, "UNIT" if u else "MOCK", unit=u)
        if aid:
            self.ctx.app.go("quiz", aid=aid)
