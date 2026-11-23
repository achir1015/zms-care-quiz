# 資料助秘照顧服務員學科測驗
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/64a8bb44-f110-468d-b870-de58b6a023d5" />
示範


https://github.com/user-attachments/assets/2706bc8c-9d47-4d24-a061-f9723f6ac28d


照顧服務員單一級技術士學科測驗練習系統。匯入每年的學科測驗 PDF，自動依單元拆出題目、四個選項、正確答案與圖片，
存進 MariaDB；每次隨機出 100 題，選項順序隨機換位置（正確答案跟著變），記錄每次成績並畫出成長圖表。

## 下載

- **Windows 11**：到 [Releases](https://github.com/achir1015/zms-care-quiz/releases/latest) 下載 `ZMSCareQuiz-Setup-1.0.0.exe`，安裝後桌面會有捷徑，打開就能用（資料庫內建，自動啟動與停止）。
- 第一次開啟會自動載入**內建基本題庫 897 題（889 題可出題），每題附 AI 解說**；第一次使用請建立系統管理員帳號。

## 功能

- **匯入 PDF 自動拆題**：題庫參考資料（178004A13，依六個工作項目分單元）與每年度學科測試試題（104～115 年）。
  題目或選項裡的圖片（例如資源回收標誌、省水標章）以 `[[img:編號]]` 存在文字中，圖片本身存在 `qb_image`（MEDIUMBLOB）。
- **每年題目記錄**：題庫已有的題目只記錄「這年度有考」（`qb_appear`）；新的題目加進題庫，並依最相似的題庫題目或
  共同科目關鍵字自動判斷單元（職業安全衛生、工作倫理與職業道德、環境保護、節能減碳）。
- **出題**：模擬測驗（依各單元題數比例抽 100 題）、單元練習、歷屆試題、錯題複習；選項每次隨機換位置，
  「以上皆是／以上皆非」固定在最後。
- **統計**：各單元題庫數、總題庫數、每年度新增題數、每年考卷各單元題數。
- **成績與成長圖表**：每次分數折線圖、各單元答對率（含最近 5 次趨勢）、最常答錯的題目。
- **使用者權限**：測驗練習、題庫查詢與維護、匯入 PDF、成績統計、系統管理五項（無／查詢／維護）。
- **內建基本題庫**：16 份 PDF（106／114／115 年版題庫、114 參考題庫、104～115 年度學科測試試題）合併而成，安裝後免匯入即可練習。
- **AI 試題解說**：每題說明為什麼對、其他選項錯在哪、記憶小訣竅；用選項文字說明，選項換位也正確。
  新題目可填 Claude API 金鑰補產生。
- **單元複習**：依單元瀏覽題庫、先想再看答案與解說、只看錯題；自然語音（微軟神經語音）朗讀題目、答案與解說。
- **語音動態教學**、程式內更新、桌面捷徑、備份還原。

## 平台

| 平台 | 狀態 |
|---|---|
| Windows 11 | ✅ v1.0.0 |
| MacBook Pro | 規劃中 |
| 線上版（HTML） | 規劃中 |
| iPhone／iPad（線上安裝） | 規劃中 |
| Android | 規劃中 |

## 開發

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install flet==1.1.2 flet-audio==1.1.2 flet-desktop==1.1.2 flet-web==1.1.2 pymysql certifi edge-tts pillow pyinstaller qrcode pymupdf pytest
.venv\Scripts\python tools\demo_data.py --reset     # 開發資料庫：admin/admin123、student/student1，匯入 ..\PDF
.venv\Scripts\python main.py                         # 桌面版
.venv\Scripts\python run_web.py                      # 網頁預覽 http://127.0.0.1:8650
.venv\Scripts\python -m pytest -q tests
.venv\Scripts\python tools\build_windows.py          # 安裝檔 dist-installer\ZMSCareQuiz-Setup-版本.exe
```

資料庫埠：開發與安裝版 3458、測試 3468。題庫 PDF 不放進儲存庫（放在上一層 `PDF\`）。

系統開發：吳玉柱 先生 與 Claude AI Opus 5.5
