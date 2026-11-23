r"""產生線上版（GitHub Pages，docs/）用到的資料與素材。

* docs/img/：程式圖示（PWA 192／512、favicon、apple-touch-icon 180）、題目裡的圖片 docs/img/q/<編號>.png
* docs/app/bank.js：內建基本題庫（題目、選項、答案、單元、AI 解說、歷屆試題題序），直接從 assets/seed/bank.json.gz 轉出
* docs/voice/<課程>.mp3：線上版語音動態教學旁白（微軟神經語音 曉臻，免費；已存在且文字沒變就略過）

用法：.venv\Scripts\python tools\make_pages.py   （產生旁白需要網路）
"""
import asyncio
import base64
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

from cq import APP_VERSION  # noqa: E402

DOCS = os.path.join(HERE, "docs")
VOICE = "zh-TW-HsiaoChenNeural"

# 線上版的語音教學（和桌面版不同：沒有匯入 PDF、帳號權限，紀錄存在這台裝置的瀏覽器）
LESSONS = [
    dict(key="web_intro", title="認識線上版", steps=[
        "內建 897 題基本題庫", "每次 100 題，選項隨機換位置", "每題都有 AI 解說", "成績存在這台裝置"],
        voice=("歡迎使用資料助秘照顧服務員學科測驗線上版。線上版內建勞動部照顧服務員單一級技術士的學科題庫，"
               "以及一百零四年到一百一十五年的學科測試試題，合併起來將近九百題，不用安裝、不用匯入就可以練習。"
               "每次測驗隨機抽一百題，選項的順序每次都會換位置，例如題庫的 A 可能變成 B，正確答案也會跟著變，"
               "所以要真的看懂內容才答得對。每一題都有 AI 寫好的解說，告訴你為什麼對、其他選項錯在哪裡，還有記憶小訣竅。"
               "你的成績和錯題會存在這台裝置的瀏覽器裡，換手機或電腦可以用備份檔帶過去。")),
    dict(key="web_quiz", title="開始測驗與作答", steps=[
        "選擇測驗方式", "點選選項作答，可以更改", "題號格看進度、跳題", "交卷看分數與解說"],
        voice=("按開始測驗，先選測驗方式。模擬測驗會依照各單元題數的比例抽一百題，最像正式考試；"
               "單元練習只出你選的單元；歷屆試題照某一年的考卷原本的題目順序；錯題複習只出你上次答錯的題目。"
               "作答時直接點選項，選錯了再點別的就能改。一頁十題，上面的題號格會顯示哪些已經作答，點題號可以直接跳過去。"
               "時間到或按交卷就會評分，每一題都會標出正確答案，答錯的題目會用紅色標示，下面附 AI 解說，"
               "按朗讀可以聽題目、答案和解說。")),
    dict(key="web_review", title="單元複習與 AI 解說", steps=[
        "選單元、輸入關鍵字", "先想答案再看解說", "只看我的錯題", "自然語音朗讀"],
        voice=("單元複習可以一個單元一個單元瀏覽題庫。先選單元，也可以輸入關鍵字，例如鼻胃管或心肺復甦術。"
               "建議先自己想答案，再按看答案與解說；如果只想快速看過一遍，可以勾選直接顯示答案。"
               "勾選只看我的錯題，就只會列出你最近答錯的題目。每一題都可以按朗讀，"
               "用自然的語音念出題目、正確答案和解說，走路或通勤時也可以用聽的複習。")),
    dict(key="web_growth", title="成績與成長圖表", steps=[
        "每次分數折線圖", "各單元答對率", "最常答錯的題目", "備份與還原紀錄"],
        voice=("成長圖表會把每一次交卷的分數畫成折線，虛線是及格分數六十分，看得出自己有沒有進步。"
               "下面是各單元的答對率，答對率低的單元就多用單元練習加強；最常答錯的題目也會列出來，按一下就能看解說。"
               "紀錄存在這台裝置的瀏覽器，清除瀏覽器資料會不見，建議偶爾到設定按備份紀錄，存成一個檔案，"
               "之後在別的裝置按還原紀錄就能接著練習。")),
]


def icons():
    out = os.path.join(DOCS, "img")
    os.makedirs(out, exist_ok=True)
    src = Image.open(os.path.join(HERE, "assets", "icon.png")).convert("RGBA")
    for name, size in (("icon-512.png", 512), ("icon-192.png", 192), ("favicon-64.png", 64)):
        src.resize((size, size), Image.LANCZOS).save(os.path.join(out, name))
    bg = Image.new("RGBA", src.size, (14, 116, 104, 255))          # apple-touch-icon 不能透明
    Image.alpha_composite(bg, src).convert("RGB").resize((180, 180), Image.LANCZOS).save(
        os.path.join(out, "apple-touch-icon.png"))


