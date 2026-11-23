"""題庫：匯入 PDF（自動拆題、比對、增加題庫）、單元、題目維護、圖片、統計。

比對規則（判斷是不是「同一題」）：
1. 題目＋四個選項（不管順序）＋正確答案的文字，正規化後完全相同 → 同一題。
2. 否則找最相似的題目：題目與選項的相似度平均 ≥ 0.9，而且正確答案的文字也相似 → 同一題（只是字有些微不同）。
3. 其他 → 新題目，加進題庫；單元依序用：題庫 PDF 上的工作項目 → 最相似的題庫題目 → 共同科目關鍵字 → 待分類。
"""
import hashlib
import json
import random
import re

from . import pdfparse as P
from .core import BizError

SAME_SCORE = 0.9
UNIT_SCORE = 0.45
CARE_WORDS = ("案主", "被照顧者", "照顧服務員", "照服員", "長者", "個案", "失智", "臥床", "老人", "家屬", "案家")


def _bigrams(s):
    s = P.norm(s)
    return frozenset(s[i:i + 2] for i in range(len(s) - 1)) or frozenset([s])


def _sim(a, b):
    return len(a & b) / max(1, len(a | b))


def norm_key(stem, opts, answer):
    body = P.norm(stem) + "|" + "|".join(sorted(P.norm(o) for o in opts)) + "|" + P.norm(opts[answer - 1])
    return hashlib.sha1(body.encode("utf-8")).hexdigest()


def pin_last(opts):
    return int(bool(re.match(r"^以上(皆|都|均)?(是|非|對|不對|正確|不正確)$", P.norm(opts[3]))))


class _Index:
    """記憶體中的比對索引（匯入一份 PDF 時建立一次）。"""

    def __init__(self, rows):
        self.items = []
        self.by_key = {}
        for r in rows:
            self.add(r)

    def add(self, r):
        opts = [r["opt1"], r["opt2"], r["opt3"], r["opt4"]]
        it = {"row": r, "stem": _bigrams(r["stem"]), "opts": _bigrams("".join(sorted(P.norm(o) for o in opts))),
              "ans": _bigrams(opts[r["answer"] - 1])}
        self.items.append(it)
        self.by_key[r["norm_key"]] = it

    def best(self, stem, opts, answer):
        s1 = _bigrams(stem)
        s2 = _bigrams("".join(sorted(P.norm(o) for o in opts)))
        top, score = None, 0.0
        for it in self.items:
            sc = (_sim(s1, it["stem"]) + _sim(s2, it["opts"])) / 2
            if sc > score:
                top, score = it, sc
        same = False
        if top and score >= SAME_SCORE:
            same = _sim(_bigrams(opts[answer - 1]), top["ans"]) >= 0.8
        return top, score, same


