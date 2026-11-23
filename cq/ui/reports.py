"""成績統計（全部使用者、最常答錯的題目）與測驗設定。"""
import flet as ft

from . import theme as T
from .qview import plain

I = ft.Icons


class Scores(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        names = b.unit_names()
        self.grid = T.Grid([("uid", "帳號", "s", 90), ("name", "姓名", "s", 100), ("dept", "班別", "s", 120),
                            ("n", "練習次數", "s", 70), ("last_s", "最近分數", "s", 70), ("best_s", "最高分", "s", 60),
                            ("avg_s", "平均", "s", 60), ("when", "最近練習", "s", 140)],
                           on_pick=lambda r: ctx.app.go("growth", uid=r["uid"]), height=330)
        rows = []
        for r in b.score_board():
            rows.append(dict(r, last_s="%g" % float(r["last_score"]) if r["last_score"] is not None else "",
                             best_s="%g" % float(r["best"]) if r["best"] is not None else "",
                             avg_s="%g" % float(r["avg"]) if r["avg"] is not None else "", when=T.show(r["last_at"])))
        self.grid.set_rows(rows)
        self.hard = T.Grid([("no", "題號", "s", 70), ("unit_s", "單元", "s", 120), ("stem_s", "題目", "s", 520),
                            ("n", "作答次數", "s", 70), ("rate", "答錯率", "s", 70)],
                           on_pick=lambda r: ctx.app.go("bank", open=r["id"]) if b.can("BANK", 1) else None,
                           height=330)
        hr = []
        for r in b.hard_questions():
            hr.append(dict(r, no=r["bank_no"] or "#%d" % r["id"], unit_s="%s %s" % (r["unit"], names.get(r["unit"], "")),
                           stem_s=plain(r["stem"]), rate="%g%%" % float(r["wrong_rate"])))
        self.hard.set_rows(hr)
        super().__init__([
            T.page_header(I.LEADERBOARD, "成績統計", "全部使用者的練習成績（點一列看該學員的成長圖表）", "violet",
                          [ctx.export_button(self.grid, "學員成績")]),
            self.grid,
            ft.Row([ft.Text("最常答錯的題目", size=16, weight=ft.FontWeight.W_700, expand=True),
                    ctx.export_button(self.hard, "常錯題目")]),
            self.hard], spacing=12, expand=True, scroll=ft.ScrollMode.AUTO)


class Settings(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        c = ctx.books.company()
        self.name = T.field("單位名稱（公司、機構或訓練班）", c.get("name") or "", width=420)
        self.size = T.field("每次測驗題數", c.get("quiz_size") or 100, width=150, suffix="題")
        self.pass_ = T.field("及格分數", c.get("pass_score") or 60, width=150, suffix="分")
        self.limit = T.field("測驗時間", c.get("time_limit") or 0, width=150, suffix="分鐘",
                             helper="0＝不限時")
        self.shuffle = T.switch("選項順序隨機換位置（正確答案跟著變）", c.get("shuffle_options", 1))
        self.ai_key = T.field("Claude API 金鑰（補產生 AI 解說用，可不填）", c.get("ai_key") or "", width=420,
                              password=True, can_reveal_password=True)
        self.ai_model = T.field("模型", c.get("ai_model") or "claude-opus-5-5", width=200)
        self.ai_msg = T.muted("", 12)
        self.ai_bar = ft.ProgressBar(value=0, visible=False, color=T.ACCENT, bgcolor="#E6F4F1", bar_height=8)
        self.old = T.switch("出題包含「歷屆試題才有」的舊題目（關掉＝只用最新題庫＋共同科目）", c.get("include_old", 1))
        super().__init__([
            T.page_header(I.TUNE, "測驗設定", "題數、及格分數、時間與出題範圍（所有使用者共用）", "pink",
                          [T.btn("儲存", I.SAVE, lambda e: self.save())]),
            T.card(ft.Column([
                self.name, ft.Row([self.size, self.pass_, self.limit], spacing=14, wrap=True),
                self.shuffle, self.old,
                T.muted("說明：正式學科測試是 80 題、100 分鐘；本系統依需求預設每次 100 題，每題 1 分。"
                        "選項換位時，「以上皆是／以上皆非」會固定在最後一個。", 12)], spacing=14), padding=22),
            T.card(ft.Column([
                ft.Row([T.icon_tile(I.AUTO_AWESOME, "violet", 34),
                        ft.Text("AI 試題解說", size=16, weight=ft.FontWeight.W_700)]),
                T.muted("內建題庫已附 AI 解說，不必設定也能用。之後匯入的新題目沒有解說時，填入 Claude API 金鑰，"
                        "按「補產生缺少的解說」由 AI 補上（會產生 API 費用，每題約幾毛錢）。", 12),
                ft.Row([self.ai_key, self.ai_model], spacing=14, wrap=True),
                ft.Row([T.btn("補產生缺少的解說", I.AUTO_AWESOME, lambda e: self.fill_ai(), kind="outline"), self.ai_msg],
                       spacing=12),
                self.ai_bar], spacing=12), padding=22)],
            spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)

    def save(self):
        self.ctx.guard(self.ctx.books.save_company, name=self.name.value, quiz_size=self.size.value,
                       pass_score=self.pass_.value, time_limit=self.limit.value, include_old=self.old.value,
                       shuffle_options=self.shuffle.value, ai_key=self.ai_key.value, ai_model=self.ai_model.value,
                       ok="測驗設定已儲存")

    def fill_ai(self):
        b = self.ctx.books
        self.save()
        ids = b.missing_explain_ids()
        if not ids:
            self.ai_msg.value = "所有題目都已有解說"
            self.update()
            return

        def work():
            self.ai_bar.visible = True
            ok = 0
            for i, qid in enumerate(ids):
                try:
                    b.ai_explain(qid)
                    ok += 1
                except Exception as ex:
                    self.ai_msg.value = "第 %d 題失敗：%s" % (i + 1, ex)
                    self.update()
                    break
                self.ai_bar.value = (i + 1) / len(ids)
                self.ai_msg.value = "已產生 %d／%d 題" % (ok, len(ids))
                self.update()
            self.ai_bar.visible = False
            self.update()
        self.ctx.page.run_thread(work)
