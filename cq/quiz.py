"""測驗：出題（每次 100 題，選項隨機換位置、正確答案跟著變）、作答、交卷評分、成績與成長圖表資料。"""
import random

from .core import BizError
from .seed import MODES


def make_perm(pin_last=False, shuffle=True):
    """選項換位：回傳 '3142' 之類（第 i 個位置顯示原本第幾個選項）。"""
    if not shuffle:
        return "1234"
    if pin_last:
        p = ["1", "2", "3"]
        random.shuffle(p)
        return "".join(p) + "4"
    p = ["1", "2", "3", "4"]
    random.shuffle(p)
    return "".join(p)


def allocate(sizes, n):
    """依各單元題數比例分配 n 題（最大餘數法），每個單元不超過它的題數。"""
    total = sum(sizes.values())
    if total <= n:
        return dict(sizes)
    raw = {k: v * n / total for k, v in sizes.items()}
    out = {k: min(sizes[k], int(r)) for k, r in raw.items()}
    rest = n - sum(out.values())
    for k in sorted(raw, key=lambda k: raw[k] - int(raw[k]), reverse=True):
        if rest <= 0:
            break
        if out[k] < sizes[k]:
            out[k] += 1
            rest -= 1
    return out


class QuizMixin:
    # ================================================================ 出題
    def _pool_sql(self):
        """可以出題的題目：啟用、未刪題；設定「不含舊題」時只用最新題庫＋共同科目。"""
        c = self.company()
        sql = "q.active=1 AND q.deleted=0"
        if not c.get("include_old", 1):
            latest = self.latest_bank_id()
            sql += (" AND (q.origin='MANUAL' OR q.unit IN (SELECT code FROM qb_unit WHERE grp='COMMON') OR "
                    "EXISTS (SELECT 1 FROM qb_appear a WHERE a.qid=q.id AND a.source_id=%d))" % int(latest))
        return sql

    def quiz_options(self):
        """開始測驗畫面用：各單元可出題數、歷屆試題清單、錯題數、進行中的測驗。"""
        pool = self._pool_sql()
        units = self.db.rows("SELECT u.code, u.name, u.grp, COUNT(q.id) n FROM qb_unit u LEFT JOIN qb_question q "
                             "ON q.unit=u.code AND %s GROUP BY u.code ORDER BY u.sort" % pool)
        years = self.db.rows("SELECT s.id, s.year, s.title, COUNT(a.qid) n FROM qb_source s JOIN qb_appear a "
                             "ON a.source_id=s.id JOIN qb_question q ON q.id=a.qid AND q.active=1 AND q.deleted=0 "
                             "WHERE s.kind='EXAM' GROUP BY s.id ORDER BY s.year DESC")
        c = self.company()
        return {"units": units, "years": years, "wrong": len(self._wrong_ids()), "size": int(c.get("quiz_size") or 100),
                "total": sum(u["n"] for u in units), "open": self.open_attempt()}

    def _wrong_ids(self, uid=None):
        """這個人最近一次作答答錯的題目（後來答對就不算）。"""
        rows = self.db.rows(
            "SELECT x.qid, x.is_correct FROM qz_answer x JOIN qz_attempt t ON t.id=x.attempt_id "
            "WHERE t.uid=%s AND t.status='DONE' AND x.chosen>=0 ORDER BY t.finished_at, t.id", (uid or self.uid,))
        last = {}
        for r in rows:
            last[r["qid"]] = r["is_correct"]
        ids = [q for q, ok in last.items() if not ok]
        if not ids:
            return []
        alive = {r["id"] for r in self.db.rows("SELECT id FROM qb_question q WHERE q.active=1 AND q.deleted=0 AND "
                                               "q.id IN (%s)" % ",".join(str(int(i)) for i in ids))}
        return [i for i in ids if i in alive]

    def open_attempt(self):
        return self.db.row("SELECT * FROM qz_attempt WHERE uid=%s AND status='OPEN' ORDER BY id DESC LIMIT 1",
                           (self.uid,))

    def start_quiz(self, mode="MOCK", unit="", source_id=0, size=None):
        self.need("QUIZ", 1)
        if mode not in MODES:
            raise BizError("不明的測驗方式")
        c = self.company()
        n = int(size or c.get("quiz_size") or 100)
        pool = self._pool_sql()
        if mode == "MOCK":
            rows = self.db.rows("SELECT q.id, q.unit, q.pin_last FROM qb_question q WHERE %s" % pool)
            by = {}
            for r in rows:
                by.setdefault(r["unit"], []).append(r)
            take = allocate({k: len(v) for k, v in by.items()}, n)
            picked = [r for k, v in by.items() for r in random.sample(v, take.get(k, 0))]
            random.shuffle(picked)
        elif mode == "UNIT":
            rows = self.db.rows("SELECT q.id, q.unit, q.pin_last FROM qb_question q WHERE q.unit=%%s AND %s" % pool,
                                (unit,))
            picked = random.sample(rows, min(n, len(rows)))
        elif mode == "YEAR":
            picked = self.db.rows("SELECT q.id, q.unit, q.pin_last FROM qb_appear a JOIN qb_question q ON q.id=a.qid "
                                  "WHERE a.source_id=%s AND q.active=1 AND q.deleted=0 ORDER BY a.no", (source_id,))
        else:
            ids = self._wrong_ids()
            random.shuffle(ids)
            ids = ids[:n]
            picked = self.db.rows("SELECT q.id, q.unit, q.pin_last FROM qb_question q WHERE q.id IN (%s)"
                                  % ",".join(str(int(i)) for i in ids)) if ids else []
            random.shuffle(picked)
        if not picked:
            raise BizError("沒有可以出題的題目" + ("，你目前沒有答錯的題目 👍" if mode == "WRONG" else "，請先匯入學科測驗 PDF"))
        shuffle = bool(c.get("shuffle_options", 1))
        ans = {r["id"]: r["answer"] for r in self.db.rows(
            "SELECT id, answer FROM qb_question WHERE id IN (%s)" % ",".join(str(int(r["id"])) for r in picked))}
        with self.db.transaction():
            self.db.exec("DELETE x FROM qz_answer x JOIN qz_attempt t ON t.id=x.attempt_id "
                         "WHERE t.uid=%s AND t.status='OPEN'", (self.uid,))
            self.db.exec("DELETE FROM qz_attempt WHERE uid=%s AND status='OPEN'", (self.uid,))
            aid = self.db.exec("INSERT INTO qz_attempt (uid, mode, unit, source_id, q_count) VALUES (%s, %s, %s, %s, %s)",
                               (self.uid, mode, (unit or "") if mode == "UNIT" else "",
                                int(source_id or 0) if mode == "YEAR" else 0, len(picked)))
            rows = []
            for i, r in enumerate(picked):
                perm = make_perm(r["pin_last"], shuffle)
                rows.append((aid, i + 1, r["id"], perm, perm.index(str(ans[r["id"]])) + 1))
            self.db.exec_many("INSERT INTO qz_answer (attempt_id, seq, qid, perm, correct_pos) VALUES (%s, %s, %s, %s, %s)",
                              rows)
        self.log("quiz_start", aid, "%s %s 題" % (MODES[mode], len(picked)))
        return aid

    def attempt(self, aid):
        """一次測驗的完整內容：題目依換位後的順序給選項；交卷前不回傳正確答案。"""
        t = self.db.row("SELECT * FROM qz_attempt WHERE id=%s", (aid,))
        if not t or (t["uid"] != self.uid and not self.can("RPT", 1)):
            raise BizError("找不到這次測驗")
        done = t["status"] == "DONE"
        rows = self.db.rows("SELECT x.*, q.stem, q.opt1, q.opt2, q.opt3, q.opt4, q.unit, q.bank_no FROM qz_answer x "
                            "JOIN qb_question q ON q.id=x.qid WHERE x.attempt_id=%s ORDER BY x.seq", (aid,))
        items = []
        for r in rows:
            opts = [r["opt%s" % k] for k in r["perm"]]
            it = {"seq": r["seq"], "qid": r["qid"], "stem": r["stem"], "options": opts, "chosen": r["chosen"],
                  "unit": r["unit"], "bank_no": r["bank_no"]}
            if done:
                it["correct_pos"] = r["correct_pos"]
                it["is_correct"] = r["is_correct"]
            items.append(it)
        return {"attempt": t, "items": items, "done": done}

    def answer(self, aid, seq, chosen):
        t = self.db.row("SELECT uid, status FROM qz_attempt WHERE id=%s", (aid,))
        if not t or t["uid"] != self.uid:
            raise BizError("找不到這次測驗")
        if t["status"] != "OPEN":
            raise BizError("這次測驗已經交卷")
        chosen = int(chosen or 0)
        if chosen not in (0, 1, 2, 3, 4):
            raise BizError("選項不正確")
        self.db.exec("UPDATE qz_answer SET chosen=%s WHERE attempt_id=%s AND seq=%s", (chosen, aid, seq))

    def submit(self, aid, seconds=0, answers=None):
        """交卷評分。answers＝{seq: 位置}（一次送出全部作答，可省略）。"""
        t = self.db.row("SELECT * FROM qz_attempt WHERE id=%s", (aid,))
        if not t or t["uid"] != self.uid:
            raise BizError("找不到這次測驗")
        if t["status"] != "OPEN":
            raise BizError("這次測驗已經交卷")
        with self.db.transaction():
            if answers:
                self.db.exec_many("UPDATE qz_answer SET chosen=%s WHERE attempt_id=%s AND seq=%s",
                                  [(int(v or 0), aid, int(k)) for k, v in answers.items()])
            self.db.exec("UPDATE qz_answer SET is_correct=(chosen=correct_pos) WHERE attempt_id=%s", (aid,))
            s = self.db.row("SELECT COUNT(*) n, SUM(chosen>0) answered, SUM(is_correct) ok FROM qz_answer "
                            "WHERE attempt_id=%s", (aid,))
            n, ok = int(s["n"] or 0), int(s["ok"] or 0)
            score = round(ok * 100.0 / n, 1) if n else 0
            self.db.exec("UPDATE qz_attempt SET status='DONE', answered=%s, correct=%s, score=%s, finished_at=NOW(), "
                         "seconds=%s WHERE id=%s", (int(s["answered"] or 0), ok, score, int(seconds or 0), aid))
        self.log("quiz_submit", aid, "%s 分（%d/%d）" % (score, ok, n))
        return self.result(aid)

    def abandon(self, aid):
        t = self.db.row("SELECT uid, status FROM qz_attempt WHERE id=%s", (aid,))
        if t and t["uid"] == self.uid and t["status"] == "OPEN":
            self.db.exec("DELETE FROM qz_answer WHERE attempt_id=%s", (aid,))
            self.db.exec("DELETE FROM qz_attempt WHERE id=%s", (aid,))

    def result(self, aid):
        t = self.db.row("SELECT * FROM qz_attempt WHERE id=%s", (aid,))
        if not t or (t["uid"] != self.uid and not self.can("RPT", 1)):
            raise BizError("找不到這次測驗")
        by_unit = self.db.rows("SELECT q.unit, u.name, COUNT(*) n, SUM(x.is_correct) ok FROM qz_answer x "
                               "JOIN qb_question q ON q.id=x.qid LEFT JOIN qb_unit u ON u.code=q.unit "
                               "WHERE x.attempt_id=%s GROUP BY q.unit ORDER BY u.sort", (aid,))
        c = self.company()
        return {"attempt": t, "by_unit": by_unit, "pass": float(t["score"]) >= int(c.get("pass_score") or 60),
                "pass_score": int(c.get("pass_score") or 60)}

    # ================================================================ 成績與成長
    def history(self, uid=None, limit=500):
        uid = uid or self.uid
        if uid != self.uid:
            self.need("RPT", 1)
        return self.db.rows("SELECT t.*, u.name unit_name, s.year src_year FROM qz_attempt t "
                            "LEFT JOIN qb_unit u ON u.code=t.unit LEFT JOIN qb_source s ON s.id=t.source_id "
                            "WHERE t.uid=%s AND t.status='DONE' ORDER BY t.finished_at, t.id LIMIT %s", (uid, limit))

    def growth(self, uid=None):
        """成長圖表：每次成績、各單元答對率（全部與最近 5 次）。"""
        uid = uid or self.uid
        hist = self.history(uid)
        recent = [h["id"] for h in hist[-5:]]
        units = self.db.rows(
            "SELECT q.unit, u.name, COUNT(*) n, SUM(x.is_correct) ok, "
            "SUM(x.attempt_id IN (%s)) rn, SUM(x.is_correct AND x.attempt_id IN (%s)) rok "
            "FROM qz_answer x JOIN qz_attempt t ON t.id=x.attempt_id JOIN qb_question q ON q.id=x.qid "
            "LEFT JOIN qb_unit u ON u.code=q.unit WHERE t.uid=%%s AND t.status='DONE' GROUP BY q.unit ORDER BY u.sort"
            % (((",".join(str(i) for i in recent) or "0"),) * 2), (uid,))
        for u in units:
            u["rate"] = round(int(u["ok"] or 0) * 100.0 / u["n"], 1) if u["n"] else 0
            u["recent_rate"] = round(int(u["rok"] or 0) * 100.0 / int(u["rn"]), 1) if u["rn"] else None
        scores = [float(h["score"]) for h in hist]
        summary = {"count": len(hist), "best": max(scores) if scores else 0, "last": scores[-1] if scores else 0,
                   "avg": round(sum(scores) / len(scores), 1) if scores else 0,
                   "first": scores[0] if scores else 0, "wrong": len(self._wrong_ids(uid))}
        return {"history": hist, "units": units, "summary": summary}

    def score_board(self):
        """所有使用者的成績摘要（成績統計權限）。"""
        self.need("RPT", 1)
        return self.db.rows(
            "SELECT u.uid, u.name, u.dept, COUNT(t.id) n, MAX(t.score) best, ROUND(AVG(t.score),1) avg, "
            "MAX(t.finished_at) last_at, (SELECT score FROM qz_attempt z WHERE z.uid=u.uid AND z.status='DONE' "
            "ORDER BY z.finished_at DESC, z.id DESC LIMIT 1) last_score "
            "FROM sys_user u LEFT JOIN qz_attempt t ON t.uid=u.uid AND t.status='DONE' "
            "GROUP BY u.uid ORDER BY u.uid")

    def hard_questions(self, limit=50):
        """最常答錯的題目。"""
        self.need("RPT", 1)
        return self.db.rows(
            "SELECT q.id, q.unit, q.bank_no, q.stem, COUNT(*) n, SUM(x.is_correct) ok, "
            "ROUND(100 - SUM(x.is_correct) * 100.0 / COUNT(*), 1) wrong_rate FROM qz_answer x "
            "JOIN qz_attempt t ON t.id=x.attempt_id AND t.status='DONE' JOIN qb_question q ON q.id=x.qid "
            "GROUP BY q.id HAVING n >= 2 ORDER BY wrong_rate DESC, n DESC LIMIT %s", (limit,))
