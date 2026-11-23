"""AI 試題解說：用 Claude API 產生一題的解說（補產生沒有內建解說的新題目）。

解說一律用選項的「文字」說明，不寫選項編號或字母，因為出題時選項順序會隨機換位置。
"""
import re

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM = (
    "你是台灣照顧服務員單一級技術士學科測驗的資深講師，替學員寫試題解說。"
    "規則：繁體中文、台灣用語，80～160 字；先說正確答案為什麼對（引用答案文字），"
    "再簡短說明其他選項錯在哪裡，最後一句「記憶小訣竅：…」。"
    "絕對不要寫選項編號或字母（①②③④、A/B/C/D、第幾個選項），一律用選項文字稱呼；"
    "以題目給的正確答案為準；不確定的數字或法條條號不要編造。只輸出解說本文，不要標題、不要 Markdown、不要換行。"
)


class AIError(Exception):
    pass


def explain(api_key, question, model=None):
    """question：dict(stem, options[4], answer_text, unit)。回傳解說文字。"""
    if not api_key:
        raise AIError("尚未設定 Claude API 金鑰（系統管理 → 測驗設定）")
    try:
        import anthropic
    except ImportError:
        raise AIError("缺少 anthropic 套件")
    client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2)
    opts = "\n".join("・" + re.sub(r"\[\[img:\d+\]\]", "（附圖）", o) for o in question["options"])
    prompt = ("單元：%s\n題目：%s\n選項：\n%s\n正確答案：%s" % (
        question.get("unit", ""), re.sub(r"\[\[img:\d+\]\]", "（附圖）", question["stem"]), opts,
        re.sub(r"\[\[img:\d+\]\]", "（附圖）", question["answer_text"])))
    try:
        resp = client.beta.messages.create(
            model=model or DEFAULT_MODEL, max_tokens=2000, system=SYSTEM,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": prompt}])
    except anthropic.AuthenticationError:
        raise AIError("Claude API 金鑰不正確")
    except anthropic.RateLimitError:
        raise AIError("AI 使用量已達上限，請稍後再試")
    except anthropic.APIStatusError as e:
        raise AIError("AI 服務錯誤（%s）：%s" % (e.status_code, e.message))
    except anthropic.APIConnectionError:
        raise AIError("無法連線 AI 服務，請確認網路")
    if resp.stop_reason == "refusal":
        raise AIError("AI 拒絕產生這題的解說")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = re.sub(r"\s*\n\s*", "", text)
    if not text:
        raise AIError("AI 沒有回傳內容")
    return text
