"""題庫畫面：題庫瀏覽與維護（含圖片）、題庫統計（各單元、總數、每年度）、匯入學科測驗 PDF。"""
import os

import flet as ft

from . import theme as T
from .qview import LETTERS, plain, rich

I = ft.Icons
ORIGIN = {"BANK": ("題庫", "blue"), "EXAM": ("歷屆才有", "violet"), "MANUAL": ("手動新增", "amber")}
GRP_TONE = {"CARE": "teal", "COMMON": "violet", "OTHER": "slate"}


# ====================================================================== 題庫瀏覽與維護
class Bank(ft.Row):
    def __init__(self, ctx, open=None, **kw):
        self.ctx = ctx
        b = ctx.books
        self.can_edit = b.can("BANK", 2)
        units = b.units()
        self.unit_opts = [(u["code"], "%s %s" % (u["code"], u["name"])) for u in units]
        years = sorted({s["year"] for s in b.sources() if s["kind"] == "EXAM"}, reverse=True)
        self.unit = T.dropdown("單元", self.unit_opts, "", width=230, blank="全部單元", filterable=False,
                               on_select=lambda e: self.load())
        self.year = T.dropdown("出現年度", [(y, "%d 年度試題" % y) for y in years], "", width=160, blank="全部",
                               filterable=False, on_select=lambda e: self.load())
        self.status = T.dropdown("狀態", [("on", "出題中"), ("off", "停用／刪題"), ("img", "有圖片")], "", width=140,
                                 blank="全部", filterable=False, on_select=lambda e: self.load())
        self.origin = T.dropdown("來源", [(k, v[0]) for k, v in ORIGIN.items()], "", width=130, blank="全部",
                                 filterable=False, on_select=lambda e: self.load())
        self.kw = T.field("關鍵字", "", width=200, prefix_icon=I.SEARCH, on_submit=lambda e: self.load())
        self.grid = T.Grid([("no", "題號", "s", 70), ("unit_s", "單元", "s", 110), ("stem_s", "題目", "s", 430),
                            ("ans_s", "答案", "s", 40), ("years", "出現年度", "s", 150), ("origin_s", "來源", "s", 70),
                            ("state", "狀態", "s", 60)], on_pick=lambda r: self.show(r["id"]))
        self.detail = ft.Container(T.empty_state(I.TOUCH_APP, "點左邊的題目看內容", "題目、四個選項、正確答案、出現年度"),
                                   width=470, bgcolor=T.CARD, border_radius=16, border=ft.Border.all(1, T.LINE),
                                   padding=18)
        self.page_no = 0
        self.all_rows = []
        self.full = T.Grid(self.grid.cols)            # 匯出用：全部符合條件的題目（不顯示）
        self.pager = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=14)
        actions = [self.unit, self.year, self.status, self.origin, self.kw]
        if self.can_edit:
            actions.append(T.btn("新增題目", I.ADD, lambda e: self.edit(None)))
        left = ft.Column([
            T.page_header(I.LIBRARY_BOOKS, "題庫瀏覽與維護", "固定拆解：題目、四個選項、正確答案；出題時選項才隨機換位置",
                          "teal"),
            ft.Row(actions + [ctx.export_button(self.full, "題庫")], wrap=True, spacing=10, run_spacing=8),
            self.grid, self.pager], expand=True, spacing=12)
        super().__init__([left, ft.Column([self.detail], scroll=ft.ScrollMode.AUTO)], expand=True, spacing=16,
                         vertical_alignment=ft.CrossAxisAlignment.START)
        self.load(refresh=False)
        if open:
            self.show(int(open), refresh=False)

    def load(self, refresh=True):
        names = dict(self.unit_opts)
        rows = self.ctx.books.questions(self.unit.value or "", int(self.year.value or 0), self.kw.value or "",
                                        self.origin.value or "", self.status.value or "")
        for r in rows:
            r["no"] = r["bank_no"] or "#%d" % r["id"]
            r["unit_s"] = names.get(r["unit"], r["unit"])
            r["stem_s"] = plain(r["stem"])
            r["ans_s"] = "①②③④"[r["answer"] - 1]
            r["origin_s"] = ORIGIN.get(r["origin"], ("", ""))[0]
            r["state"] = "刪題" if r["deleted"] else ("出題中" if r["active"] else "停用")
            r["years"] = r["years"] or ""
        self.all_rows = rows
        self.full.data_rows = rows
        self.page_no = 0
        self.show_page(refresh)

    PAGE = 100

    def show_page(self, refresh=True):
        rows = self.all_rows
        pages = max(1, (len(rows) + self.PAGE - 1) // self.PAGE)
        self.page_no = max(0, min(self.page_no, pages - 1))
        a = self.page_no * self.PAGE
        self.grid.set_rows(rows[a:a + self.PAGE], [T.muted("（符合條件共 %d 題）" % len(rows), 12)])
        self.pager.controls = [
            T.btn("上一頁", I.CHEVRON_LEFT, lambda e: self.turn(-1), kind="outline", disabled=self.page_no == 0),
            T.muted("第 %d／%d 頁" % (self.page_no + 1, pages), 13),
            T.btn("下一頁", I.CHEVRON_RIGHT, lambda e: self.turn(1), kind="outline", disabled=self.page_no >= pages - 1)]
        self.pager.visible = pages > 1
        if refresh:
            self.update()

    def turn(self, d):
        self.page_no += d
        self.show_page()

    def show(self, qid, refresh=True):
        q = self.ctx.guard(self.ctx.books.question, qid)
        if not q:
            return
        names = dict(self.unit_opts)
        opts = []
        for i in range(1, 5):
            right = q["answer"] == i
            opts.append(ft.Container(ft.Row([
                ft.Container(ft.Text("①②③④"[i - 1], size=15, weight=ft.FontWeight.W_800,
                                     color=ft.Colors.WHITE if right else T.TEXT), width=30, height=30,
                             border_radius=15, bgcolor=T.SUCCESS if right else "#EEF2F7", alignment=ft.Alignment.CENTER),
                rich(self.ctx, q["opt%d" % i], 14)], spacing=10), padding=10, border_radius=10,
                bgcolor="#E8F7EE" if right else "#FBFCFE", border=ft.Border.all(1, "#86D3A3" if right else T.LINE)))
        ap = [ft.Row([T.chip("%s %s" % ("題庫" if a["kind"] == "BANK" else "%s 年度" % a["year"], ""), "blue"
                             if a["kind"] == "BANK" else "violet"),
                      T.muted("第 %d 題，原答案 (%d)" % (a["no"], a["orig_answer"]), 12)]) for a in q["appears"]]
        st = q["stats"] or {}
        n = int(st.get("n") or 0)
        o = ORIGIN.get(q["origin"], ("", "slate"))
        acts = []
        if self.can_edit:
            acts = [T.btn("修改", I.EDIT, lambda e: self.edit(q)),
                    T.btn("停用" if q["active"] else "啟用", I.BLOCK if q["active"] else I.CHECK_CIRCLE,
                          lambda e: self.toggle(q), kind="outline")]
        self.detail.content = ft.Column([
            ft.Row([T.chip(q["bank_no"] or "#%d" % q["id"], "blue", I.TAG), T.chip(names.get(q["unit"], q["unit"]), "teal"),
                    T.chip(o[0], o[1])] + ([T.chip("本題刪題", "rose")] if q["deleted"] else []) +
                   ([] if q["active"] else [T.chip("停用", "slate")]), wrap=True, spacing=6),
            rich(self.ctx, q["stem"], 16, weight=ft.FontWeight.W_600, expand=False),
            ft.Column(opts, spacing=8),
            ft.Divider(height=6, color=T.LINE),
            ft.Text("出現紀錄", size=14, weight=ft.FontWeight.W_700),
            ft.Column(ap or [T.muted("（手動新增）", 12)], spacing=4),
            T.muted("練習作答 %d 次，答對率 %s" % (n, ("%g%%" % round(int(st.get("ok") or 0) * 100.0 / n, 1)) if n else "—"),
                    12),
            T.muted("修改：%s %s" % (q["updated_by"], T.show(q["updated_at"])) if q["updated_by"] else "", 11),
            ft.Row(acts, spacing=10)], spacing=10)
        if refresh:
            self.update()

    def toggle(self, q):
        if self.ctx.guard(self.ctx.books.set_active, q["id"], not q["active"], ok="已更新"):
            self.load()
            self.show(q["id"])

    def edit(self, q):
        c = self.ctx
        q = q or {"id": 0, "unit": self.unit.value or "01", "stem": "", "opt1": "", "opt2": "", "opt3": "", "opt4": "",
                  "answer": 0, "active": 1}
        unit = T.dropdown("單元", self.unit_opts, q["unit"], width=260, filterable=False)
        stem = T.field("題目（圖片保留 [[img:編號]] 標記）", q["stem"], multiline=True, min_lines=2, max_lines=5)
        opts = [T.field("選項 %s" % "①②③④"[i], q["opt%d" % (i + 1)], multiline=True, max_lines=3) for i in range(4)]
        ans = ft.RadioGroup(value=str(q["answer"] or ""), content=ft.Row(
            [ft.Radio(value=str(i), label="①②③④"[i - 1]) for i in range(1, 5)]))
        active = T.switch("出題時使用", q["active"])

        def save(e):
            qid = c.guard(c.books.save_question, q["id"], unit.value, stem.value, [o.value for o in opts],
                          ans.value, active.value, ok="已儲存")
            if qid:
                c.close()
                self.load()
                self.show(qid)
        c.dialog("修改題目" if q["id"] else "新增題目", ft.Column([
            unit, stem, *opts, ft.Row([ft.Text("正確答案", size=14), ans]), active,
            T.muted("提醒：這裡存的是固定順序；出題時選項會隨機換位置，正確答案自動跟著變。", 12)],
            tight=True, spacing=10, scroll=ft.ScrollMode.AUTO, height=560),
            [T.btn("取消", kind="ghost", on_click=lambda e: c.close()), T.btn("儲存", I.SAVE, save)],
            icon=I.EDIT_NOTE, width=680)


# ====================================================================== 題庫統計
class Stats(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        s = b.bank_stats()
        t = s["total"]
        lb = s["latest_bank"]
        ks = T.kpis([
            T.kpi("總題庫數", str(t["usable"]), I.LIBRARY_BOOKS, "blue", "出題中（全部 %d 題）" % t["total"]),
            T.kpi("題庫參考資料", str(t["bank"]), I.MENU_BOOK, "teal", (lb["version"] if lb else "尚未匯入")),
            T.kpi("歷屆試題新增", str(t["exam_only"]), I.HISTORY_EDU, "violet", "題庫沒有、考卷有的題目"),
            T.kpi("曾經出現在考卷", str(t["appeared"]), I.FACT_CHECK, "amber", "題目"),
            T.kpi("圖形題", str(s["images"]), I.IMAGE, "pink", "張圖片")])
        top = max([u["usable"] for u in s["units"]] or [1]) or 1
        unit_rows = []
        for u in s["units"]:
            if not u["total"] and u["code"] == "99":
                continue
            unit_rows.append(ft.Row([
                T.chip(u["code"], GRP_TONE.get(u["grp"], "slate"), size=12),
                ft.Text(u["name"], size=14, width=170, max_lines=1),
                ft.Container(ft.Container(bgcolor=T.ACCENT if u["grp"] == "CARE" else "#8B5CF6", border_radius=5,
                                          width=max(2, 340 * u["usable"] / top), height=14), width=350),
                ft.Text(str(u["usable"]), size=15, weight=ft.FontWeight.W_800, width=50,
                        text_align=ft.TextAlign.RIGHT),
                T.muted("題庫 %d　歷屆 %d　手動 %d　停用 %d" % (u["bank"], u["exam_only"], u["manual"],
                                                       u["inactive"]), 12)], spacing=10))
        units_card = T.card(ft.Column([
            ft.Row([T.icon_tile(I.CATEGORY, "teal", 34), ft.Text("各單元題庫數", size=16, weight=ft.FontWeight.W_700,
                                                                  expand=True),
                    T.chip("總題庫數 %d" % t["usable"], "blue", I.FUNCTIONS)]),
            T.muted("01～06＝照顧服務員題庫工作項目；07～10＝技能檢定共同科目（只出現在歷屆試題，依關鍵字自動分類，可在題庫維護修改）", 12),
            *unit_rows], spacing=10), padding=20)
        self.ygrid = T.Grid([("year_s", "年度", "s", 70), ("kind_s", "種類", "s", 110), ("title", "名稱", "s", 230),
                             ("q_total", "拆出題數", "s", 70), ("q_new", "新增到題庫", "s", 80),
                             ("q_same", "題庫已有", "s", 70), ("rate", "新題比例", "s", 70)], height=300)
        rows = []
        for r in s["sources"]:
            rows.append(dict(r, year_s=str(r["year"] or ""), kind_s="題庫參考資料" if r["kind"] == "BANK" else "學科測試試題",
                             rate="%d%%" % round(r["q_new"] * 100 / r["q_total"]) if r["q_total"] else ""))
        self.ygrid.set_rows(rows)
        # 每年度考卷各單元題數
        names = b.unit_names()
        mat = {}
        for r in b.year_matrix():
            mat.setdefault(r["year"], {})[r["unit"]] = r["n"]
        codes = [u["code"] for u in s["units"] if any(u["code"] in v for v in mat.values())]
        cols = [("year", "年度", "s", 60)] + [(c, names.get(c, c)[:6], "s", 64) for c in codes]
        self.mgrid = T.Grid(cols, height=300)
        self.mgrid.set_rows([dict({"year": y}, **{c: v.get(c, "") for c in codes}) for y, v in sorted(mat.items())])
        super().__init__([
            T.page_header(I.INSIGHTS, "題庫統計", "各單元題庫數、總題庫數、每年度新增題數", "amber",
                          [ctx.export_button(self.ygrid, "各年度題數")]),
            ks, units_card,
            ft.Row([ft.Column([ft.Text("各年度匯入與新增題數", size=16, weight=ft.FontWeight.W_700), self.ygrid],
                              expand=1, spacing=8),
                    ft.Column([ft.Text("每年度考卷各單元題數", size=16, weight=ft.FontWeight.W_700), self.mgrid],
                              expand=1, spacing=8)], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START,
                   data="split")], spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)


# ====================================================================== 匯入 PDF
class Import(ft.Column):
    running = False

    def __init__(self, ctx, **kw):
        self.ctx = ctx
        self.msg = ft.Column(spacing=8)
        self.bar = ft.ProgressBar(value=0, visible=False, color=T.ACCENT, bgcolor="#E6F4F1", bar_height=8,
                                  border_radius=4)
        self.grid = T.Grid([("year_s", "年度", "s", 60), ("kind_s", "種類", "s", 110), ("title", "名稱", "s", 200),
                            ("file_name", "檔名", "s", 250), ("q_total", "題數", "s", 50), ("q_new", "新增", "s", 50),
                            ("q_same", "已有", "s", 50), ("when", "匯入時間", "s", 140)],
                           on_pick=lambda r: self.source_menu(r))
        steps = [(I.UPLOAD_FILE, "blue", "選擇 PDF", "可一次選多份：題庫參考資料（178004A13…）與每年度學科測試試題"),
                 (I.CONTENT_CUT, "teal", "自動拆題", "依題號切出題目、①②③④ 四個選項與正確答案；圖片一起存進資料庫"),
                 (I.COMPARE_ARROWS, "violet", "比對題庫", "題庫已有的只記錄「這年度有考」，新題目加進題庫並自動判斷單元"),
                 (I.INSIGHTS, "amber", "更新統計", "各單元題庫數、總題庫數、每年度新增題數馬上更新")]
        super().__init__([
            T.page_header(I.UPLOAD_FILE, "匯入學科測驗 PDF", "每年的學科測驗 PDF 匯入後自動拆題、增加題庫", "blue",
                          [T.btn("選擇 PDF 匯入", I.UPLOAD_FILE, self.pick, kind="accent"),
                           T.btn("重新判斷單元", I.AUTO_FIX_HIGH, lambda e: self.reclassify(), kind="outline")]),
            ft.Row([T.card(ft.Row([T.icon_tile(ic, tone, 42), ft.Column([
                ft.Text(t, size=15, weight=ft.FontWeight.W_700), T.muted(d, 12)], spacing=2, expand=True)],
                spacing=12), padding=14, expand=True) for ic, tone, t, d in steps], spacing=12, data="split"),
            self.bar, self.msg,
            ft.Text("已匯入的 PDF（點一列可刪除）", size=16, weight=ft.FontWeight.W_700), self.grid],
            spacing=14, expand=True)
        self.load(refresh=False)

    def load(self, refresh=True):
        rows = self.ctx.books.sources()
        for r in rows:
            r["year_s"] = str(r["year"] or "")
            r["kind_s"] = "題庫參考資料" if r["kind"] == "BANK" else "學科測試試題"
            r["when"] = T.show(r["imported_at"])
        self.grid.set_rows(rows)
        if refresh:
            self.update()

    async def pick(self, e):
        if Import.running:
            self.ctx.toast("正在匯入中，請稍候", True)
            return
        files = await ft.FilePicker().pick_files(dialog_title="選擇學科測驗 PDF（可多選）", allowed_extensions=["pdf"],
                                                 allow_multiple=True, with_data=self.ctx.web)
        if not files:
            return
        items = []
        for f in files:
            if f.bytes:
                items.append((f.name, bytes(f.bytes)))
            elif f.path and os.path.isfile(f.path):
                with open(f.path, "rb") as fh:
                    items.append((f.name or os.path.basename(f.path), fh.read()))
        # 題庫參考資料先匯入（歷屆試題才比對得到單元）
        items.sort(key=lambda x: (0 if ("學科.pdf" in x[0] or "A1" in x[0] or "參考" in x[0]) else 1, x[0]))
        self.ctx.page.run_thread(self.work, items)

    def work(self, items):
        Import.running = True
        self.bar.visible = True
        self.msg.controls = []
        self.update()
        total_new = 0
        try:
            for name, data in items:
                line = ft.Row([ft.ProgressRing(width=16, height=16), ft.Text("拆題中：%s" % name, size=13)])
                self.msg.controls.append(line)
                self.update()

                def prog(i, n):
                    self.bar.value = i / n
                    if i % 20 == 0 or i == n:
                        self.bar.update()
                try:
                    r = self.ctx.books.import_pdf(data, name, progress=prog)
                    total_new += r["new"]
                    units = "、".join("%s:%d" % (k, v) for k, v in sorted(r["by_unit"].items()))
                    line.controls = [ft.Icon(I.CHECK_CIRCLE, color=T.SUCCESS, size=18), ft.Text(
                        "%s（%s %s）：拆出 %d 題，新增 %d 題、題庫已有 %d 題%s" % (
                            name, r["year"] or "", "題庫" if r["kind"] == "BANK" else "年度試題", r["total"], r["new"],
                            r["same"], ("　新題單元 " + units) if units else ""), size=13, expand=True)]
                    for w in r["warnings"][:5]:
                        self.msg.controls.append(T.muted("　⚠ " + w, 12))
                except Exception as ex:
                    line.controls = [ft.Icon(I.ERROR_OUTLINE, color=T.DANGER, size=18),
                                     ft.Text("%s：%s" % (name, ex), size=13, color=T.DANGER, expand=True)]
                self.update()
        finally:
            Import.running = False
            self.bar.visible = False
            self.load()
        self.ctx.toast("匯入完成，題庫新增 %d 題" % total_new)

    def reclassify(self):
        n = self.ctx.guard(self.ctx.books.reclassify)
        if n is not None and n is not False:
            self.ctx.toast("重新判斷完成：%d 題改了單元" % (0 if n is True else n))

    def source_menu(self, r):
        c = self.ctx
        if not c.books.can("IMP", 2):
            return

        def go():
            n = c.guard(c.books.delete_source, r["id"])
            if n is not None:
                c.toast("已刪除「%s」，題庫移除 %d 題" % (r["title"], 0 if n is True else n))
                self.load()
        c.confirm("刪除匯入的 PDF", "刪除「%s」（%s）？只出現在這份 PDF、也沒人作答過的題目會一起從題庫移除；"
                  "其他題目只拿掉這年度的出現紀錄。" % (r["title"], r["file_name"]), go, yes="刪除")


_ = LETTERS
