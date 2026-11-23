r"""匯入 PDF、比對、統計、出題換位、交卷評分。PDF 在 E:\照顧服務員學科\PDF（沒有就略過）。"""
import glob
import os

import pytest

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "PDF")
BANK = os.path.join(PDF_DIR, "照顧服務員學科.pdf")
need_pdf = pytest.mark.skipif(not os.path.isfile(BANK), reason="沒有題庫 PDF")


def _read(p):
    with open(p, "rb") as f:
        return f.read()


@need_pdf
def test_import_all(biz):
    st = biz.import_pdf(_read(BANK), "照顧服務員學科.pdf")
    assert st["kind"] == "BANK" and st["total"] == 625 and st["new"] == 623
    s = biz.bank_stats()
    units = {u["code"]: u for u in s["units"]}
    assert units["01"]["total"] == 191 and units["06"]["name"] == "職業倫理"
    assert s["total"]["deleted"] == 3 and s["total"]["usable"] == 620
    with pytest.raises(Exception):
        biz.import_pdf(_read(BANK), "again.pdf")                 # 同一份不能匯兩次
    for f in sorted(glob.glob(os.path.join(PDF_DIR, "1*.pdf"))):
        r = biz.import_pdf(_read(f), os.path.basename(f))
        assert r["total"] == 80 and r["same"] + r["new"] == 80
        assert r["same"] >= 50, (f, r)                           # 大部分考題都在題庫裡
    r = biz.import_pdf(_read(os.path.join(PDF_DIR, "照顧服務員考古題115.pdf")), "115.pdf")
    assert r["year"] == 115
    s = biz.bank_stats()
    assert s["images"] >= 2                                      # 圖片題（資源回收標誌、標章）
    img_q = biz.questions(status="img")
    assert img_q and all("[[img:" in (q["stem"] + q["opt1"]) for q in img_q)
    im = biz.image(int(__import__("re").search(r"img:(\d+)", img_q[0]["stem"]).group(1)))
    assert im["png"][:4] == b"\x89PNG"
    # 歷屆才有的題目：共同科目會分到 07～10
    common = sum(u["total"] for u in s["units"] if u["grp"] == "COMMON")
    assert common > 30
    q = biz.questions(year=114)
    assert len(q) == 80


@need_pdf
def test_quiz_flow(biz):
    biz.import_pdf(_read(BANK), "bank.pdf")
    aid = biz.start_quiz("MOCK")
    a = biz.attempt(aid)
    assert len(a["items"]) == 100 and not a["done"]
    assert len({it["qid"] for it in a["items"]}) == 100
    # 選項換位後，正確答案的文字仍然是原本的正確答案
    rows = biz.db.rows("SELECT x.*, q.answer, q.opt1, q.opt2, q.opt3, q.opt4 FROM qz_answer x JOIN qb_question q "
                       "ON q.id=x.qid WHERE attempt_id=%s", (aid,))
    moved = 0
    for r in rows:
        shown = [r["opt%s" % k] for k in r["perm"]]
        assert shown[r["correct_pos"] - 1] == r["opt%d" % r["answer"]]
        moved += r["correct_pos"] != r["answer"]
    assert moved > 30                                            # 真的有換位置
    # 依單元比例：01 身體照顧 191/620 ≈ 31 題
    n01 = sum(1 for it in a["items"] if it["unit"] == "01")
    assert 28 <= n01 <= 33
    ans = {r["seq"]: (r["correct_pos"] if r["seq"] <= 70 else 0) for r in rows}
    res = biz.submit(aid, 600, ans)
    assert float(res["attempt"]["score"]) == 70.0 and res["pass"]
    g = biz.growth()
    assert g["summary"]["count"] == 1 and g["summary"]["wrong"] == 30
    aid2 = biz.start_quiz("WRONG")
    assert len(biz.attempt(aid2)["items"]) == 30
    aid3 = biz.start_quiz("UNIT", unit="05")
    assert all(it["unit"] == "05" for it in biz.attempt(aid3)["items"])
    assert biz.open_attempt()["id"] == aid3                     # 開新測驗會取代未交卷的


def test_allocate():
    from cq.quiz import allocate
    out = allocate({"01": 191, "02": 102, "03": 72, "04": 87, "05": 101, "06": 67}, 100)
    assert sum(out.values()) == 100 and out["01"] == 31


def test_seed_bank(db):
    """全新安裝：內建基本題庫自動載入，可直接出 100 題；同一份 PDF 再匯入會被判定為已匯入過。"""
    from cq import seedbank
    from cq.biz import Biz
    n = seedbank.load(db)
    assert n > 800
    assert seedbank.load(db) == 0                                  # 已有題目就不再載入
    b = Biz(db)
    b.create_first_admin("admin", "管理員", "admin123")
    b.login("admin", "admin123")
    s = b.bank_stats()
    assert s["total"]["usable"] > 800 and s["images"] >= 3 and len(s["sources"]) == 16
    aid = b.start_quiz("MOCK")
    assert len(b.attempt(aid)["items"]) == 100
    if os.path.isfile(BANK):
        with pytest.raises(Exception):
            b.import_pdf(_read(BANK), "照顧服務員學科.pdf")


def test_explain_and_review(db):
    """內建題庫每題都有解說；解說不寫選項編號；單元複習的選項換位後正確位置仍指向正確答案。"""
    import re
    from cq import seedbank
    from cq.biz import Biz
    seedbank.load(db)
    b = Biz(db)
    b.create_first_admin("admin", "管理員", "admin123")
    b.login("admin", "admin123")
    assert b.missing_explain_ids() == []
    for r in db.rows("SELECT explain_text FROM qb_question WHERE deleted=0"):
        assert not re.search(r"[①②③④]", r["explain_text"])
    items = b.review_items("01")
    assert len(items) > 150
    for it in items[:50]:
        q = db.row("SELECT * FROM qb_question WHERE id=%s", (it["qid"],))
        assert it["options"][it["correct_pos"] - 1] == q["opt%d" % q["answer"]]
        assert it["explain"]
    aid = b.start_quiz("UNIT", unit="02")
    b.submit(aid, 10, {})
    done = b.attempt(aid)
    assert all(x["explain"] for x in done["items"])


def test_fill_explanations(db):
    """舊版載入的題庫沒有解說：開啟時依比對鍵補上，不覆蓋已有的。"""
    from cq import seedbank
    seedbank.load(db)
    db.exec("UPDATE qb_question SET explain_text=NULL")
    db.exec("UPDATE qb_question SET explain_text='自己寫的' WHERE id=(SELECT MIN(id) FROM (SELECT id FROM qb_question) t)")
    n = seedbank.fill_explanations(db)
    assert n > 800
    assert db.value("SELECT explain_text FROM qb_question ORDER BY id LIMIT 1") == "自己寫的"