class BankMixin:
    # ================================================================ 單元
    def units(self, with_counts=False):
        rows = self.db.rows("SELECT * FROM qb_unit ORDER BY sort, code")
        if with_counts:
            cnt = {r["unit"]: r for r in self.db.rows(
                "SELECT unit, COUNT(*) total, SUM(active=1 AND deleted=0) usable, SUM(origin='BANK') bank, "
                "SUM(origin='EXAM') exam_only, SUM(origin='MANUAL') manual, SUM(deleted=1) deleted, "
                "SUM(active=0) inactive, SUM(exam_count>0) appeared FROM qb_question GROUP BY unit")}
            for r in rows:
                c = cnt.get(r["code"], {})
                for k in ("total", "usable", "bank", "exam_only", "manual", "deleted", "inactive", "appeared"):
                    r[k] = int(c.get(k) or 0)
        return rows

    def unit_names(self):
        return {r["code"]: r["name"] for r in self.db.rows("SELECT code, name FROM qb_unit")}

    def save_unit(self, code, name, keywords=None):
        self.need("BANK")
        if not (name or "").strip():
            raise BizError("單元名稱必填")
        args = [name.strip()[:60]]
        sql = "UPDATE qb_unit SET name=%s"
        if keywords is not None:
            sql += ", keywords=%s"
            args.append(",".join(k.strip() for k in re.split(r"[,，、\s]+", keywords) if k.strip())[:400])
        self.db.exec(sql + " WHERE code=%s", tuple(args + [code]))
        self.log("unit", code, name)

    # ================================================================ 匯入 PDF
    def sources(self):
        return self.db.rows("SELECT id, kind, year, title, version, file_name, pages, q_total, q_new, q_same, note, "
                            "imported_at, imported_by FROM qb_source ORDER BY kind='EXAM', year DESC, id DESC")

    def preview_pdf(self, data, file_name=""):
        """只拆題不寫入（匯入前先看拆出幾題、有沒有提醒）。"""
        self.need("IMP")
        try:
            res = P.parse(bytes(data), file_name)
        except P.ParseError as e:
            raise BizError(str(e))
        except Exception as e:
            raise BizError("無法讀取這份 PDF：%s" % e)
        sha = hashlib.sha256(data).hexdigest()
        old = self.db.row("SELECT id, title, imported_at FROM qb_source WHERE sha256=%s", (sha,))
        return {"kind": res["kind"], "year": res["year"], "title": res["title"], "version": res["version"],
                "count": len(res["questions"]), "images": len(res["images"]), "warnings": res["warnings"],
                "units": res["units"], "deleted": sum(q["deleted"] for q in res["questions"]),
                "duplicate": old}

    def import_pdf(self, data, file_name="", year=None, progress=None):
        """匯入一份 PDF。回傳 dict(source_id, new, same, total, warnings, by_unit)。"""
        self.need("IMP")
        data = bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        if self.db.value("SELECT id FROM qb_source WHERE sha256=%s", (sha,)):
            raise BizError("這份 PDF 已經匯入過了")
        try:
            res = P.parse(data, file_name)
        except P.ParseError as e:
            raise BizError(str(e))
        if year:
            res["year"] = int(year)
        kind = res["kind"]
        # 題庫 PDF：用 PDF 上的工作項目名稱更新單元名稱
        for code, name in res["units"]:
            self.db.exec("UPDATE qb_unit SET name=%s WHERE code=%s AND grp='CARE'", (name[:60], code))
        units = self.units()
        kw_units = [(u["code"], [k for k in (u["keywords"] or "").split(",") if k]) for u in units
                    if u["grp"] == "COMMON"]
        care_units = {u["code"] for u in units if u["grp"] == "CARE"}
        idx = _Index(self.db.rows("SELECT id, unit, stem, opt1, opt2, opt3, opt4, answer, norm_key, origin, unit_auto, "
                                  "first_year, last_year FROM qb_question"))
        stat = {"new": 0, "same": 0, "total": len(res["questions"]), "by_unit": {}, "warnings": list(res["warnings"])}
        with self.db.transaction():
            sid = self.db.exec(
                "INSERT INTO qb_source (kind, year, title, version, file_name, sha256, pages, q_total, pdf, note, "
                "imported_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (kind, res["year"], res["title"][:120], res["version"][:40], (file_name or "")[-200:], sha,
                 res["pages"], len(res["questions"]), data, "\n".join(res["warnings"]), self.uid))
            img_ids = [self._save_image(im) for im in res["images"]]

            def fix(t):
                return P.IMG_RE.sub(lambda m: "[[img:%d]]" % img_ids[int(m.group(1))], t)

            for i, q in enumerate(res["questions"]):
                if progress:
                    progress(i + 1, len(res["questions"]))
                stem, opts, ans = fix(q["stem"]), [fix(o) for o in q["options"]], q["answer"]
                key = norm_key(stem, opts, ans)
                hit = idx.by_key.get(key)
                same = bool(hit)
                if not hit:
                    top, score, same = idx.best(stem, opts, ans)
                    hit = top if same else None
                if hit:
                    r = hit["row"]
                    qid = r["id"]
                    self._touch(r, kind, res["year"], q, sid)
                    stat["same"] += 1
                else:
                    unit = self._guess_unit(kind, q, stem, opts, ans, idx, kw_units, care_units)
                    qid = self.db.exec(
                        "INSERT INTO qb_question (unit, bank_no, stem, opt1, opt2, opt3, opt4, answer, pin_last, "
                        "norm_key, origin, first_year, last_year, exam_count, deleted, active, unit_auto) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)",
                        (unit, ("%s-%03d" % (q["unit"], q["no"])) if kind == "BANK" else "", stem, *opts, ans,
                         pin_last(opts), key, kind, res["year"], res["year"], 1 if kind == "EXAM" else 0,
                         int(q["deleted"]), 0 if q["deleted"] else 1))
                    r = {"id": qid, "unit": unit, "stem": stem, "opt1": opts[0], "opt2": opts[1], "opt3": opts[2],
                         "opt4": opts[3], "answer": ans, "norm_key": key, "origin": kind, "unit_auto": 1,
                         "first_year": res["year"], "last_year": res["year"]}
                    idx.add(r)
                    stat["new"] += 1
                    stat["by_unit"][unit] = stat["by_unit"].get(unit, 0) + 1
                self.db.exec("INSERT IGNORE INTO qb_appear (qid, source_id, no, orig_answer) VALUES (%s, %s, %s, %s)",
                             (qid, sid, q["no"], ans))
            self.db.exec("UPDATE qb_source SET q_new=%s, q_same=%s WHERE id=%s", (stat["new"], stat["same"], sid))
        if kind == "BANK":
            stat["reclassified"] = self.reclassify(log=False)
        stat["source_id"] = sid
        stat["kind"], stat["year"], stat["title"] = kind, res["year"], res["title"]
        self.log("import_pdf", file_name or res["title"], json.dumps(
            {k: stat[k] for k in ("new", "same", "total")}, ensure_ascii=False))
        return stat

    def reclassify(self, log=True):
        """重新判斷「歷屆試題才有、單元沒手動改過」的題目單元（匯入新題庫或修改關鍵字後使用）。"""
        self.need("BANK")
        units = self.units()
        kw_units = [(u["code"], [k for k in (u["keywords"] or "").split(",") if k]) for u in units
                    if u["grp"] == "COMMON"]
        care_units = {u["code"] for u in units if u["grp"] == "CARE"}
        ref = _Index(self.db.rows("SELECT id, unit, stem, opt1, opt2, opt3, opt4, answer, norm_key FROM qb_question "
                                  "WHERE origin='BANK'"))
        changed = 0
        for r in self.db.rows("SELECT id, unit, stem, opt1, opt2, opt3, opt4, answer FROM qb_question "
                              "WHERE origin='EXAM' AND unit_auto=1"):
            opts = [r["opt1"], r["opt2"], r["opt3"], r["opt4"]]
            u = self._guess_unit("EXAM", {"unit": ""}, r["stem"], opts, r["answer"], ref, kw_units, care_units)
            if u != r["unit"]:
                self.db.exec("UPDATE qb_question SET unit=%s WHERE id=%s", (u, r["id"]))
                changed += 1
        if log:
            self.log("reclassify", "", "%d 題改單元" % changed)
        return changed

    def _touch(self, r, kind, year, q, sid):
        """題庫已有這一題：更新出現年度；題庫 PDF 的單元與題號優先。"""
        sets, args = ["first_year=IF(first_year=0 OR first_year>%s, %s, first_year)",
                      "last_year=GREATEST(last_year, %s)"], [year, year, year]
        if kind == "EXAM":
            sets.append("exam_count=exam_count+1")
        elif q["deleted"]:
            pass                       # 題庫裡重複而被刪的那一題：保留原本那一題，不動它
        else:
            sets += ["origin=IF(origin='MANUAL', origin, 'BANK')", "bank_no=%s", "deleted=%s"]
            args += ["%s-%03d" % (q["unit"], q["no"]), int(q["deleted"])]
            if q["deleted"]:
                sets.append("active=0")
            if r.get("unit_auto", 1) and q["unit"]:
                sets.append("unit=%s")
                args.append(q["unit"])
                r["unit"] = q["unit"]
            r["origin"] = "BANK"
        self.db.exec("UPDATE qb_question SET %s WHERE id=%%s" % ", ".join(sets), tuple(args + [r["id"]]))

    @staticmethod
    def _guess_unit(kind, q, stem, opts, ans, idx, kw_units, care_units):
        if kind == "BANK" and q["unit"]:
            return q["unit"]
        top, score, _ = idx.best(stem, opts, ans)
        if top and score >= UNIT_SCORE and top["row"]["unit"] in care_units:
            return top["row"]["unit"]
        text = P.norm(stem + "".join(opts))
        hits = [(sum(text.count(P.norm(k)) for k in kws), code) for code, kws in kw_units]
        hits.sort(reverse=True)
        care = any(w in stem for w in CARE_WORDS)
        if hits and hits[0][0] > 0 and not (care and hits[0][0] < 2):
            return hits[0][1]
        if top and (care or score >= 0.3) and top["row"]["unit"] in care_units:
            return top["row"]["unit"]
        if hits and hits[0][0] > 0:
            return hits[0][1]
        return "99"

    def _save_image(self, im):
        old = self.db.value("SELECT id FROM qb_image WHERE sha1=%s", (im["sha1"],))
        if old:
            return old
        return self.db.exec("INSERT INTO qb_image (sha1, png, w, h, disp_w, disp_h) VALUES (%s, %s, %s, %s, %s, %s)",
                            (im["sha1"], im["png"], im["w"], im["h"], im["pt_w"], im["pt_h"]))

    def delete_source(self, sid):
        """刪除一份匯入的 PDF：只出現在這份 PDF、也沒人作答過的題目會一起刪除，其餘只拿掉出現紀錄。"""
        self.need("IMP")
        src = self.db.row("SELECT id, title, kind FROM qb_source WHERE id=%s", (sid,))
        if not src:
            raise BizError("找不到這份 PDF")
        qids = [r["qid"] for r in self.db.rows("SELECT qid FROM qb_appear WHERE source_id=%s", (sid,))]
        removed = 0
        with self.db.transaction():
            self.db.exec("DELETE FROM qb_appear WHERE source_id=%s", (sid,))
            self.db.exec("DELETE FROM qb_source WHERE id=%s", (sid,))
            for qid in qids:
                left = self.db.rows("SELECT s.kind, s.year FROM qb_appear a JOIN qb_source s ON s.id=a.source_id "
                                    "WHERE a.qid=%s", (qid,))
                if not left:
                    if self.db.value("SELECT 1 FROM qz_answer WHERE qid=%s LIMIT 1", (qid,)) or \
                            self.db.value("SELECT origin FROM qb_question WHERE id=%s", (qid,)) == "MANUAL":
                        self.db.exec("UPDATE qb_question SET active=0 WHERE id=%s AND origin<>'MANUAL'", (qid,))
                    else:
                        self.db.exec("DELETE FROM qb_question WHERE id=%s", (qid,))
                        removed += 1
                    continue
                years = [r["year"] for r in left]
                self.db.exec("UPDATE qb_question SET first_year=%s, last_year=%s, exam_count=%s, "
                             "origin=IF(origin='MANUAL', 'MANUAL', %s) WHERE id=%s",
                             (min(years), max(years), sum(1 for r in left if r["kind"] == "EXAM"),
                              "BANK" if any(r["kind"] == "BANK" for r in left) else "EXAM", qid))
            used = set()
            for r in self.db.rows("SELECT CONCAT(stem, opt1, opt2, opt3, opt4) t FROM qb_question "
                                  "WHERE CONCAT(stem, opt1, opt2, opt3, opt4) LIKE '%%[[img:%%'"):
                used |= {int(x) for x in P.IMG_RE.findall(r["t"])}
            for r in self.db.rows("SELECT id FROM qb_image"):
                if r["id"] not in used:
                    self.db.exec("DELETE FROM qb_image WHERE id=%s", (r["id"],))
        self.log("delete_source", src["title"], "刪除 %d 題" % removed)
        return removed

    # ================================================================ 題目
    def latest_bank_id(self):
        return self.db.value("SELECT id FROM qb_source WHERE kind='BANK' ORDER BY year DESC, id DESC LIMIT 1") or 0

    def questions(self, unit="", year=0, kw="", origin="", status="", limit=2000):
        self.need("BANK", 1)
        where, args = [], []
        if unit:
            where.append("q.unit=%s")
            args.append(unit)
        if year:
            where.append("EXISTS (SELECT 1 FROM qb_appear a JOIN qb_source s ON s.id=a.source_id "
                         "WHERE a.qid=q.id AND s.kind='EXAM' AND s.year=%s)")
            args.append(int(year))
        if kw:
            where.append("CONCAT(q.stem, q.opt1, q.opt2, q.opt3, q.opt4) LIKE %s")
            args.append("%" + kw.strip() + "%")
        if origin:
            where.append("q.origin=%s")
            args.append(origin)
        if status == "img":
            where.append("CONCAT(q.stem, q.opt1, q.opt2, q.opt3, q.opt4) LIKE '%%[[img:%%'")
        elif status == "off":
            where.append("(q.active=0 OR q.deleted=1)")
        elif status == "on":
            where.append("q.active=1 AND q.deleted=0")
        sql = ("SELECT q.*, (SELECT GROUP_CONCAT(DISTINCT s.year ORDER BY s.year SEPARATOR '、') FROM qb_appear a "
               "JOIN qb_source s ON s.id=a.source_id WHERE a.qid=q.id AND s.kind='EXAM') years "
               "FROM qb_question q%s ORDER BY q.unit, q.bank_no='', q.bank_no, q.first_year, q.id LIMIT %%s"
               % ((" WHERE " + " AND ".join(where)) if where else ""))
        return self.db.rows(sql, tuple(args) + (limit,))

    def question(self, qid):
        self.need("BANK", 1)
        q = self.db.row("SELECT * FROM qb_question WHERE id=%s", (qid,))
        if not q:
            raise BizError("找不到這一題")
        q["appears"] = self.db.rows("SELECT s.kind, s.year, s.title, a.no, a.orig_answer FROM qb_appear a "
                                    "JOIN qb_source s ON s.id=a.source_id WHERE a.qid=%s ORDER BY s.year", (qid,))
        q["stats"] = self.db.row("SELECT COUNT(*) n, COALESCE(SUM(is_correct),0) ok FROM qz_answer x JOIN qz_attempt t "
                                 "ON t.id=x.attempt_id WHERE x.qid=%s AND t.status='DONE'", (qid,))
        return q

    def save_question(self, qid, unit, stem, opts, answer, active=True):
        """修改或新增（qid=0）題目。"""
        self.need("BANK")
        stem = (stem or "").strip()
        opts = [(o or "").strip() for o in opts]
        if not stem or len(opts) != 4 or not all(opts):
            raise BizError("題目與四個選項都必須填寫")
        answer = int(answer or 0)
        if answer not in (1, 2, 3, 4):
            raise BizError("請選擇正確答案")
        if len({P.norm(o) for o in opts}) < 4:
            raise BizError("四個選項不能有相同的內容")
        key = norm_key(stem, opts, answer)
        dup = self.db.value("SELECT id FROM qb_question WHERE norm_key=%s AND id<>%s", (key, qid or 0))
        if dup:
            raise BizError("題庫已有相同的題目（編號 %s）" % dup)
        if qid:
            old = self.db.row("SELECT * FROM qb_question WHERE id=%s", (qid,))
            if not old:
                raise BizError("找不到這一題")
            self.db.exec("UPDATE qb_question SET unit=%s, unit_auto=IF(unit=%s, unit_auto, 0), stem=%s, opt1=%s, "
                         "opt2=%s, opt3=%s, opt4=%s, answer=%s, pin_last=%s, norm_key=%s, active=%s, updated_at=NOW(), "
                         "updated_by=%s WHERE id=%s",
                         (unit, unit, stem, *opts, answer, pin_last(opts), key, int(bool(active)), self.uid, qid))
            diff = {k: [old[k], v] for k, v in (("unit", unit), ("stem", stem), ("opt1", opts[0]), ("opt2", opts[1]),
                                                ("opt3", opts[2]), ("opt4", opts[3]), ("answer", answer),
                                                ("active", int(bool(active)))) if old[k] != v}
            self.log("question", qid, json.dumps(diff, ensure_ascii=False))
            return qid
        qid = self.db.exec("INSERT INTO qb_question (unit, stem, opt1, opt2, opt3, opt4, answer, pin_last, norm_key, "
                           "origin, active, unit_auto, updated_at, updated_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                           "%s, 'MANUAL', %s, 0, NOW(), %s)",
                           (unit, stem, *opts, answer, pin_last(opts), key, int(bool(active)), self.uid))
        self.log("question_add", qid, stem[:60])
        return qid

    def set_active(self, qid, active):
        self.need("BANK")
        self.db.exec("UPDATE qb_question SET active=%s, updated_at=NOW(), updated_by=%s WHERE id=%s",
                     (int(bool(active)), self.uid, qid))
        self.log("question_active", qid, "啟用" if active else "停用")

    def image(self, img_id):
        r = self.db.row("SELECT png, w, h, disp_w, disp_h FROM qb_image WHERE id=%s", (img_id,))
        return r

    # ================================================================ 統計
    def bank_stats(self):
        """各單元題庫數、總題庫數、每年度新增題數。"""
        units = self.units(with_counts=True)
        tot = {k: sum(u[k] for u in units) for k in ("total", "usable", "bank", "exam_only", "manual", "deleted",
                                                      "inactive", "appeared")}
        years = self.db.rows("SELECT id, kind, year, title, q_total, q_new, q_same, imported_at FROM qb_source "
                             "ORDER BY year, kind")
        imgs = self.db.value("SELECT COUNT(*) FROM qb_image") or 0
        return {"units": units, "total": tot, "sources": years, "images": imgs,
                "latest_bank": self.db.row("SELECT title, version, year FROM qb_source WHERE kind='BANK' "
                                           "ORDER BY year DESC, id DESC LIMIT 1")}

    def year_matrix(self):
        """每年度試題各單元題數（看每年考哪些單元）。"""
        return self.db.rows("SELECT s.year, q.unit, COUNT(*) n FROM qb_appear a JOIN qb_source s ON s.id=a.source_id "
                            "JOIN qb_question q ON q.id=a.qid WHERE s.kind='EXAM' GROUP BY s.year, q.unit "
                            "ORDER BY s.year, q.unit")

    def random_question(self):
        ids = self.db.rows("SELECT id FROM qb_question WHERE active=1 AND deleted=0")
        return self.question(random.choice(ids)["id"]) if ids else None
