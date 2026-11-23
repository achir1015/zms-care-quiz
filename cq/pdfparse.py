"""學科測驗 PDF 拆題：題庫（178004A13 等，依工作項目分單元）與每年度學科測試試題。

輸出每一題：題號、正確答案（1～4）、題目、四個選項；題目或選項裡的圖片以 [[img:n]] 標記，
圖片本身（PNG）另外放在 images[n]。

做法：
1. 用 PyMuPDF 取出每頁的文字片段與圖片位置（略過每頁都有的浮水印大圖）。
2. 依「列」排序（同一列由左到右），把圖片插在它所在的位置，串成一長串文字。
3. 以「題號. (答案)」切題（題號必須連續，避免內文的數字被誤認），再以 ①②③④ 切選項。
"""
import hashlib
import io
import os
import re
import unicodedata

IMG = "[[img:%d]]"
IMG_RE = re.compile(r"\[\[img:(\d+)\]\]")
CIRCLED = "①②③④"

# 頁首頁尾（每頁重複，要去掉）
NOISE = [
    re.compile(r"^全國技術士技能檢定.*梯次$"),
    re.compile(r"^Page \d+ of \d+$"),
    re.compile(r"^\d{2,3}\s*照顧服務員\s*單一\s*\d+\s*-\s*\d+.*$"),
    re.compile(r"^\d{2,3}\s*照顧服務員\s*單一\s*$"),
    re.compile(r"^准考證號碼"), re.compile(r"^姓$"), re.compile(r"^名[：:]$"),
    re.compile(r"^\d{1,3}$"),                          # 單獨一行的頁碼
]
UNIT_RE = re.compile(r"17800\s*照顧服務員\s*單一級?\s*工作項目\s*(\d+)\s*[：:]\s*(\S+)")
YEAR_RE = re.compile(r"(\d{2,3})\s*年度?\s*(?:第\s*(\d)\s*梯次)?\s*17800")
BANK_RE = re.compile(r"學科測試參考資料|檔案名稱\s*:\s*\d+A\d+")
VERSION_RE = re.compile(r"檔案名稱\s*:\s*(\S+)|版次編號\s*:\s*(\S+)|公告日期\s*:\s*([\d 年月日]+)")


class ParseError(Exception):
    pass


def _squash(s):
    """PDF 偶爾把每個字之間都放空白（104～106 年），把中文字之間的單一空白拿掉。"""
    return re.sub(r"(?<=[^\x00-\x7f]) (?=[^\x00-\x7f])|(?<=[^\x00-\x7f]) (?=\d)|(?<=\d) (?=[^\x00-\x7f])", "", s)


def _png_of(doc, xref):
    import pymupdf
    pix = pymupdf.Pixmap(doc, xref)
    try:
        if pix.n - pix.alpha >= 4:                 # CMYK → RGB
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        img = doc.extract_image(xref)
        if img and img.get("smask"):
            mask = pymupdf.Pixmap(doc, img["smask"])
            pix = pymupdf.Pixmap(pix, mask)
    except Exception:
        pass
    return pix.tobytes("png"), pix.width, pix.height


