"""測驗畫面：選擇測驗方式 → 作答（100 題、選項隨機換位置）→ 交卷評分與檢討；我的成績與成長圖表。"""
import asyncio
import time

import flet as ft

from .. import rocdate
from ..seed import MODES
from . import theme as T
from .qview import LETTERS, line_chart, plain, rate_bar, rich

I = ft.Icons
MODE_STYLE = {"MOCK": (I.ASSIGNMENT, "blue"), "UNIT": (I.CATEGORY, "teal"), "YEAR": (I.HISTORY_EDU, "violet"),
              "WRONG": (I.REPLAY, "rose")}


def Quiz(ctx, aid=None, review=None, **kw):
    """選單「開始測驗」：有 aid 就直接進作答／檢討畫面。"""
    if aid or review:
        return QuizRun(ctx, aid or review)
    return QuizStart(ctx)


# ====================================================================== 選擇測驗方式
class QuizStart(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        b = ctx.books
        o = b.quiz_options()
        self.opt = o
        size = o["size"]
        units = [u for u in o["units"] if u["n"]]
        self.unit = T.dropdown("選擇單元", [(u["code"], "%s %s（%d 題）" % (u["code"], u["name"], u["n"])) for u in units],
                               units[0]["code"] if units else None, width=330, filterable=False)
        self.year = T.dropdown("選擇年度", [(y["id"], "%s 年度（%d 題）" % (y["year"], y["n"])) for y in o["years"]],
                               o["years"][0]["id"] if o["years"] else None, width=330, filterable=False)
        cards = [
            self.mode_card("MOCK", "模擬測驗", "從整個題庫依各單元題數比例隨機抽 %d 題，最像正式考試" % size,
                           [T.chip("每題 1 分，滿分 100", "blue", I.STARS)], "開始模擬測驗"),
            self.mode_card("UNIT", "單元練習", "針對某一個單元加強，隨機抽 %d 題（單元題數不足時全部出）" % size,
                           [self.unit], "開始單元練習"),
            self.mode_card("YEAR", "歷屆試題", "照該年度學科測試的原題目出題（選項一樣隨機換位置）",
                           [self.year], "開始歷屆試題", disabled=not o["years"]),
            self.mode_card("WRONG", "錯題複習", "把你最近一次答錯、還沒答對的題目再做一次（最多 %d 題）" % size,
                           [T.chip("目前錯題 %d 題" % o["wrong"], "rose", I.ERROR_OUTLINE)], "開始錯題複習",
                           disabled=not o["wrong"]),
        ]
        top = []
        if o["open"]:
            t = o["open"]
            top.append(ft.Container(ft.Row([
                ft.Icon(I.PENDING_ACTIONS, color="#B45309"),
                ft.Text("你有一份還沒交卷的%s（%d 題，%s 開始）" % (MODES.get(t["mode"], ""), t["q_count"],
                                                         T.show(t["started_at"])), size=14, expand=True),
                T.btn("繼續作答", I.PLAY_ARROW, lambda e: ctx.app.go("quiz", aid=t["id"]), kind="accent"),
                T.btn("放棄", I.DELETE_OUTLINE, lambda e: self.abandon(t["id"]), kind="ghost")]),
                bgcolor="#FFF7E6", border=ft.Border.all(1, "#F5D9A8"), border_radius=14, padding=14))
        if not o["total"]:
            top.append(T.card(T.empty_state(I.UPLOAD_FILE, "題庫還沒有題目",
                                            "請由「題庫 → 匯入學科測驗 PDF」匯入題庫參考資料與歷屆試題"), padding=10))
        intro = T.card(ft.Column([
            ft.Row([T.icon_tile(I.LIGHTBULB_OUTLINE, "amber", 34), ft.Text("測驗說明", size=16, weight=ft.FontWeight.W_700)]),
            *[ft.Text(s, size=13, color=T.TEXT) for s in (
                "1. 每次從題庫隨機抽取 %d 題，每題 1 分，滿分 100 分（及格 %d 分）。" % (size, b.company().get("pass_score") or 60),
                "2. 選項順序每次都會隨機換位置，例如原本的 (A) 可能變成 (B)，正確答案跟著變，要看懂內容才答得對。",
                "3. 點選選項即可作答，再點其他選項可以更改；作答會自動儲存，關掉程式下次可以繼續。",
                "4. 完成後按「交卷」評分，未作答的題目視為答錯；交卷後可看每題正確答案與各單元答對率。",
                "5. 每次成績都會記錄下來，「我的成績與成長」可看成長圖表與錯題。")]], spacing=6), padding=18)
        super().__init__([
            T.page_header(I.EDIT_NOTE, "開始測驗", "題庫共 %d 題可出題　·　每次 %d 題" % (o["total"], size), "blue",
                          [T.btn("我的成績與成長", I.SHOW_CHART, lambda e: ctx.app.go("growth"), kind="outline")]),
            *top,
            ft.ResponsiveRow([ft.Container(c, col={"xs": 12, "md": 6}) for c in cards], spacing=14, run_spacing=14),
            intro], spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)

    def mode_card(self, mode, title, desc, extra, button, disabled=False):
        icon, tone = MODE_STYLE[mode]
        return T.card(ft.Column([
            ft.Row([T.icon_tile(icon, tone, 48, radius=14),
                    ft.Column([ft.Text(title, size=18, weight=ft.FontWeight.W_800), T.muted(desc, 12)], spacing=2,
                              expand=True)], spacing=14),
            ft.Row(extra, wrap=True),
            ft.Row([T.btn(button, I.PLAY_ARROW, lambda e: self.start(mode), disabled=disabled,
                          kind="accent" if mode == "MOCK" else "primary")], alignment=ft.MainAxisAlignment.END)],
            spacing=12), padding=20, height=210)

    def start(self, mode):
        kw = {}
        if mode == "UNIT":
            kw["unit"] = self.unit.value or ""
        if mode == "YEAR":
            kw["source_id"] = int(self.year.value or 0)
        aid = self.ctx.guard(self.ctx.books.start_quiz, mode, **kw)
        if aid:
            self.ctx.app.go("quiz", aid=aid)

    def abandon(self, aid):
        def go():
            self.ctx.books.abandon(aid)
            self.ctx.app.go("quiz")
        self.ctx.confirm("放棄這份測驗", "作答內容會刪除，確定嗎？", go, yes="放棄")


# ====================================================================== 作答與檢討
class QuizRun(ft.Row):
    def __init__(self, ctx, aid):
        self.ctx = ctx
        self.aid = aid
        self.data_ = ctx.books.attempt(aid)
        t = self.data_["attempt"]
        self.items = self.data_["items"]
        self.done = self.data_["done"]
        self.answers = {it["seq"]: it["chosen"] for it in self.items}
        self.t0 = time.time() - (0 if self.done else self._elapsed(t))
        c = ctx.books.company()
        self.limit = int(c.get("time_limit") or 0) * 60
        self.filter = "all"
        self.unit_names = ctx.books.unit_names()
        self.cards = {}
        self.list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self.nav = ft.Row(wrap=True, spacing=6, run_spacing=6)
        self.progress = ft.Text("", size=14, weight=ft.FontWeight.W_700)
        self.bar = ft.ProgressBar(value=0, color=T.ACCENT, bgcolor="#E6F4F1", bar_height=8, border_radius=4)
        self.timer = ft.Text("", size=22, weight=ft.FontWeight.W_800, color=T.PRIMARY)
        self.result_box = ft.Column(spacing=10)
        title = "%s%s" % (MODES.get(t["mode"], "測驗"), ("　" + self.unit_names.get(t["unit"], "")) if t["unit"] else "")
        self.title = title
        side = ft.Container(ft.Column([
            ft.Text(title, size=16, weight=ft.FontWeight.W_800),
            T.muted("%d 題　·　%s" % (t["q_count"], T.show(t["started_at"])), 12),
            ft.Divider(height=8, color=T.LINE),
            ft.Row([ft.Icon(I.TIMER_OUTLINED, color=T.PRIMARY), self.timer]),
            self.progress, self.bar,
            self.filter_row(),
            ft.Container(ft.Column([self.nav], scroll=ft.ScrollMode.AUTO), expand=True),
            self.action_row()], spacing=10), width=300, padding=16, bgcolor=T.CARD, border_radius=16,
            border=ft.Border.all(1, T.LINE))
        super().__init__([ft.Column([self.result_box, self.list], expand=True, spacing=12), side],
                         expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.render(refresh=False)
        if self.done:
            self.show_result(refresh=False)
        else:
            ctx.page.run_task(self.tick)

    @staticmethod
    def _elapsed(t):
        import datetime as dt
        try:
            return max(0, (dt.datetime.now() - t["started_at"]).total_seconds())
        except Exception:
            return 0

    # ---------------------------------------------------------------- 右側工具
    def filter_row(self):
        opts = [("all", "全部")] + ([("wrong", "答錯"), ("right", "答對")] if self.done else [("todo", "未作答")])
        self.seg = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=ft.Text(t, size=12)) for k, t in opts], selected=["all"],
            on_change=self.on_filter, show_selected_icon=False)
        return self.seg

    def action_row(self):
        if self.done:
            return ft.Column([
                T.btn("再做一份同樣方式", I.REPLAY, lambda e: self.again(), kind="accent", width=268),
                T.btn("我的成績與成長", I.SHOW_CHART, lambda e: self.ctx.app.go("growth"), kind="outline", width=268)],
                spacing=8)
        return ft.Column([
            T.btn("交卷", I.TASK_ALT, lambda e: self.ask_submit(), kind="accent", width=268),
            T.btn("先離開（作答已儲存）", I.LOGOUT, lambda e: self.ctx.app.go("quiz"), kind="ghost", width=268)],
            spacing=8)

    def on_filter(self, e):
        self.filter = (self.seg.selected or ["all"])[0]
        self.page_no = 0
        self.render()

    # ---------------------------------------------------------------- 題目卡片（一頁 10 題，畫面才快）
    PER_PAGE = 10

    def shown(self):
        out = []
        for it in self.items:
            ch = self.answers.get(it["seq"], 0)
            if self.filter == "todo" and ch:
                continue
            if self.filter == "wrong" and it.get("is_correct"):
                continue
            if self.filter == "right" and not it.get("is_correct"):
                continue
            out.append(it)
        return out

    def render(self, refresh=True, top=True):
        self.cards = {}
        items = self.shown()
        pages = max(1, (len(items) + self.PER_PAGE - 1) // self.PER_PAGE)
        self.page_no = max(0, min(getattr(self, "page_no", 0), pages - 1))
        part = items[self.page_no * self.PER_PAGE:(self.page_no + 1) * self.PER_PAGE]
        rows = []
        for it in part:
            card = self.card(it)
            self.cards[it["seq"]] = card
            rows.append(card)
        if not rows:
            rows = [T.empty_state(I.TASK_ALT, "沒有符合的題目")]
        else:
            last = self.page_no == pages - 1
            pager = ft.Row([
                T.btn("上一頁", I.CHEVRON_LEFT, lambda e: self.goto_page(self.page_no - 1), kind="outline",
                      disabled=self.page_no == 0),
                T.muted("第 %d／%d 頁（第 %d～%d 題）" % (self.page_no + 1, pages, part[0]["seq"], part[-1]["seq"]), 13),
                T.btn("下一頁", I.CHEVRON_RIGHT, lambda e: self.goto_page(self.page_no + 1), kind="outline",
                      disabled=last) if not (last and not self.done) else
                T.btn("交卷", I.TASK_ALT, lambda e: self.ask_submit(), kind="accent")],
                alignment=ft.MainAxisAlignment.CENTER, spacing=16)
            rows.append(ft.Container(pager, padding=ft.Padding.only(top=4, bottom=12)))
        self.list.controls = rows
        self.render_nav()
        if refresh:
            self.update()
            if top:
                self.ctx.page.run_task(self.list.scroll_to, offset=0, duration=0)

    def goto_page(self, n):
        self.page_no = n
        self.render()

    def card(self, it):
        seq = it["seq"]
        ch = self.answers.get(seq, 0)
        opts = []
        for i, text in enumerate(it["options"], start=1):
            opts.append(self.option(it, i, text, ch))
        head = [ft.Container(ft.Text("第 %d 題" % seq, size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_700),
                             bgcolor=T.PRIMARY, border_radius=8, padding=ft.Padding.symmetric(horizontal=10, vertical=3)),
                T.chip("%s %s" % (it["unit"], self.unit_names.get(it["unit"], "")), "slate", size=11)]
        border_color = T.LINE
        bg = T.CARD
        if self.done:
            ok = it.get("is_correct")
            head.append(T.chip("答對" if ok else ("未作答" if not ch else "答錯"), "green" if ok else "rose",
                               I.CHECK_CIRCLE if ok else I.CANCEL))
            border_color = "#9AD8B0" if ok else "#F3B4B4"
            bg = "#F6FFF9" if ok else "#FFF7F7"
        elif ch:
            border_color = "#9CC7C1"
        return ft.Container(ft.Column([
            ft.Row(head, spacing=8),
            rich(self.ctx, it["stem"], 16, weight=ft.FontWeight.W_500),
            ft.Column(opts, spacing=8)], spacing=10), padding=18, bgcolor=bg, border_radius=14,
            border=ft.Border.only(left=ft.BorderSide(4, border_color), top=ft.BorderSide(1, T.LINE),
                                  right=ft.BorderSide(1, T.LINE), bottom=ft.BorderSide(1, T.LINE)),
            key=ft.ScrollKey("q%d" % seq))

    def option(self, it, i, text, ch):
        sel = ch == i
        mark_bg, mark_fg, bg, bd = "#EEF2F7", T.TEXT, "#FBFCFE", "#DCE3EC"
        tail = None
        if self.done:
            right = it.get("correct_pos") == i
            if right:
                mark_bg, mark_fg, bg, bd = T.SUCCESS, ft.Colors.WHITE, "#E8F7EE", "#86D3A3"
                tail = ft.Row([ft.Icon(I.CHECK, color=T.SUCCESS, size=18),
                               ft.Text("正確答案", size=12, color=T.SUCCESS, weight=ft.FontWeight.W_700)], spacing=2)
            elif sel:
                mark_bg, mark_fg, bg, bd = T.DANGER, ft.Colors.WHITE, "#FDECEC", "#F3A9A9"
                tail = ft.Row([ft.Icon(I.CLOSE, color=T.DANGER, size=18),
                               ft.Text("你的答案", size=12, color=T.DANGER, weight=ft.FontWeight.W_700)], spacing=2)
        elif sel:
            mark_bg, mark_fg, bg, bd = T.ACCENT, ft.Colors.WHITE, "#E3F6F3", T.ACCENT
        row = [ft.Container(ft.Text(LETTERS[i - 1], size=14, weight=ft.FontWeight.W_800, color=mark_fg), width=30,
                            height=30, border_radius=15, bgcolor=mark_bg, alignment=ft.Alignment.CENTER),
               rich(self.ctx, text, 15)]
        if tail:
            row.append(tail)
        return ft.Container(ft.Row(row, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=9), bgcolor=bg, border_radius=10,
                            border=ft.Border.all(1.5 if sel else 1, bd), ink=not self.done,
                            on_click=None if self.done else (lambda e, s=it["seq"], i=i: self.pick(s, i)))

    def pick(self, seq, i):
        cur = self.answers.get(seq, 0)
        self.answers[seq] = 0 if cur == i else i               # 再點一次同一個選項＝取消
        try:
            self.ctx.books.answer(self.aid, seq, self.answers[seq])
        except Exception as ex:
            self.ctx.toast(str(ex), True)
            return
        it = next(x for x in self.items if x["seq"] == seq)
        if seq in self.cards:
            new = self.card(it)
            idx = self.list.controls.index(self.cards[seq])
            self.list.controls[idx] = new
            self.cards[seq] = new
            self.list.update()
        self.render_nav(only=seq)
        self.nav_cells[seq].update()
        self.progress.update()
        self.bar.update()

    def _cell_style(self, it):
        ch = self.answers.get(it["seq"], 0)
        if self.done:
            return (T.SUCCESS, ft.Colors.WHITE) if it.get("is_correct") else ("#F87171", ft.Colors.WHITE)
        return (T.ACCENT, ft.Colors.WHITE) if ch else ("#EEF2F7", T.TEXT)

    def render_nav(self, only=None):
        """右側題號格：只建立一次，之後只改顏色（每點一次不必重送 100 格）。"""
        n = len(self.items)
        answered = sum(1 for v in self.answers.values() if v)
        if not getattr(self, "nav_cells", None):
            self.nav_cells = {}
            for it in self.items:
                bg, fg = self._cell_style(it)
                self.nav_cells[it["seq"]] = ft.Container(
                    ft.Text(str(it["seq"]), size=11, color=fg, weight=ft.FontWeight.W_600), width=38, height=28,
                    bgcolor=bg, border_radius=6, alignment=ft.Alignment.CENTER,
                    on_click=lambda e, s=it["seq"]: self.jump(s), ink=True)
            self.nav.controls = list(self.nav_cells.values())
        else:
            for it in self.items:
                if only and it["seq"] != only:
                    continue
                bg, fg = self._cell_style(it)
                c = self.nav_cells[it["seq"]]
                c.bgcolor, c.content.color = bg, fg
        on_page = set(self.cards)
        for s, c in self.nav_cells.items():
            c.border = ft.Border.all(2, T.PRIMARY) if s in on_page else None
        if self.done:
            t = self.data_["attempt"]
            self.progress.value = "答對 %d／%d 題" % (t["correct"], t["q_count"])
            self.bar.value = (t["correct"] / t["q_count"]) if t["q_count"] else 0
            self.timer.value = "%s 分" % ("%g" % float(t["score"]))
        else:
            self.progress.value = "已作答 %d／%d 題" % (answered, n)
            self.bar.value = answered / n if n else 0

    def jump(self, seq):
        if seq not in self.cards:
            items = self.shown()
            if not any(it["seq"] == seq for it in items):
                self.seg.selected = ["all"]
                self.filter = "all"
                items = self.items
            pos = next(i for i, it in enumerate(items) if it["seq"] == seq)
            self.page_no = pos // self.PER_PAGE
            self.render(top=False)
        self.ctx.page.run_task(self._scroll_to, seq)

    async def _scroll_to(self, seq):
        await asyncio.sleep(0.15)                         # 等新的一頁畫好再捲
        await self.list.scroll_to(scroll_key="q%d" % seq, duration=300)

    # ---------------------------------------------------------------- 計時、交卷
    async def tick(self):
        while not self.done:
            try:
                if self.page is None:
                    return
            except Exception:
                return
            sec = int(time.time() - self.t0)
            if self.limit:
                left = max(0, self.limit - sec)
                self.timer.value = "剩 %02d:%02d" % (left // 60, left % 60)
                self.timer.color = T.DANGER if left < 300 else T.PRIMARY
                if left == 0:
                    self.ctx.toast("時間到，自動交卷")
                    self.submit()
                    return
            else:
                self.timer.value = "%02d:%02d" % (sec // 60, sec % 60)
            try:
                self.timer.update()
            except Exception:
                return
            await asyncio.sleep(1)

    def ask_submit(self):
        left = sum(1 for v in self.answers.values() if not v)
        msg = "還有 %d 題沒作答，未作答視為答錯。確定要交卷嗎？" % left if left else "全部都作答了，確定要交卷嗎？"
        self.ctx.confirm("交卷", msg, self.submit, yes="交卷", danger=bool(left))

    def submit(self):
        r = self.ctx.guard(self.ctx.books.submit, self.aid, int(time.time() - self.t0), self.answers)
        if not r:
            return
        self.ctx.app.go("quiz", review=self.aid)
        self.ctx.say_text(result_speech(r))

    def again(self):
        t = self.data_["attempt"]
        aid = self.ctx.guard(self.ctx.books.start_quiz, t["mode"], unit=t["unit"], source_id=t["source_id"])
        if aid:
            self.ctx.app.go("quiz", aid=aid)

    def show_result(self, refresh=True):
        r = self.ctx.books.result(self.aid)
        t = r["attempt"]
        score = float(t["score"])
        ok = r["pass"]
        units = [rate_bar("%s %s" % (u["unit"], u["name"] or ""), round(int(u["ok"] or 0) * 100.0 / u["n"], 1),
                          sub="%d／%d 題" % (int(u["ok"] or 0), u["n"]), width=230) for u in r["by_unit"]]
        mins = int(t["seconds"] or 0) // 60
        self.result_box.controls = [ft.Container(ft.Row([
            ft.Container(ft.Column([ft.Text("%g" % score, size=46, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                                    ft.Text("分", size=14, color="#DCE6F5")], spacing=0,
                                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                         width=130, height=130, border_radius=65, alignment=ft.Alignment.CENTER,
                         bgcolor=T.SUCCESS if ok else T.DANGER),
            ft.Column([
                ft.Text(("恭喜及格！" if ok else "再加油！") + "　及格分數 %d" % r["pass_score"], size=20,
                        weight=ft.FontWeight.W_800, color=T.SUCCESS if ok else T.DANGER),
                ft.Row([T.chip("答對 %d" % t["correct"], "green", I.CHECK_CIRCLE),
                        T.chip("答錯 %d" % (t["answered"] - t["correct"]), "rose", I.CANCEL),
                        T.chip("未作答 %d" % (t["q_count"] - t["answered"]), "amber", I.HELP_OUTLINE),
                        T.chip("用時 %d 分鐘" % mins, "slate", I.TIMER_OUTLINED),
                        T.chip(T.show(t["finished_at"]), "slate", I.EVENT)], wrap=True, spacing=6),
                ft.Row(units, wrap=True, spacing=18, run_spacing=10)], spacing=10, expand=True)], spacing=22),
            padding=20, bgcolor=T.CARD, border_radius=16, border=ft.Border.all(1, T.LINE))]
        if refresh:
            self.update()


def result_speech(r):
    t = r["attempt"]
    s = "交卷完成。你這次得到 %g 分，答對 %d 題。" % (float(t["score"]), t["correct"])
    s += "恭喜及格！" if r["pass"] else "還差一點，繼續加油！"
    weak = sorted(r["by_unit"], key=lambda u: int(u["ok"] or 0) / u["n"])[:1]
    if weak and weak[0]["n"] >= 3 and int(weak[0]["ok"] or 0) / weak[0]["n"] < 0.8:
        s += "答對率最低的是%s，可以用單元練習加強。" % weak[0]["name"]
    return s


# ====================================================================== 我的成績與成長
class Growth(ft.Column):
    def __init__(self, ctx, uid=None, **kw):
        self.ctx = ctx
        b = ctx.books
        uid = uid or b.uid
        g = b.growth(uid)
        s = g["summary"]
        hist = g["history"]
        who = b.user["name"] if uid == b.uid else next((u["name"] for u in b.users() if u["uid"] == uid), uid)
        pass_score = int(b.company().get("pass_score") or 60)
        diff = s["last"] - s["first"] if s["count"] > 1 else 0
        ks = T.kpis([
            T.kpi("練習次數", str(s["count"]), I.ASSIGNMENT_TURNED_IN, "blue", "已交卷"),
            T.kpi("最近一次", "%g 分" % s["last"], I.SCHEDULE, "teal", T.show(hist[-1]["finished_at"]) if hist else ""),
            T.kpi("最高分", "%g 分" % s["best"], I.EMOJI_EVENTS, "amber", "平均 %g 分" % s["avg"]),
            T.kpi("成長", ("+%g" % diff) if diff >= 0 else "%g" % diff, I.TRENDING_UP if diff >= 0 else I.TRENDING_DOWN,
                  "green" if diff >= 0 else "rose", "第一次 → 最近一次"),
            T.kpi("待複習錯題", str(s["wrong"]), I.REPLAY, "rose", "按這裡開始錯題複習",
                  lambda e: self.start_wrong() if s["wrong"] else None)])
        labels = [rocdate.show(h["finished_at"].date())[4:] if h["finished_at"] else "" for h in hist]
        chart = T.card(ft.Column([
            ft.Row([T.icon_tile(I.SHOW_CHART, "teal", 34),
                    ft.Text("分數成長圖表", size=16, weight=ft.FontWeight.W_700, expand=True),
                    T.muted("每一點是一次交卷的成績（滿分 100）", 12)]),
            line_chart([float(h["score"]) for h in hist], labels, width=700, height=280,
                       pass_line=pass_score) if hist else
            T.empty_state(I.SHOW_CHART, "還沒有成績", "完成第一次測驗後，這裡會畫出你的成長曲線")], spacing=10),
            padding=18, expand=3)
        units = T.card(ft.Column([
            ft.Row([T.icon_tile(I.BAR_CHART, "violet", 34), ft.Text("各單元答對率", size=16, weight=ft.FontWeight.W_700)]),
            ft.Column([rate_bar("%s %s" % (u["unit"], u["name"] or ""), u["rate"], u["recent_rate"],
                                "共作答 %d 題" % u["n"]) for u in g["units"]] or
                      [T.muted("還沒有資料", 13)], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)], spacing=12),
            padding=18, expand=2, height=360)
        self.grid = T.Grid([("when", "交卷時間", "s", 150), ("mode_name", "方式", "s", 140), ("q_count", "題數", "s", 50),
                            ("correct", "答對", "s", 50), ("score_s", "分數", "s", 60), ("mins", "用時", "s", 70)],
                           on_pick=lambda r: ctx.app.go("quiz", review=r["id"]), height=300)
        rows = []
        for h in reversed(hist):
            rows.append(dict(h, when=T.show(h["finished_at"]), score_s="%g" % float(h["score"]),
                             mins="%d 分" % (int(h["seconds"] or 0) // 60),
                             mode_name=MODES.get(h["mode"], "") + (" " + (h["unit_name"] or "") if h["unit"] else "") +
                             (" %s年" % h["src_year"] if h["mode"] == "YEAR" and h["src_year"] else "")))
        self.grid.set_rows(rows)
        super().__init__([
            T.page_header(I.SHOW_CHART, "成績與成長" + ("" if uid == b.uid else "：" + who),
                          "%s 的練習紀錄、分數成長圖表與各單元答對率（點下方紀錄可看該次的每一題）" % who, "teal",
                          [T.btn("開始測驗", I.PLAY_ARROW, lambda e: ctx.app.go("quiz"), kind="accent")]
                          if uid == b.uid else None),
            ks, ft.Row([chart, units], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START, data="split"),
            ft.Text("練習紀錄", size=16, weight=ft.FontWeight.W_700), self.grid],
            spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)

    def start_wrong(self):
        aid = self.ctx.guard(self.ctx.books.start_quiz, "WRONG")
        if aid:
            self.ctx.app.go("quiz", aid=aid)


_ = plain
