r"""內建基本題庫：安裝後第一次開啟（題庫還是空的）時自動載入 assets/seed/bank.json.gz。

內容由 tools/make_seed_bank.py 從 ..\PDF 的全部 PDF 匯入後匯出（題目、圖片、單元、出現紀錄、PDF 清單；不含 PDF 原檔）。
使用者之後再匯入同一份 PDF 會被判定為「已匯入過」（同一個 sha256）。
"""
import base64
import gzip
import json
import os

TABLES = {
    "qb_unit": ["code", "name", "grp", "keywords", "sort"],
    "qb_source": ["id", "kind", "year", "title", "version", "file_name", "sha256", "pages", "q_total", "q_new", "q_same",
                  "note", "imported_at", "imported_by"],
    "qb_image": ["id", "sha1", "png", "w", "h", "disp_w", "disp_h"],
    "qb_question": ["id", "unit", "bank_no", "stem", "opt1", "opt2", "opt3", "opt4", "answer", "pin_last", "norm_key",
                    "origin", "first_year", "last_year", "exam_count", "unit_auto", "deleted", "active", "created_at",
                    "explain_text", "explain_by", "explain_at"],
    "qb_appear": ["qid", "source_id", "no", "orig_answer"],
}


def seed_path():
    from .settings import resource_dir
    return os.path.join(resource_dir(), "assets", "seed", "bank.json.gz")


def dump(db, path):
    out = {"format": "zms-care-quiz-seed/1"}
    for t, cols in TABLES.items():
        rows = db.rows("SELECT %s FROM %s" % (", ".join("`%s`" % c for c in cols), t))
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, (bytes, bytearray)):
                    r[k] = {"b64": base64.b64encode(bytes(v)).decode("ascii")}
                elif hasattr(v, "isoformat"):
                    r[k] = v.isoformat(sep=" ")
        out[t] = rows
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return {t: len(out[t]) for t in TABLES}


def load(db, path=None):
    """題庫是空的（也沒匯入過任何 PDF）才載入。回傳載入題數。"""
    path = path or seed_path()
    if not os.path.isfile(path):
        return 0
    if db.value("SELECT COUNT(*) FROM qb_question") or db.value("SELECT COUNT(*) FROM qb_source"):
        return 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    with db.transaction():
        for t, cols in TABLES.items():
            rows = [tuple(base64.b64decode(r[c]["b64"]) if isinstance(r.get(c), dict) else r.get(c) for c in cols)
                    for r in data.get(t, [])]
            verb = "REPLACE" if t == "qb_unit" else "INSERT IGNORE"
            db.exec_many("%s INTO %s (%s) VALUES (%s)" % (verb, t, ", ".join("`%s`" % c for c in cols),
                                                         ", ".join(["%s"] * len(cols))), rows)
    return len(data.get("qb_question", []))



def fill_explanations(db, path=None):
    """已經有題庫的資料庫（例如較早版本載入的內建題庫）：依比對鍵補上內建解說，只補空白的，不覆蓋。"""
    path = path or seed_path()
    if not os.path.isfile(path):
        return 0
    if not db.value("SELECT COUNT(*) FROM qb_question WHERE deleted=0 AND (explain_text IS NULL OR explain_text='')"):
        return 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    rows = [(q["explain_text"], q.get("explain_by") or "內建 AI", q["norm_key"]) for q in data.get("qb_question", [])
            if q.get("explain_text")]
    n = 0
    for text, by, key in rows:
        n += db.exec("UPDATE qb_question SET explain_text=%s, explain_by=%s, explain_at=NOW() "
                     "WHERE norm_key=%s AND (explain_text IS NULL OR explain_text='')", (text, by, key)) or 0
    return n


def fill_units(db, path=None):
    """已經有題庫的資料庫：內建題庫人工指定單元的題目（unit_auto=0），若使用者這邊還在「待分類」就改成內建的單元。
    使用者自己指定過的單元（不是 99）不覆蓋。"""
    path = path or seed_path()
    if not os.path.isfile(path):
        return 0
    if not db.value("SELECT COUNT(*) FROM qb_question WHERE unit='99'"):
        return 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    n = 0
    for q in data.get("qb_question", []):
        if not q.get("unit_auto") and q.get("unit") not in (None, "", "99"):
            n += db.exec("UPDATE qb_question SET unit=%s, unit_auto=0 WHERE norm_key=%s AND unit='99'",
                         (q["unit"], q["norm_key"])) or 0
    return n
