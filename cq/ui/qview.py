"""題目顯示共用元件：含圖片的題目／選項文字、成績折線圖、單元答對率長條。"""
import flet as ft
import flet.canvas as cv

from ..pdfparse import IMG_RE
from . import theme as T

LETTERS = "ABCD"
_IMG_CACHE = {}


def _img(ctx, img_id, scale=1.6):
    r = _IMG_CACHE.get(img_id)
    if r is None:
        r = ctx.books.image(img_id) or {}
        _IMG_CACHE[img_id] = r
    if not r.get("png"):
        return ft.Container(ft.Icon(ft.Icons.BROKEN_IMAGE, color=T.MUTED), tooltip="圖片 %s 不存在" % img_id)
    w = int((r.get("disp_w") or r.get("w") or 60) * scale)
    h = int((r.get("disp_h") or r.get("h") or 60) * scale)
    return ft.Container(ft.Image(src=bytes(r["png"]), width=w, height=h, fit=ft.BoxFit.CONTAIN),
                        border=ft.Border.all(1, T.LINE), border_radius=6, padding=4, bgcolor=ft.Colors.WHITE)


def rich(ctx, text, size=15, color=None, weight=None, expand=True):
    """文字裡的 [[img:編號]] 換成圖片；沒有圖片時就是一般文字。"""
    text = text or ""
    if not IMG_RE.search(text):
        return ft.Text(text, size=size, color=color or T.TEXT, weight=weight, expand=expand, selectable=False)
    parts, pos = [], 0
    for m in IMG_RE.finditer(text):
        if m.start() > pos:
            parts.append(ft.Text(text[pos:m.start()], size=size, color=color or T.TEXT, weight=weight))
        parts.append(_img(ctx, int(m.group(1))))
        pos = m.end()
    if pos < len(text):
        parts.append(ft.Text(text[pos:], size=size, color=color or T.TEXT, weight=weight))
    return ft.Row(parts, wrap=True, spacing=8, run_spacing=6, expand=expand,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER)


def plain(text):
    """清單用的純文字（圖片顯示成〔圖〕）。"""
    return IMG_RE.sub("〔圖〕", text or "")


def line_chart(values, labels=None, width=760, height=260, pass_line=60, color=T.ACCENT):
    """成績折線圖（0～100 分）：每一點是一次測驗；虛線是及格分數。寬度會跟著外框自動調整。"""
    canvas = cv.Canvas(_chart_shapes(values, labels, width, height, pass_line, color), height=height, expand=True)

    def resized(e):
        w = int(getattr(e, "width", 0) or 0)
        if w > 120 and abs(w - getattr(canvas, "_w", width)) > 4:
            canvas._w = w
            canvas.shapes = _chart_shapes(values, labels, w, height, pass_line, color)
            canvas.update()
    canvas.on_resize = resized
    canvas.resize_interval = 100
    return canvas