def _page_tokens(doc, page, images):
    """回傳這頁依閱讀順序排好的 (文字) 列。"""
    pw, ph = page.rect.width, page.rect.height
    toks, imgs = [], []                          # (y0, y1, x0, text)
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            for sp in ln["spans"]:
                t = sp["text"]
                if t.strip() == "":
                    continue
                x0, y0, x1, y1 = sp["bbox"]
                toks.append([y0, y1, x0, t])
    for info in page.get_image_info(xrefs=True):
        x0, y0, x1, y1 = info["bbox"]
        w, h = x1 - x0, y1 - y0
        if w * h > pw * ph * 0.18 or w < 4 or h < 4:     # 浮水印（整頁大圖）或極小的點
            continue
        xref = info.get("xref") or 0
        if not xref:
            continue
        try:
            png, iw, ih = _png_of(doc, xref)
        except Exception:
            # 抽不出來就直接截那一塊畫面
            import pymupdf
            pix = page.get_pixmap(clip=pymupdf.Rect(x0, y0, x1, y1), dpi=200)
            png, iw, ih = pix.tobytes("png"), pix.width, pix.height
        n = len(images)
        images.append({"png": png, "w": iw, "h": ih, "pt_w": round(w), "pt_h": round(h),
                       "sha1": hashlib.sha1(png).hexdigest()})
        imgs.append([y0, y1, x0, " " + IMG % n + " "])
    # 分列：依 y 排序，垂直中心落在目前這列範圍內的算同一列
    toks.sort(key=lambda t: (t[0], t[2]))
    rows = []
    for t in toks:
        cy = (t[0] + t[1]) / 2
        if rows and rows[-1]["y0"] - 1 <= cy <= rows[-1]["y1"] + 1:
            r = rows[-1]
            r["toks"].append(t)
            r["y0"], r["y1"] = min(r["y0"], t[0]), max(r["y1"], t[1])
        else:
            rows.append({"y0": t[0], "y1": t[1], "toks": [t]})
    # 圖片：放進「中心最接近」的那一列；圖片上方沒有任何列時自成一列
    for im in imgs:
        cy = (im[0] + im[1]) / 2
        near = [r for r in rows if r["y0"] - 4 <= cy <= r["y1"] + 4 or im[0] <= (r["y0"] + r["y1"]) / 2 <= im[1]]
        if near:
            r = min(near, key=lambda r: abs((r["y0"] + r["y1"]) / 2 - cy))
            r["toks"].append(im)
        else:
            rows.append({"y0": im[0], "y1": im[0] + 1, "toks": [im]})
            rows.sort(key=lambda r: r["y0"])
    out = []
    for r in rows:
        line = "".join(t[3] for t in sorted(r["toks"], key=lambda t: t[2])).strip()
        line = _squash(re.sub(r"[ 　]+", " ", line))
        line = line.replace("⑤", "窗")                 # 114 參考題庫的「窗」字被編成 ⑤（選項只有 ①～④）
        if line:
            out.append(line)
    return out


def norm(s):
    """比對用：全形半形統一、去掉空白與標點。"""
    s = unicodedata.normalize("NFKC", IMG_RE.sub("圖", s or ""))
    return re.sub(r"[\s，,。．\.、；;：:？?！!「」『』\"'（）()\[\]【】~～\-－—_/／]", "", s)


