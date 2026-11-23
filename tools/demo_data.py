r"""開發用：在開發資料庫（data/）建立 admin/admin123、學員 student/student1，匯入 ..\PDF 的全部 PDF，
並替學員做幾次練習（讓成長圖表有資料）。用法：python tools/demo_data.py [--reset]"""
import glob
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cq.biz import Biz  # noqa: E402
from cq.database import DB  # noqa: E402
from cq.dbserver import LocalDatabaseServer  # noqa: E402
from cq.settings import Settings  # noqa: E402

PDF_DIR = os.path.join(os.path.dirname(HERE), "PDF")

st = Settings.load()
srv = LocalDatabaseServer(st)
srv.start()
try:
    db = DB(st)
    if "--reset" in sys.argv:
        c = db.connect(use_db=False)
        with c.cursor() as cur:
            cur.execute("DROP DATABASE IF EXISTS `%s`" % st.database)
        c.close()
    db.prepare()
    st.save()
    b = Biz(db)
    if not b.has_users():
        b.create_first_admin("admin", "系統管理員", "admin123")
    b.login("admin", "admin123")
    b.save_company(name="資料助秘長照訓練中心")
    files = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")), key=lambda f: (not os.path.basename(f).startswith("照顧服務員學科"), f))
    for f in files:
        with open(f, "rb") as fh:
            try:
                r = b.import_pdf(fh.read(), os.path.basename(f))
                print(os.path.basename(f), "新增", r["new"], "已有", r["same"], r["by_unit"])
            except Exception as e:
                print(os.path.basename(f), e)
    if not db.value("SELECT 1 FROM sys_user WHERE uid='student'"):
        from cq.seed import ROLES
        b.save_user("student", "王小美", "學員", False, True, ROLES["學員"], pw="student1", is_new=True, dept="115 年第 1 班")
    s = Biz(db)
    s.login("student", "student1")
    if not db.value("SELECT COUNT(*) FROM qz_attempt WHERE uid='student'"):
        for i, rate in enumerate([0.58, 0.64, 0.7, 0.69, 0.78, 0.83, 0.86, 0.91]):
            aid = s.start_quiz("MOCK" if i % 3 != 2 else "UNIT", unit="01")
            rows = db.rows("SELECT seq, correct_pos FROM qz_answer WHERE attempt_id=%s", (aid,))
            ans = {r["seq"]: (r["correct_pos"] if random.random() < rate else (r["correct_pos"] % 4) + 1) for r in rows}
            s.submit(aid, random.randint(1500, 3600), ans)
            db.exec("UPDATE qz_attempt SET finished_at=DATE_SUB(NOW(), INTERVAL %s DAY), "
                    "started_at=DATE_SUB(NOW(), INTERVAL %s DAY) WHERE id=%s", (16 - i * 2, 16 - i * 2, aid))
    print(b.bank_stats()["total"])
finally:
    db.close()
    srv.stop()
