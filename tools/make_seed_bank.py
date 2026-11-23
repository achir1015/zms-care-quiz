r"""產生內建基本題庫 assets/seed/bank.json.gz：在暫時的測試資料庫匯入 ..\PDF（含 ..\PDF\使用者提供）全部 PDF 後匯出。

匯入順序：最新版題庫 → 舊版題庫 → 參考題庫 → 各年度學科測試試題（舊到新）。
用法：.venv\Scripts\python tools\make_seed_bank.py
"""
import glob
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TMP = tempfile.mkdtemp(prefix="cq-seed-")
os.environ["CQ_DATA_DIR"] = TMP

from cq import pdfparse, seedbank  # noqa: E402
from cq.biz import Biz  # noqa: E402
from cq.database import DB  # noqa: E402
from cq.dbserver import LocalDatabaseServer  # noqa: E402
from cq.settings import Settings, find_mariadb  # noqa: E402

PDF = os.path.join(os.path.dirname(HERE), "PDF")
files = sorted(glob.glob(os.path.join(PDF, "*.pdf")) + glob.glob(os.path.join(PDF, "*", "*.pdf")))
info = []
for f in files:
    r = pdfparse.parse(f, os.path.basename(f))
    info.append((f, r["kind"], r["year"]))
order = {"BANK": 0, "REF": 1, "EXAM": 2}
info.sort(key=lambda x: (order[x[1]], -x[2] if x[1] != "EXAM" else x[2], x[0]))

st = Settings(port=3478, password="seed-pw-123", database="cq_seed", mariadb_bin=find_mariadb(),
              datadir=os.path.join(TMP, "mariadb"))
srv = LocalDatabaseServer(st)
srv.start()
try:
    db = DB(st)
    os.environ["CQ_NO_SEED"] = "1"
    db.prepare()
    b = Biz(db)
    b.create_first_admin("seed", "內建題庫", "seed-pw-123")
    b.login("seed", "seed-pw-123")
    for f, kind, year in info:
        with open(f, "rb") as fh:
            r = b.import_pdf(fh.read(), os.path.basename(f))
        print("%-5s %s %-40s 拆 %3d 新增 %3d 已有 %3d" % (kind, year, os.path.basename(f), r["total"], r["new"], r["same"]))
        db.exec("UPDATE qb_source SET imported_by='內建' WHERE id=%s", (r["source_id"],))
    # 內建 AI 解說（tools/data/explanations.json.gz：依比對鍵；題目文字修正過的用相似度帶入）
    import gzip
    import json
    from cq.bank import _Index
    exp_path = os.path.join(HERE, "tools", "data", "explanations.json.gz")
    if os.path.isfile(exp_path):
        exps = json.load(gzip.open(exp_path, "rt", encoding="utf-8"))
        by_key = {x["key"]: x["explain"] for x in exps}
        ref = _Index([{"id": i, "unit": "", "stem": x["stem"], "opt1": x["options"][0], "opt2": x["options"][1],
                       "opt3": x["options"][2], "opt4": x["options"][3],
                       "answer": x["options"].index(x["answer_text"]) + 1, "norm_key": x["key"]}
                      for i, x in enumerate(exps)])
        hit = fuzzy = 0
        for q in db.rows("SELECT id, stem, opt1, opt2, opt3, opt4, answer, norm_key FROM qb_question WHERE deleted=0"):
            e = by_key.get(q["norm_key"])
            if e:
                hit += 1
            else:
                opts = [q["opt%d" % i] for i in range(1, 5)]
                top, score, same = ref.best(q["stem"], opts, q["answer"])
                if top and score >= 0.85 and same is not None:
                    e = by_key.get(top["row"]["norm_key"])
                    fuzzy += 1
            if e:
                db.exec("UPDATE qb_question SET explain_text=%s, explain_by='內建 AI', explain_at=NOW() WHERE id=%s",
                        (e, q["id"]))
        print("解說：比對鍵 %d 題、相似度 %d 題、沒有 %d 題" % (hit, fuzzy, db.value(
            "SELECT COUNT(*) FROM qb_question WHERE deleted=0 AND (explain_text IS NULL OR explain_text='')")))
    out = os.path.join(HERE, "assets", "seed", "bank.json.gz")
    print(seedbank.dump(db, out), "%.1f MB" % (os.path.getsize(out) / 1e6))
    print(b.bank_stats()["total"])
    db.close()
finally:
    srv.stop()
    shutil.rmtree(TMP, ignore_errors=True)