def bank():
    with gzip.open(os.path.join(HERE, "assets", "seed", "bank.json.gz"), "rt", encoding="utf-8") as f:
        d = json.load(f)
    qdir = os.path.join(DOCS, "img", "q")
    os.makedirs(qdir, exist_ok=True)
    imgs = {}
    for im in d["qb_image"]:
        name = "%d.png" % im["id"]
        with open(os.path.join(qdir, name), "wb") as f:
            f.write(base64.b64decode(im["png"]["b64"]))
        # 顯示大小：PDF 上的點數 ×2（手機上才看得清楚）
        imgs[im["id"]] = [int(im["disp_w"] or im["w"]) * 2, int(im["disp_h"] or im["h"]) * 2]
    units = [dict(c=u["code"], n=u["name"], g=u["grp"]) for u in sorted(d["qb_unit"], key=lambda u: u["sort"])]
    srcs = sorted(d["qb_source"], key=lambda s: (s["kind"], -(s["year"] or 0)))
    banks = [s for s in d["qb_source"] if s["kind"] == "BANK"]
    latest = max(banks, key=lambda s: (s["year"] or 0, s["id"]))["id"] if banks else 0
    appear = {}
    for a in d["qb_appear"]:
        appear.setdefault(a["source_id"], []).append((a["no"] or 0, a["qid"]))
    in_latest = {q for no, q in appear.get(latest, [])}
    common = {u["code"] for u in d["qb_unit"] if u["grp"] == "COMMON"}
    qs = []
    alive = set()
    for q in sorted(d["qb_question"], key=lambda q: q["id"]):
        if not q["active"] or q["deleted"]:
            continue
        alive.add(q["id"])
        qs.append(dict(
            i=q["id"], u=q["unit"], b=q["bank_no"] or "", s=q["stem"], o=[q["opt1"], q["opt2"], q["opt3"], q["opt4"]],
            a=q["answer"], p=1 if q["pin_last"] else 0, r=q["origin"], f=q["first_year"] or 0, l=q["last_year"] or 0,
            x=q["exam_count"] or 0, e=q["explain_text"] or "",
            n=1 if (q["id"] in in_latest or q["unit"] in common or q["origin"] == "MANUAL") else 0))
    sources = []
    for s in srcs:
        ids = [qid for no, qid in sorted(appear.get(s["id"], [])) if qid in alive]
        sources.append(dict(id=s["id"], k=s["kind"], y=s["year"], t=s["title"], q=ids if s["kind"] == "EXAM" else [],
                            c=len(ids)))
    data = dict(v=APP_VERSION, units=units, sources=sources, q=qs, img=imgs,
                lessons=[dict(k=s["key"], t=s["title"], st=s["steps"], v=s["voice"]) for s in LESSONS])
    js = "/* 由 tools/make_pages.py 從內建題庫產生，請勿手動修改 */\nwindow.BANK=" + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    os.makedirs(os.path.join(DOCS, "app"), exist_ok=True)
    with open(os.path.join(DOCS, "app", "bank.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    return len(qs), len(js.encode("utf-8"))


async def lesson_voice():
    import edge_tts
    out = os.path.join(DOCS, "voice")
    os.makedirs(out, exist_ok=True)
    stamp_path = os.path.join(out, "voice.json")
    stamps = json.load(open(stamp_path, encoding="utf-8")) if os.path.isfile(stamp_path) else {}
    for s in LESSONS:
        path = os.path.join(out, s["key"] + ".mp3")
        h = hashlib.sha1((VOICE + s["voice"]).encode("utf-8")).hexdigest()
        if stamps.get(s["key"]) == h and os.path.isfile(path):
            continue
        for n in range(5):
            try:
                await edge_tts.Communicate(s["voice"], VOICE, rate="+5%").save(path)
                stamps[s["key"]] = h
                break
            except Exception as ex:                                  # edge-tts 偶爾回 503
                print("retry", s["key"], ex)
                await asyncio.sleep(3 + n * 3)
    with open(stamp_path, "w", encoding="utf-8") as f:
        json.dump(stamps, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    icons()
    n, size = bank()
    print("題庫 %d 題，bank.js %.0f KB" % (n, size / 1024))
    asyncio.run(lesson_voice())
    print("OK", APP_VERSION)