def _chart_shapes(values, labels, width, height, pass_line, color):
    left, right, top, bottom = 40, 26, 24, 30
    W, H = width - left - right, height - top - bottom
    shapes = []
    grid_paint = ft.Paint(color="#E5E9F0", stroke_width=1)
    for v in range(0, 101, 20):
        y = top + H - H * v / 100
        shapes.append(cv.Line(left, y, left + W, y, paint=grid_paint))
        shapes.append(cv.Text(left - 8, y - 8, str(v), ft.TextStyle(size=11, color=T.MUTED),
                              alignment=ft.Alignment.TOP_RIGHT))
    if pass_line:
        y = top + H - H * pass_line / 100
        shapes.append(cv.Line(left, y, left + W, y, paint=ft.Paint(color="#F59E0B", stroke_width=1.5,
                                                                   stroke_dash_pattern=[6, 4])))
        shapes.append(cv.Text(left + W - 4, y - 18, "及格 %d" % pass_line, ft.TextStyle(size=11, color="#B45309"),
                              alignment=ft.Alignment.TOP_RIGHT))
    n = len(values)
    if n:
        step = W / max(1, n - 1) if n > 1 else 0
        pts = [(left + (i * step if n > 1 else W / 2), top + H - H * max(0, min(100, v)) / 100)
               for i, v in enumerate(values)]
        if n > 1:
            elems = [cv.Path.MoveTo(pts[0][0], top + H)] + [cv.Path.LineTo(x, y) for x, y in pts] + \
                    [cv.Path.LineTo(pts[-1][0], top + H), cv.Path.Close()]
            shapes.append(cv.Path(elems, paint=ft.Paint(color=ft.Colors.with_opacity(0.12, color),
                                                        style=ft.PaintingStyle.FILL)))
            shapes.append(cv.Path([cv.Path.MoveTo(*pts[0])] + [cv.Path.LineTo(x, y) for x, y in pts[1:]],
                                  paint=ft.Paint(color=color, stroke_width=3, style=ft.PaintingStyle.STROKE)))
        every = max(1, n // 12)
        for i, (x, y) in enumerate(pts):
            shapes.append(cv.Circle(x, y, 5, paint=ft.Paint(color=ft.Colors.WHITE, style=ft.PaintingStyle.FILL)))
            shapes.append(cv.Circle(x, y, 5, paint=ft.Paint(color=color, stroke_width=2.5,
                                                            style=ft.PaintingStyle.STROKE)))
            if n <= 20 or i == n - 1:
                shapes.append(cv.Text(x, y - 22, ("%g" % values[i]), ft.TextStyle(size=11, color=T.TEXT,
                                                                                  weight=ft.FontWeight.W_600),
                                      alignment=ft.Alignment.TOP_CENTER))
            if labels and (i % every == 0 or i == n - 1):
                shapes.append(cv.Text(x, top + H + 8, labels[i], ft.TextStyle(size=10, color=T.MUTED),
                                      alignment=ft.Alignment.TOP_CENTER))
    return shapes


def rate_bar(label, rate, recent=None, sub="", width=None):
    """單元答對率：灰底長條＋顏色依高低；recent＝最近 5 次答對率（小字）。"""
    tone = T.SUCCESS if rate >= 80 else T.ACCENT if rate >= 60 else T.WARN if rate >= 40 else T.DANGER
    trend = ""
    if recent is not None:
        d = recent - rate
        trend = "最近 %g%%%s" % (recent, "　↑" if d >= 3 else "　↓" if d <= -3 else "")
    return ft.Column([
        ft.Row([ft.Text(label, size=13, weight=ft.FontWeight.W_600, expand=True, max_lines=1),
                T.muted(trend, 12), ft.Text("%g%%" % rate, size=14, weight=ft.FontWeight.W_800, color=tone)]),
        ft.ProgressBar(value=max(0.0, min(1.0, rate / 100)), color=tone, bgcolor="#EEF2F7", bar_height=10,
                       border_radius=5),
        T.muted(sub, 11) if sub else ft.Container()], spacing=4, width=width)


def speak_text_of(stem, answer_text, explain):
    """朗讀用文字：題目、正確答案、解說（圖片標記拿掉）。"""
    def clean(s):
        return IMG_RE.sub("如圖", s or "")
    return "題目：%s。正確答案是：%s。%s" % (clean(stem), clean(answer_text), clean(explain))


def explain_box(ctx, explain, speak=None, title="AI 解說"):
    """解說框：淡黃底、燈泡圖示＋朗讀按鈕（微軟神經語音）。沒有解說時顯示提示。"""
    head = [ft.Icon(ft.Icons.TIPS_AND_UPDATES, color="#B45309", size=18),
            ft.Text(title, size=13, weight=ft.FontWeight.W_700, color="#92400E", expand=True)]
    if speak and explain:
        head.append(ft.IconButton(ft.Icons.VOLUME_UP, icon_color="#B45309", icon_size=20, tooltip="朗讀題目、答案與解說",
                                  on_click=lambda e: ctx.say_text(speak())))
    body = ft.Text(explain, size=14, color="#3F2D0C", selectable=True) if explain else \
        T.muted("這題還沒有解說（管理員可在「題庫瀏覽與維護」用 AI 產生）", 12)
    return ft.Container(ft.Column([ft.Row(head, spacing=6), body], spacing=4), bgcolor="#FFF8E6",
                        border=ft.Border.all(1, "#F5D9A8"), border_radius=10,
                        padding=ft.Padding.only(left=12, right=8, top=6, bottom=10))