def parse(path_or_bytes, name=""):
    """拆解一份 PDF。回傳 dict(kind, year, title, version, units[], questions[], images[], warnings[])。"""
    import pymupdf
    doc = pymupdf.open(stream=path_or_bytes, filetype="pdf") if isinstance(path_or_bytes, (bytes, bytearray)) \
        else pymupdf.open(path_or_bytes)
    images, lines = [], []
    for page in doc:
        lines += _page_tokens(doc, page, images)
    if any(re.search(r"\d \d \d", ln) for ln in lines[:3]):      # 104～106 年：每個字都隔一個空白
        lines = [re.sub(r"(?<=\d) (?=[\d.])|(?<=\.) (?=\d)|(?<=\() (?=\d)|(?<=\d) (?=\))|(?<=[A-Za-z]) (?=[A-Za-z.])",
                        "", ln) for ln in lines]
    lines = [ln for ln in lines if not any(p.match(ln) for p in NOISE)]
    head = "\n".join(lines[:12])
    # 種類：有「工作項目」分單元＝BANK 題庫；標題寫「參考題庫／題庫」但沒分單元＝REF 參考題庫；其他＝EXAM 年度試題
    has_units = any(UNIT_RE.search(ln) for ln in lines[:40])
    if BANK_RE.search(head) or has_units:
        kind = "BANK"
    elif re.search(r"題庫", head) and not re.search(r"學科測試試題", head):
        kind = "REF"
    else:
        kind = "EXAM"
    year, batch, version, title = 0, 0, "", ""
    base = re.sub(r"\.pdf$", "", os.path.basename(name or ""), flags=re.I).strip()
    if kind == "EXAM":
        m = YEAR_RE.search(_squash(head.replace(" ", " ")))
        if m:
            year, batch = int(m.group(1)), int(m.group(2) or 0)
        title = "%d 年度學科測試試題" % year if year else "學科測試試題"
    else:
        for m in VERSION_RE.finditer(head):
            version = version or (m.group(2) or "")
            if m.group(1):
                title = "學科題庫 " + m.group(1)
        m = re.search(r"公告日期\s*:\s*(\d+)\s*年", head)
        if m:
            year = int(m.group(1))
    if not year:
        m = re.search(r"(?<!\d)(1\d{2})(?!\d)", base)
        if m:
            year = int(m.group(1))
    if not year:                                    # 檔名沒有年度：用 PDF 建立日期換算民國年
        m = re.match(r"D:(\d{4})", (doc.metadata or {}).get("creationDate") or "")
        if m and int(m.group(1)) > 1911:
            year = int(m.group(1)) - 1911
    if kind == "BANK" and not title:
        title = ("%d 年版學科題庫" % year) if year else "學科題庫"
    if kind == "REF":
        title = ("%d 年度參考題庫" % year) if year else "參考題庫"

    # 串成一長串，記下工作項目（單元）的切換點
    units, stream, marks = [], [], []
    pos = 0
    for ln in lines:
        m = UNIT_RE.search(ln)
        if m:
            code = "%02d" % int(m.group(1))
            units.append((code, m.group(2).strip()))
            marks.append((pos, code))
            continue
        if kind == "BANK" and (ln.startswith(("技術士技能檢定", "檔案名稱", "版次編號", "公告日期", "自108", "自 108"))):
            continue
        if kind == "EXAM" and pos == 0 and not re.match(r"^\d+\s*\.\s*\(", ln):
            continue                                   # 試卷開頭說明
        stream.append(ln)
        pos += len(ln) + 1
    text = "\n".join(stream)

    # 依題號切題：題號必須接續（每個單元重新從 1 開始）
    qs, warnings = [], []
    starts = []
    expect = 1
    for m in re.finditer(r"(?:^|\n|\s)(\d{1,3})\s*\.\s*\(\s*([1-4]{1,4})\s*\)", text):
        n = int(m.group(1))
        unit_here = _unit_at(marks, m.start(1))
        if starts and unit_here != starts[-1][3] and n == 1:
            expect = 1
        if n == expect:
            starts.append((m.start(), m.end(), n, unit_here, m.group(2)))
            expect += 1
    for i, (s, e, n, unit, ans) in enumerate(starts):
        body = text[e: starts[i + 1][0] if i + 1 < len(starts) else len(text)]
        body = re.sub(r"\s*\n\s*", "", body).strip()
        body = re.sub(r"(?<=[A-Za-z0-9,.])(?=[A-Za-z])", "", body)
        deleted = "本題刪題" in body[:12]
        body = re.sub(r"^\(?本題刪題\)?", "", body).strip()
        parts = re.split("([%s])" % CIRCLED, body)
        stem, opts, cur = parts[0], {}, None
        for p in parts[1:]:
            if p in CIRCLED:
                cur = CIRCLED.index(p) + 1
                opts[cur] = ""
            elif cur:
                opts[cur] += p
        if sorted(opts) != [1, 2, 3, 4]:
            warnings.append("第 %s 單元第 %d 題：選項不是剛好四個（%s）" % (unit or "-", n, body[:30]))
            continue
        clean = [_tidy(opts[k]) for k in (1, 2, 3, 4)]
        stem = _tidy(stem)
        # 「如下圖」的圖片排在選項下一列 → 會黏在第四個選項後面，移回題目
        m = re.match(r"^(.*?)[。.]?((?:\[\[img:\d+\]\])+)$", clean[3])
        if m and m.group(1) and "圖" in stem and not IMG_RE.search(stem):
            clean[3] = _tidy(m.group(1))
            stem = stem + m.group(2)
        if len(ans) != 1:
            warnings.append("第 %s 單元第 %d 題是複選（%s），已略過" % (unit or "-", n, ans))
            continue
        qs.append({"unit": unit, "no": n, "answer": int(ans), "stem": stem, "options": clean,
                   "deleted": deleted})
    if not qs:
        raise ParseError("這份 PDF 找不到「題號.(答案) 題目 ①…②…③…④…」格式的試題")
    return {"kind": kind, "year": year, "batch": batch, "title": title, "version": version, "units": units,
            "questions": qs, "images": images, "warnings": warnings, "pages": len(doc)}


def _unit_at(marks, pos):
    u = ""
    for p, code in marks:
        if p <= pos:
            u = code
    return u


def _tidy(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    s = re.sub(r"\s*\[\[img:(\d+)\]\]\s*", r"[[img:\1]]", s)
    s = re.sub(r"\s*[。．]\s*$", "", s).strip()
    s = re.sub(r"(?<=[^\x00-\x7f]) (?=[^\x00-\x7f])", "", s)
    return s


def summary(res):
    out = io.StringIO()
    print("%s %s 年 %s：%d 題、%d 張圖" % (res["kind"], res["year"], res["title"], len(res["questions"]),
                                     len(res["images"])), file=out)
    return out.getvalue()
