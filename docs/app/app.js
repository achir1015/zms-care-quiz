/* 資料助秘照顧服務員學科測驗 線上版
 * 題庫在 bank.js（tools/make_pages.py 從內建題庫產生）；成績、錯題、設定存在這台裝置的 localStorage。
 * 出題規則與桌面版相同：模擬測驗依單元比例抽題（最大餘數法）、選項隨機換位置（以上皆是／非固定在最後）。 */
"use strict";
const B = window.BANK;
const QM = new Map(B.q.map((q) => [q.i, q]));
const UNIT = Object.fromEntries(B.units.map((u) => [u.c, u]));
const MODES = { MOCK: "模擬測驗", UNIT: "單元練習", YEAR: "歷屆試題", WRONG: "錯題複習" };
const KIND = { BANK: "題庫", REF: "參考題庫", EXAM: "學科測試試題" };
const ORIGIN = { BANK: "題庫", REF: "參考題庫", EXAM: "歷屆才有", MANUAL: "自建" };
const KEYS = "ABCD";
const PER_PAGE = 10;
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");

/* ------------------------------------------------------------------ 儲存 */
const STORE = "zms-care-quiz.v1";
const DEF = { size: 100, pass: 60, time: 100, includeOld: true, shuffle: true, voice: "", rate: 1 };
let S = load();
function load() {
  try {
    const d = JSON.parse(localStorage.getItem(STORE) || "{}");
    return { set: Object.assign({}, DEF, d.set || {}), done: d.done || [], open: d.open || null };
  } catch (e) { return { set: Object.assign({}, DEF), done: [], open: null }; }
}
function save() {
  try { localStorage.setItem(STORE, JSON.stringify(S)); }
  catch (e) { toast("無法儲存紀錄（瀏覽器空間不足或是無痕模式）"); }
}

/* ------------------------------------------------------------------ 小工具 */
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
const IMG_RE = /\[\[img:(\d+)\]\]/g;
function rich(t) {
  return esc(t).replace(IMG_RE, (m, id) => {
    const wh = B.img[id] || [80, 80];
    return `<img src="../img/q/${id}.png" width="${wh[0]}" height="${wh[1]}" alt="題目圖片">`;
  });
}
const plain = (t) => String(t || "").replace(IMG_RE, "〔圖〕");
const sayable = (t) => String(t || "").replace(IMG_RE, "如圖");
function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function sample(a, n) { return shuffle(a.slice()).slice(0, n); }
function fmtSec(s) { s = Math.max(0, Math.round(s)); const m = Math.floor(s / 60); return `${m}:${String(s % 60).padStart(2, "0")}`; }
function fmtDate(t) { const d = new Date(t); return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; }
const fmtScore = (x) => (Math.round(x * 10) / 10).toString();
function unitName(c) { return UNIT[c] ? UNIT[c].n : "待分類"; }
let toastTimer = 0;
function toast(msg, ms = 3200) {
  let el = $(".toast");
  if (!el) { el = document.createElement("div"); el.className = "toast"; document.body.appendChild(el); }
  el.textContent = msg; el.style.display = "block";
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.style.display = "none"; }, ms);
}
function dialog(html, onMount, onClose) {
  const m = document.createElement("div");
  m.className = "mask";
  m.innerHTML = `<div class="dlg">${html}<div class="row" style="margin-top:14px;justify-content:flex-end"><button class="btn out" data-x>關閉</button></div></div>`;
  let closed = false;
  const close = () => { if (closed) return; closed = true; TTS.stop(); m.remove(); if (onClose) onClose(); };
  m.addEventListener("click", (e) => {
    if (e.target === m || e.target.closest("[data-x]")) close();
    const b = e.target.closest("[data-say]"); if (b) speakQ(Number(b.dataset.say), b);
  });
  document.body.appendChild(m);
  if (onMount) onMount(m.querySelector(".dlg"), close);
  return close;
}
function ask(msg, okText = "確定") {
  return new Promise((res) => {
    let ok = false;
    dialog(`<h3>請確認</h3><p>${msg}</p><div class="row" style="justify-content:flex-end"><button class="btn" data-ok>${esc(okText)}</button></div>`,
      (d, close) => { d.querySelector("[data-ok]").onclick = () => { ok = true; close(); }; }, () => res(ok));
  });
}

/* ------------------------------------------------------------------ 語音（瀏覽器內建；優先挑自然語音） */
const TTS = {
  ok: "speechSynthesis" in window,
  btn: null,
  list() {
    if (!this.ok) return [];
    const vs = speechSynthesis.getVoices();
    const tw = vs.filter((v) => /zh[-_]TW/i.test(v.lang));
    const zh = tw.length ? tw : vs.filter((v) => /^zh/i.test(v.lang) && !/HK|yue/i.test(v.lang));
    const rank = (v) => (/Natural|Online|Neural/i.test(v.name) ? 4 : 0) + (/HsiaoChen|曉臻|HsiaoYu|曉雨/i.test(v.name) ? 2 : 0)
      + (/Google/i.test(v.name) ? 1 : 0) + (/Mei-Jia|美佳|Meijia/i.test(v.name) ? 1 : 0);
    return zh.sort((a, b) => rank(b) - rank(a));
  },
  pick() {
    const l = this.list();
    return l.find((v) => v.name === S.set.voice) || l[0] || null;
  },
  natural() { const v = this.pick(); return !!v && /Natural|Online|Neural|Google|Mei-Jia|美佳/i.test(v.name); },
  stop() {
    if (this.ok) speechSynthesis.cancel();
    if (this.btn) { this.btn.classList.remove("on"); this.btn.textContent = "🔊 朗讀"; this.btn = null; }
  },
  speak(text, btn) {
    if (!this.ok) { toast("這個瀏覽器不支援朗讀"); return; }
    const again = btn && this.btn === btn;
    this.stop();
    if (again) return;                                   // 再按一次＝停止
    const v = this.pick();
    // 長文字分句排隊念（Chrome 一次念太長會中斷）
    const parts = String(text).match(/[^。！？；\n]+[。！？；\n]?/g) || [text];
    const chunks = [];
    for (const p of parts) { if (chunks.length && (chunks[chunks.length - 1] + p).length < 90) chunks[chunks.length - 1] += p; else chunks.push(p); }
    if (btn) { this.btn = btn; btn.classList.add("on"); btn.textContent = "⏹ 停止"; }
    chunks.forEach((c, i) => {
      const u = new SpeechSynthesisUtterance(c.trim());
      u.lang = v ? v.lang : "zh-TW"; if (v) u.voice = v;
      u.rate = Number(S.set.rate) || 1;
      if (i === chunks.length - 1) u.onend = () => { if (this.btn === btn) this.stop(); };
      speechSynthesis.speak(u);
    });
  },
};
if (TTS.ok) speechSynthesis.onvoiceschanged = () => { if (location.hash === "#settings") route(); };

/* ------------------------------------------------------------------ 題目資料 */
function poolAll() { return S.set.includeOld ? B.q : B.q.filter((q) => q.n); }
function makePerm(pin) {
  if (!S.set.shuffle) return "1234";
  return pin ? shuffle(["1", "2", "3"]).join("") + "4" : shuffle(["1", "2", "3", "4"]).join("");
}
function allocate(sizes, n) {                         // 依各單元題數比例分配 n 題（最大餘數法）
  const total = Object.values(sizes).reduce((a, b) => a + b, 0);
  if (total <= n) return Object.assign({}, sizes);
  const raw = {}, out = {};
  for (const k in sizes) { raw[k] = sizes[k] * n / total; out[k] = Math.min(sizes[k], Math.floor(raw[k])); }
  let rest = n - Object.values(out).reduce((a, b) => a + b, 0);
  for (const k of Object.keys(raw).sort((a, b) => (raw[b] - Math.floor(raw[b])) - (raw[a] - Math.floor(raw[a])))) {
    if (rest <= 0) break;
    if (out[k] < sizes[k]) { out[k]++; rest--; }
  }
  return out;
}
function wrongIds() {                                  // 最近一次作答答錯的題目（後來答對就不算）
  const last = new Map();
  for (const t of S.done) for (const it of t.items) if (it.ch >= 0) last.set(it.q, it.ch === it.c);
  return [...last].filter(([q, ok]) => !ok && QM.has(q)).map(([q]) => q);
}
function optsOf(q, perm) { return perm.split("").map((d) => q.o[Number(d) - 1]); }

/* ------------------------------------------------------------------ 出題、交卷 */
function startQuiz(mode, unit, src) {
  const n = Math.max(10, Math.min(200, Number(S.set.size) || 100));
  let picked = [];
  if (mode === "MOCK") {
    const by = {};
    for (const q of poolAll()) (by[q.u] = by[q.u] || []).push(q);
    const take = allocate(Object.fromEntries(Object.entries(by).map(([k, v]) => [k, v.length])), n);
    for (const k in by) picked.push(...sample(by[k], take[k] || 0));
    shuffle(picked);
  } else if (mode === "UNIT") {
    picked = sample(poolAll().filter((q) => q.u === unit), n);
  } else if (mode === "YEAR") {
    const s = B.sources.find((x) => x.id === Number(src));
    picked = s ? s.q.map((i) => QM.get(i)).filter(Boolean) : [];
  } else {
    picked = sample(wrongIds().map((i) => QM.get(i)), n);
  }
  if (!picked.length) { toast(mode === "WRONG" ? "你目前沒有答錯的題目 👍" : "沒有可以出題的題目"); return; }
  const items = picked.map((q) => { const p = makePerm(q.p); return { q: q.i, p, c: p.indexOf(String(q.a)) + 1, ch: -1 }; });
  S.open = { id: Date.now(), mode, unit: mode === "UNIT" ? unit : "", src: mode === "YEAR" ? Number(src) : 0,
    start: Date.now(), secs: 0, limit: (Number(S.set.time) || 0) * 60, items, page: 0 };
  save();
  location.hash = "#run";
}
function submit(auto) {
  const t = S.open; if (!t) return;
  const ok = t.items.filter((x) => x.ch === x.c).length;
  t.score = Math.round(ok * 1000 / t.items.length) / 10;
  t.ok = ok; t.end = Date.now(); t.pass = Number(S.set.pass) || 60;
  delete t.page;
  S.done.push(t); S.open = null; save();
  stopTimer();
  if (auto) toast("時間到，已自動交卷");
  location.hash = "#result/" + t.id;
}
function attemptTitle(t) {
  if (t.mode === "UNIT") return "單元練習：" + unitName(t.unit);
  if (t.mode === "YEAR") { const s = B.sources.find((x) => x.id === t.src); return "歷屆試題：" + (s ? s.t : ""); }
  return MODES[t.mode] || t.mode;
}

/* ------------------------------------------------------------------ 題目卡 */
function qCard(q, perm, opts) {
  // opts: {no, chosen, correctPos, reveal, attemptMode, practice}
  const o = optsOf(q, perm);
  const reveal = !!opts.reveal;
  const right = opts.correctPos;
  let cls = "q";
  if (reveal && opts.chosen !== undefined) cls += opts.chosen === right ? " ok" : " bad";
  else if (opts.chosen > 0) cls += " done";
  const tags = [`<span class="tag">${esc(unitName(q.u))}</span>`];
  if (q.b) tags.push(`<span class="tag">題庫 ${esc(q.b)}</span>`);
  else tags.push(`<span class="tag">${q.r === "EXAM" ? "歷屆試題" : esc(ORIGIN[q.r] || "")}${q.f ? " · " + q.f + " 年起" : ""}</span>`);
  if (q.x) tags.push(`<span class="tag">考過 ${q.x} 次</span>`);
  if (reveal && opts.chosen !== undefined) {
    tags.push(opts.chosen === right ? `<span class="tag ok">答對</span>` : opts.chosen > 0 ? `<span class="tag bad">答錯</span>` : `<span class="tag bad">未作答</span>`);
  }
  const btns = o.map((t, i) => {
    const pos = i + 1;
    let c = "opt";
    if (reveal) { if (pos === right) c += " right"; else if (pos === opts.chosen) c += " wrong"; }
    else if (pos === opts.chosen) c += " sel";
    return `<button class="${c}" data-pos="${pos}"><span class="k">${KEYS[i]}</span><span>${rich(t)}</span></button>`;
  }).join("");
  const ex = reveal ? explainHtml(q, o[right - 1]) : (opts.practice ? `<div class="row" style="margin-top:8px"><button class="btn sm out" data-show>看答案與解說</button></div>` : "");
  return `<div class="${cls}" id="q${opts.no}" data-qid="${q.i}">
    <div class="hd">${opts.no !== "" ? `<span class="no">${opts.no}.</span>` : ""}${tags.join(" ")}</div>
    <div class="stem">${rich(q.s)}</div>
    <div class="opts${reveal ? " locked" : ""}">${btns}</div>${ex}</div>`;
}
function explainHtml(q, answerText) {
  const txt = q.e ? `<p>${esc(q.e)}</p>` : `<p class="muted">這題還沒有解說</p>`;
  return `<div class="explain"><div class="eh">💡 正確答案：${rich(answerText)}<button class="say" data-say="${q.i}">🔊 朗讀</button></div>
    <div class="eh" style="margin-top:4px">AI 解說</div>${txt}</div>`;
}
function speakQ(qid, btn, answerText) {
  const q = QM.get(qid);
  if (!answerText) answerText = q.o[q.a - 1];
  TTS.speak(`題目：${sayable(q.s)}。正確答案是：${sayable(answerText)}。${sayable(q.e)}`, btn);
}

/* ------------------------------------------------------------------ 畫面：首頁 */
function vHome() {
  const g = growthData();
  const open = S.open;
  const ws = wrongIds().length;
  view.innerHTML = `
  <h1>照顧服務員學科測驗練習</h1>
  ${open ? `<div class="card" style="border-left:5px solid #F2B630"><div class="row"><div><b>還有一份測驗沒交卷</b><div class="muted">${esc(attemptTitle(open))}，已作答 ${open.items.filter((x) => x.ch > 0).length}／${open.items.length} 題</div></div><span class="sp"></span><a class="btn gold" href="#run">繼續作答</a></div></div>` : ""}
  <div class="tiles">
    <div class="tile"><b>${B.q.length}</b><span>可出題的題目</span></div>
    <div class="tile"><b>${g.count}</b><span>已完成測驗</span></div>
    <div class="tile"><b>${g.count ? fmtScore(g.last) : "—"}</b><span>最近一次分數</span></div>
    <div class="tile"><b>${g.count ? fmtScore(g.best) : "—"}</b><span>最佳分數</span></div>
    <div class="tile"><b>${ws}</b><span>待複習錯題</span></div>
  </div>
  <div class="grid">
    <div class="card mode"><span class="ic">📝</span><b>模擬測驗 ${S.set.size} 題</b><p>依各單元題數比例隨機出題，選項每次換位置，最像正式考試。</p><button class="btn" data-go="MOCK">馬上開始</button></div>
    <div class="card mode" style="border-top-color:var(--accent)"><span class="ic">📖</span><b>單元複習</b><p>一個單元一個單元看題目、答案和 AI 解說，可以用聽的。</p><a class="btn acc" href="#review">開始複習</a></div>
    <div class="card mode" style="border-top-color:#F2B630"><span class="ic">🔁</span><b>錯題複習</b><p>只出你上次答錯的題目（目前 ${ws} 題），答對就會從錯題移除。</p><button class="btn gold" data-go="WRONG" ${ws ? "" : "disabled"}>練習錯題</button></div>
    <div class="card mode" style="border-top-color:#8B5CF6"><span class="ic">🎧</span><b>第一次使用？</b><p>聽 1 分鐘語音教學，了解出題方式、解說和成績紀錄。</p><a class="btn out" href="#learn">語音教學</a></div>
  </div>
  ${g.count ? `<h2>最近成績</h2><div class="card">${chartSvg(g.scores.slice(-20), Number(S.set.pass) || 60)}</div>` : ""}
  <p class="muted">成績與錯題紀錄存在這台裝置的瀏覽器裡；換裝置請到「設定」備份與還原。也可以下載 Windows／Mac 電腦版（可匯入新年度的學科測驗 PDF、多位學員帳號）。</p>`;
  view.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => startQuiz(b.dataset.go)));
}

/* ------------------------------------------------------------------ 畫面：開始測驗 */
function vQuiz() {
  const pool = poolAll();
  const cnt = {};
  for (const q of pool) cnt[q.u] = (cnt[q.u] || 0) + 1;
  const units = B.units.filter((u) => cnt[u.c]);
  const years = B.sources.filter((s) => s.k === "EXAM" && s.c);
  const ws = wrongIds().length;
  view.innerHTML = `<h1>開始測驗</h1>
  ${S.open ? `<div class="card" style="border-left:5px solid #F2B630"><div class="row"><div><b>還有一份測驗沒交卷</b><div class="muted">${esc(attemptTitle(S.open))}；開始新的測驗會放棄這一份</div></div><span class="sp"></span><a class="btn gold" href="#run">繼續作答</a></div></div>` : ""}
  <div class="grid">
    <div class="card mode"><span class="ic">📝</span><b>模擬測驗</b><p>從 ${pool.length} 題中依各單元比例抽 ${Math.min(S.set.size, pool.length)} 題，限時 ${S.set.time ? S.set.time + " 分鐘" : "不限"}。</p><button class="btn" data-m="MOCK">開始</button></div>
    <div class="card mode" style="border-top-color:var(--accent)"><span class="ic">🎯</span><b>單元練習</b><p>只出選定單元的題目（最多 ${S.set.size} 題）。</p>
      <select id="unitSel">${units.map((u) => `<option value="${u.c}">${esc(u.n)}（${cnt[u.c]} 題）</option>`).join("")}</select><button class="btn acc" data-m="UNIT">開始</button></div>
    <div class="card mode" style="border-top-color:#8B5CF6"><span class="ic">📜</span><b>歷屆試題</b><p>照某一年考卷原本的題目順序作答（選項仍會換位置）。</p>
      <select id="yearSel">${years.map((s) => `<option value="${s.id}">${esc(s.t)}（${s.c} 題）</option>`).join("")}</select><button class="btn" style="background:#8B5CF6" data-m="YEAR">開始</button></div>
    <div class="card mode" style="border-top-color:#F2B630"><span class="ic">🔁</span><b>錯題複習</b><p>你最近答錯、還沒再答對的題目：${ws} 題。</p><button class="btn gold" data-m="WRONG" ${ws ? "" : "disabled"}>開始</button></div>
  </div>
  <p class="muted">每次題數、及格分數、測驗時間、是否包含舊版題庫的題目，可以在「設定」調整。</p>`;
  view.querySelectorAll("[data-m]").forEach((b) => (b.onclick = async () => {
    if (S.open && !(await ask("開始新的測驗會放棄還沒交卷的那一份，確定嗎？", "開始新的測驗"))) return;
    startQuiz(b.dataset.m, $("#unitSel")?.value, $("#yearSel")?.value);
  }));
}

/* ------------------------------------------------------------------ 畫面：作答 */
let timer = 0;
function stopTimer() { clearInterval(timer); timer = 0; }
function vRun() {
  const t = S.open;
  if (!t) { location.hash = "#quiz"; return; }
  const pages = Math.ceil(t.items.length / PER_PAGE);
  t.page = Math.min(t.page || 0, pages - 1);
  view.innerHTML = `<div class="runbar">
    <div class="row"><b>${esc(attemptTitle(t))}</b><span class="muted" id="done"></span><span class="sp"></span>
      <span class="timer" id="tm"></span><button class="btn acc sm" id="sub">交卷</button></div>
    <div class="cells" id="cells">${t.items.map((x, i) => `<button class="cell" data-i="${i}">${i + 1}</button>`).join("")}</div></div>
    <div id="qs"></div><div class="pager" id="pg"></div>`;
  const cells = [...view.querySelectorAll(".cell")];
  const paint = () => {
    cells.forEach((c, i) => { c.className = "cell" + (t.items[i].ch > 0 ? " a" : "") + (Math.floor(i / PER_PAGE) === t.page ? " cur" : ""); });
    $("#done").textContent = `已作答 ${t.items.filter((x) => x.ch > 0).length}／${t.items.length}`;
  };
  const show = (page, focus) => {
    t.page = page; save();
    const from = page * PER_PAGE;
    $("#qs").innerHTML = t.items.slice(from, from + PER_PAGE).map((x, k) => qCard(QM.get(x.q), x.p, { no: from + k + 1, chosen: x.ch })).join("");
    $("#pg").innerHTML = `<button class="btn out" id="pv" ${page ? "" : "disabled"}>◀ 上一頁</button><span class="muted">第 ${page + 1}／${pages} 頁</span>`
      + (page < pages - 1 ? `<button class="btn" id="nx">下一頁 ▶</button>` : `<button class="btn acc" id="sub2">交卷</button>`);
    $("#pv").onclick = () => show(page - 1);
    if ($("#nx")) $("#nx").onclick = () => show(page + 1);
    if ($("#sub2")) $("#sub2").onclick = trySubmit;
    paint();
    if (focus !== undefined) $("#q" + (focus + 1))?.scrollIntoView({ behavior: "smooth", block: "start" });
    else window.scrollTo({ top: 0 });
  };
  $("#qs").addEventListener("click", (e) => {
    const b = e.target.closest(".opt"); if (!b) return;
    const card = b.closest(".q"); const i = Number(card.id.slice(1)) - 1;
    t.items[i].ch = Number(b.dataset.pos); save();
    card.querySelectorAll(".opt").forEach((o) => o.classList.toggle("sel", o === b));
    card.classList.add("done");
    paint();
  });
  $("#cells").addEventListener("click", (e) => {
    const c = e.target.closest(".cell"); if (!c) return;
    const i = Number(c.dataset.i); const p = Math.floor(i / PER_PAGE);
    if (p !== t.page) show(p, i); else $("#q" + (i + 1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  const trySubmit = async () => {
    const left = t.items.filter((x) => x.ch <= 0).length;
    if (left && !(await ask(`還有 ${left} 題沒作答（算答錯），確定要交卷嗎？`, "交卷"))) return;
    submit(false);
  };
  $("#sub").onclick = trySubmit;
  const tick = () => {
    const el = $("#tm"); if (!el || !S.open) { stopTimer(); return; }
    if (t.limit) { const left = t.limit - t.secs; el.textContent = "⏱ 剩 " + fmtSec(left); el.classList.toggle("low", left < 300); if (left <= 0) { submit(true); return; } }
    else el.textContent = "⏱ " + fmtSec(t.secs);
  };
  stopTimer();
  let n = 0;
  timer = setInterval(() => { if (document.hidden) return; t.secs++; if (++n % 5 === 0) save(); tick(); }, 1000);
  tick();
  show(t.page);
}

/* ------------------------------------------------------------------ 畫面：成績與每題解說 */
function vResult(id) {
  const t = S.done.find((x) => String(x.id) === String(id));
  if (!t) { location.hash = "#growth"; return; }
  const n = t.items.length, wrong = t.items.filter((x) => x.ch !== x.c);
  const pass = t.score >= (t.pass || 60);
  let filter = wrong.length ? "bad" : "all", page = 0;
  view.innerHTML = `<h1>${esc(attemptTitle(t))}</h1>
  <div class="card score"><div class="big ${pass ? "pass" : "fail"}">${fmtScore(t.score)}</div>
    <div><b>${pass ? "🎉 及格" : "還差一點，再加油！"}</b><div class="muted">答對 ${t.ok}／${n} 題　·　用時 ${fmtSec(t.secs)}　·　${fmtDate(t.end)}</div></div>
    <span class="sp"></span><a class="btn out" href="#growth">成長圖表</a><a class="btn" href="#quiz">再測一次</a></div>
  <div class="row" style="margin-bottom:10px"><b>看哪些題目：</b>
    <button class="btn sm" data-f="bad">答錯與未作答（${wrong.length}）</button><button class="btn sm out" data-f="all">全部（${n}）</button></div>
  <div id="qs"></div><div class="pager" id="pg"></div>`;
  const draw = () => {
    const list = t.items.map((x, i) => [x, i]).filter(([x]) => filter === "all" || x.ch !== x.c);
    const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
    page = Math.min(page, pages - 1);
    view.querySelectorAll("[data-f]").forEach((b) => b.classList.toggle("out", b.dataset.f !== filter));
    $("#qs").innerHTML = list.length ? list.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE)
      .map(([x, i]) => QM.has(x.q) ? qCard(QM.get(x.q), x.p, { no: i + 1, chosen: x.ch, correctPos: x.c, reveal: true }) : "").join("")
      : `<div class="empty">全部答對 👍</div>`;
    pager(page, pages, (p) => { page = p; draw(); window.scrollTo({ top: 0 }); });
  };
  view.querySelectorAll("[data-f]").forEach((b) => (b.onclick = () => { filter = b.dataset.f; page = 0; draw(); }));
  draw();
}
function pager(page, pages, go) {
  const pg = $("#pg"); if (!pg) return;
  if (pages <= 1) { pg.innerHTML = ""; return; }
  pg.innerHTML = `<button class="btn out" id="pv" ${page ? "" : "disabled"}>◀ 上一頁</button><span class="muted">第 ${page + 1}／${pages} 頁</span><button class="btn out" id="nx" ${page < pages - 1 ? "" : "disabled"}>下一頁 ▶</button>`;
  $("#pv").onclick = () => go(page - 1); $("#nx").onclick = () => go(page + 1);
}

/* ------------------------------------------------------------------ 畫面：單元複習 */
const RV = { unit: "01", kw: "", show: false, wrong: false, page: 0, perms: {} };
function vReview() {
  const cnt = {};
  for (const q of B.q) cnt[q.u] = (cnt[q.u] || 0) + 1;
  view.innerHTML = `<h1>單元複習（答案與解說）</h1>
  <div class="card row">
    <select id="ru"><option value="">全部單元（${B.q.length}）</option>${B.units.filter((u) => cnt[u.c]).map((u) => `<option value="${u.c}">${esc(u.n)}（${cnt[u.c]}）</option>`).join("")}</select>
    <input type="search" id="rk" placeholder="關鍵字，例如：鼻胃管" style="flex:1;min-width:160px">
    <label class="chk"><input type="checkbox" id="rs">直接顯示答案</label>
    <label class="chk"><input type="checkbox" id="rw">只看我的錯題</label></div>
  <div class="muted" id="rc" style="margin:-4px 0 10px"></div><div id="qs"></div><div class="pager" id="pg"></div>`;
  $("#ru").value = RV.unit; $("#rk").value = RV.kw; $("#rs").checked = RV.show; $("#rw").checked = RV.wrong;
  const draw = () => {
    const kw = RV.kw.trim();
    const wset = RV.wrong ? new Set(wrongIds()) : null;
    const list = B.q.filter((q) => (!RV.unit || q.u === RV.unit) && (!wset || wset.has(q.i))
      && (!kw || (q.s + q.o.join("") + q.e).includes(kw)));
    const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
    RV.page = Math.min(RV.page, pages - 1);
    $("#rc").textContent = `共 ${list.length} 題；選項順序每次隨機排列，先想答案再看解說。點選項可以直接作答。`;
    $("#qs").innerHTML = list.length ? list.slice(RV.page * PER_PAGE, RV.page * PER_PAGE + PER_PAGE).map((q, k) => {
      const p = RV.perms[q.i] || (RV.perms[q.i] = makePerm(q.p));
      return qCard(q, p, { no: RV.page * PER_PAGE + k + 1, correctPos: p.indexOf(String(q.a)) + 1, reveal: RV.show, practice: !RV.show });
    }).join("") : `<div class="empty">${RV.wrong ? "沒有錯題 👍" : "找不到符合的題目"}</div>`;
    pager(RV.page, pages, (p) => { RV.page = p; draw(); window.scrollTo({ top: 0 }); });
  };
  const reveal = (card, chosen) => {
    const q = QM.get(Number(card.dataset.qid)); const p = RV.perms[q.i];
    const no = Number(card.id.slice(1));
    const tmp = document.createElement("div");
    tmp.innerHTML = qCard(q, p, { no, chosen, correctPos: p.indexOf(String(q.a)) + 1, reveal: true });
    card.replaceWith(tmp.firstElementChild);
  };
  $("#qs").addEventListener("click", (e) => {
    const card = e.target.closest(".q"); if (!card) return;
    if (e.target.closest("[data-show]")) reveal(card, undefined);
    else { const o = e.target.closest(".opt"); if (o && !card.querySelector(".opts.locked")) reveal(card, Number(o.dataset.pos)); }
  });
  $("#ru").onchange = (e) => { RV.unit = e.target.value; RV.page = 0; draw(); };
  let kt = 0;
  $("#rk").oninput = (e) => { clearTimeout(kt); kt = setTimeout(() => { RV.kw = e.target.value; RV.page = 0; draw(); }, 250); };
  $("#rs").onchange = (e) => { RV.show = e.target.checked; draw(); };
  $("#rw").onchange = (e) => { RV.wrong = e.target.checked; RV.page = 0; draw(); };
  draw();
}

/* ------------------------------------------------------------------ 畫面：成長圖表 */
function growthData() {
  const done = S.done;
  const scores = done.map((t) => t.score);
  const recent = new Set(done.slice(-5).map((t) => t.id));
  const units = {};
  const per = new Map();
  for (const t of done) for (const x of t.items) {
    const q = QM.get(x.q); if (!q) continue;
    const u = units[q.u] || (units[q.u] = { n: 0, ok: 0, rn: 0, rok: 0 });
    const ok = x.ch === x.c;
    u.n++; if (ok) u.ok++;
    if (recent.has(t.id)) { u.rn++; if (ok) u.rok++; }
    const p = per.get(x.q) || { n: 0, bad: 0 }; p.n++; if (!ok) p.bad++; per.set(x.q, p);
  }
  return { count: done.length, scores, units, per, best: scores.length ? Math.max(...scores) : 0, last: scores[scores.length - 1] || 0,
    avg: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10 : 0 };
}
function chartSvg(vals, pass) {
  const W = 760, H = 250, L = 38, R = 18, T = 18, Bt = 30;
  const w = W - L - R, h = H - T - Bt;
  const x = (i) => L + (vals.length <= 1 ? w / 2 : i * w / (vals.length - 1));
  const y = (v) => T + h - v / 100 * h;
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="成績折線圖">`;
  for (let v = 0; v <= 100; v += 20) s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="#E2E8F0"/><text x="${L - 6}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="#6B7280">${v}</text>`;
  s += `<line x1="${L}" x2="${W - R}" y1="${y(pass)}" y2="${y(pass)}" stroke="#C2410C" stroke-dasharray="6 5"/><text x="${W - R}" y="${y(pass) - 5}" font-size="11" text-anchor="end" fill="#C2410C">及格 ${pass}</text>`;
  if (vals.length > 1) s += `<polyline fill="none" stroke="#0FA294" stroke-width="3" points="${vals.map((v, i) => x(i) + "," + y(v)).join(" ")}"/>`;
  const step = Math.ceil(vals.length / 12);
  vals.forEach((v, i) => {
    s += `<circle cx="${x(i)}" cy="${y(v)}" r="4.5" fill="${v >= pass ? "#0FA294" : "#C2410C"}"><title>第 ${i + 1} 次：${fmtScore(v)} 分</title></circle>`;
    if (i % step === 0 || i === vals.length - 1) s += `<text x="${x(i)}" y="${H - 10}" font-size="11" text-anchor="middle" fill="#6B7280">${i + 1}</text>`;
  });
  return s + `</svg>`;
}
function vGrowth() {
  const g = growthData();
  if (!g.count) {
    view.innerHTML = `<h1>成長圖表</h1><div class="card empty">還沒有交卷紀錄。<br><br><a class="btn" href="#quiz">開始第一次測驗</a></div>`;
    return;
  }
  const pass = Number(S.set.pass) || 60;
  const urows = B.units.filter((u) => g.units[u.c]).map((u) => {
    const d = g.units[u.c]; const r = d.ok * 100 / d.n; const rr = d.rn ? d.rok * 100 / d.rn : null;
    return `<tr><td>${esc(u.n)}</td><td class="n">${d.n}</td><td style="width:40%"><div class="meter"><i style="width:${r}%;background:${r >= pass ? "#0FA294" : "#E07A4F"}"></i></div></td><td class="n">${fmtScore(r)}%</td><td class="n">${rr === null ? "—" : fmtScore(rr) + "%"}</td></tr>`;
  }).join("");
  const hard = [...g.per].filter(([, p]) => p.bad).sort((a, b) => b[1].bad - a[1].bad || b[1].bad / b[1].n - a[1].bad / a[1].n).slice(0, 20);
  view.innerHTML = `<h1>成長圖表</h1>
  <div class="tiles"><div class="tile"><b>${g.count}</b><span>測驗次數</span></div><div class="tile"><b>${fmtScore(g.scores[0])}</b><span>第一次</span></div>
    <div class="tile"><b>${fmtScore(g.last)}</b><span>最近一次</span></div><div class="tile"><b>${fmtScore(g.best)}</b><span>最佳</span></div>
    <div class="tile"><b>${fmtScore(g.avg)}</b><span>平均</span></div><div class="tile"><b>${wrongIds().length}</b><span>待複習錯題</span></div></div>
  <div class="card"><b>每次分數</b>${chartSvg(g.scores, pass)}</div>
  <h2>各單元答對率</h2><div class="card tbl"><table><tr><th>單元</th><th class="n">作答題數</th><th>答對率</th><th class="n">全部</th><th class="n">最近 5 次</th></tr>${urows}</table></div>
  <h2>最常答錯的題目</h2><div class="card tbl">${hard.length ? `<table><tr><th>題目</th><th>單元</th><th class="n">答錯／作答</th><th></th></tr>${hard.map(([qid, p]) => { const q = QM.get(qid); return `<tr><td>${esc(plain(q.s))}</td><td>${esc(unitName(q.u))}</td><td class="n">${p.bad}／${p.n}</td><td><button class="btn sm out" data-q="${qid}">解說</button></td></tr>`; }).join("")}</table>` : `<div class="empty">沒有答錯的題目 👍</div>`}</div>
  <h2>測驗紀錄</h2><div class="card tbl"><table><tr><th>時間</th><th>測驗</th><th class="n">題數</th><th class="n">分數</th><th class="n">用時</th><th></th></tr>
  ${S.done.slice().reverse().map((t) => `<tr><td>${fmtDate(t.end)}</td><td>${esc(attemptTitle(t))}</td><td class="n">${t.items.length}</td><td class="n" style="color:${t.score >= (t.pass || 60) ? "var(--ok)" : "var(--bad)"};font-weight:700">${fmtScore(t.score)}</td><td class="n">${fmtSec(t.secs)}</td><td><a class="btn sm out" href="#result/${t.id}">看詳解</a></td></tr>`).join("")}</table></div>`;
  view.querySelectorAll("[data-q]").forEach((b) => (b.onclick = () => showQ(Number(b.dataset.q))));
}
function showQ(qid) {
  const q = QM.get(qid); const p = makePerm(q.p);
  dialog(qCard(q, p, { no: "", correctPos: p.indexOf(String(q.a)) + 1, reveal: true }));
}

/* ------------------------------------------------------------------ 畫面：題庫統計 */
function vStats() {
  const cnt = {}, cntAll = {};
  for (const q of B.q) { cntAll[q.u] = (cntAll[q.u] || 0) + 1; }
  for (const q of poolAll()) cnt[q.u] = (cnt[q.u] || 0) + 1;
  const total = B.q.length;
  const newBy = {};
  for (const q of B.q) if (q.r === "EXAM" && q.f) newBy[q.f] = (newBy[q.f] || 0) + 1;
  const grp = { CARE: "工作項目", COMMON: "共同科目", OTHER: "其他" };
  view.innerHTML = `<h1>題庫統計</h1>
  <div class="tiles"><div class="tile"><b>${total}</b><span>總題庫數（可出題）</span></div>
    <div class="tile"><b>${B.q.filter((q) => q.e).length}</b><span>附 AI 解說</span></div>
    <div class="tile"><b>${B.q.filter((q) => q.x).length}</b><span>歷屆考過的題目</span></div>
    <div class="tile"><b>${B.sources.filter((s) => s.k === "EXAM").length}</b><span>年度學科測試試題</span></div></div>
  <h2>各單元題庫數</h2><div class="card tbl"><table><tr><th>類別</th><th>單元</th><th class="n">題數</th><th style="width:35%"></th><th class="n">出題用${S.set.includeOld ? "" : "（不含舊題）"}</th></tr>
  ${B.units.filter((u) => cntAll[u.c]).map((u) => `<tr><td>${grp[u.g] || ""}</td><td>${esc(u.n)}</td><td class="n">${cntAll[u.c]}</td><td><div class="meter"><i style="width:${cntAll[u.c] * 100 / Math.max(...Object.values(cntAll))}%"></i></div></td><td class="n">${cnt[u.c] || 0}</td></tr>`).join("")}
  <tr><th></th><th>合計</th><th class="n">${total}</th><th></th><th class="n">${poolAll().length}</th></tr></table></div>
  <h2>題目來源</h2><div class="card tbl"><table><tr><th>種類</th><th>年度</th><th>名稱</th><th class="n">題數</th><th class="n">題庫外的新題</th></tr>
  ${B.sources.map((s) => `<tr><td>${KIND[s.k] || s.k}</td><td>${s.y || ""}</td><td>${esc(s.t)}</td><td class="n">${s.c}</td><td class="n">${s.k === "EXAM" ? (newBy[s.y] || 0) : ""}</td></tr>`).join("")}</table></div>
  <p class="muted">「題庫外的新題」是該年度考卷裡、題庫沒有的題目（第一次出現在那一年），已依內容自動分到最接近的單元。</p>`;
}

/* ------------------------------------------------------------------ 畫面：語音教學 */
const GO = { web_intro: ["#home", "#quiz", "#review", "#growth"], web_quiz: ["#quiz", "#quiz", "#quiz", "#quiz"],
  web_review: ["#review", "#review", "#review", "#review"], web_growth: ["#growth", "#growth", "#growth", "#settings"] };
let lessonKey = "web_intro";
function vLearn() {
  const ls = B.lessons;
  const cur = ls.find((l) => l.k === lessonKey) || ls[0];
  view.innerHTML = `<h1>語音動態教學</h1><div class="lesson">
    <div class="card lessons">${ls.map((l, i) => `<button data-k="${l.k}" class="${l.k === cur.k ? "on" : ""}">${i + 1}. ${esc(l.t)}</button>`).join("")}</div>
    <div class="card"><h3 style="margin:0 0 6px">${esc(cur.t)}</h3>
      <audio id="au" controls preload="metadata" src="../voice/${cur.k}.mp3"></audio>
      <div class="steps">${cur.st.map((s, i) => `<div class="st" data-i="${i}"><span class="n">${i + 1}</span><span>${esc(s)}</span><a class="btn sm out" href="${(GO[cur.k] || [])[i] || "#home"}">跟著做</a></div>`).join("")}</div>
      <div class="vt">${esc(cur.v)}</div></div></div>`;
  view.querySelectorAll("[data-k]").forEach((b) => (b.onclick = () => { lessonKey = b.dataset.k; vLearn(); $("#au").play().catch(() => {}); }));
  const au = $("#au"); const sts = [...view.querySelectorAll(".st")];
  au.ontimeupdate = () => {
    if (!au.duration) return;
    const i = Math.min(sts.length - 1, Math.floor(au.currentTime / au.duration * sts.length));
    sts.forEach((s, k) => s.classList.toggle("on", k === i && !au.paused));
  };
  au.onpause = au.onended = () => sts.forEach((s) => s.classList.remove("on"));
}

/* ------------------------------------------------------------------ 畫面：設定 */
function vSettings() {
  const st = S.set;
  const vs = TTS.list();
  view.innerHTML = `<h1>設定</h1>
  <div class="card"><b>測驗</b>
    <div class="grid" style="margin-top:10px">
      <label>每次題數（10～200）<br><input type="number" id="sz" min="10" max="200" value="${st.size}"></label>
      <label>及格分數<br><input type="number" id="ps" min="0" max="100" value="${st.pass}"></label>
      <label>測驗時間（分鐘，0＝不限）<br><input type="number" id="tl" min="0" max="300" value="${st.time}"></label></div>
    <div class="row" style="margin-top:10px;gap:18px">
      <label class="chk"><input type="checkbox" id="io" ${st.includeOld ? "checked" : ""}>出題包含舊版題庫與歷屆才有的題目</label>
      <label class="chk"><input type="checkbox" id="sh" ${st.shuffle ? "checked" : ""}>選項隨機換位置（建議開啟）</label></div>
    <div class="row" style="margin-top:12px"><button class="btn" id="sv">儲存</button><button class="btn out" id="df">恢復預設</button></div></div>
  <div class="card"><b>朗讀語音</b>
    <p class="muted" style="margin:4px 0 8px">用這台裝置瀏覽器內建的語音。用 Microsoft Edge 開啟會有「曉臻（自然）」等微軟自然語音，最不像機器人；iPhone／iPad 可在「設定 → 輔助使用 → 朗讀內容 → 聲音」下載「美佳（增強版）」。</p>
    ${TTS.ok ? `<div class="row"><select id="vc" style="max-width:100%">${vs.length ? vs.map((v) => `<option value="${esc(v.name)}" ${v.name === (TTS.pick() || {}).name ? "selected" : ""}>${esc(v.name)}${/Natural|Online|Neural/i.test(v.name) ? "（自然）" : ""}</option>`).join("") : `<option>找不到中文語音</option>`}</select>
      <label>速度 <select id="rt">${[0.8, 0.9, 1, 1.1, 1.2, 1.35].map((r) => `<option value="${r}" ${Number(st.rate) === r ? "selected" : ""}>${r}×</option>`).join("")}</select></label>
      <button class="say" id="vt" style="margin-left:0">🔊 朗讀</button></div>` : `<p class="muted">這個瀏覽器不支援朗讀。</p>`}</div>
  <div class="card"><b>成績紀錄</b>
    <p class="muted" style="margin:4px 0 8px">紀錄存在這台裝置的瀏覽器（目前 ${S.done.length} 次測驗）。清除瀏覽器資料會不見，建議偶爾備份。</p>
    <div class="row"><button class="btn out" id="bk">⬇ 備份紀錄</button><label class="btn out">⬆ 還原紀錄<input type="file" id="rs" accept=".json,application/json" hidden></label>
      <button class="btn red" id="clr">清除全部紀錄</button></div></div>
  <div class="card"><b>關於</b><p class="muted" style="margin:4px 0 0">線上版 v${esc(B.v)}，內建 ${B.q.length} 題。電腦版（Windows／macOS）可以匯入新年度的學科測驗 PDF、建立多位學員帳號與權限：<a href="https://github.com/achir1015/zms-care-quiz/releases/latest" target="_blank" rel="noopener">下載電腦版</a>。</p></div>`;
  $("#sv").onclick = () => {
    st.size = Math.max(10, Math.min(200, Number($("#sz").value) || 100));
    st.pass = Math.max(0, Math.min(100, Number($("#ps").value) || 60));
    st.time = Math.max(0, Math.min(300, Number($("#tl").value) || 0));
    st.includeOld = $("#io").checked; st.shuffle = $("#sh").checked;
    save(); toast("已儲存"); vSettings();
  };
  $("#df").onclick = () => { S.set = Object.assign({}, DEF, { voice: st.voice, rate: st.rate }); save(); toast("已恢復預設"); vSettings(); };
  if ($("#vc")) {
    $("#vc").onchange = (e) => { st.voice = e.target.value; save(); };
    $("#rt").onchange = (e) => { st.rate = Number(e.target.value); save(); };
    $("#vt").onclick = (e) => TTS.speak("你好，我是學科測驗的朗讀語音。照顧服務員協助案主翻身時，應先向案主說明。", e.currentTarget);
  }
  $("#bk").onclick = () => {
    const blob = new Blob([JSON.stringify({ format: "zms-care-quiz-web/1", at: new Date().toISOString(), data: S })], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    const d = new Date(); a.download = `學科測驗紀錄-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}.json`;
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  $("#rs").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const j = JSON.parse(await f.text());
      if (j.format !== "zms-care-quiz-web/1" || !j.data || !Array.isArray(j.data.done)) throw new Error();
      if (!(await ask(`備份檔有 ${j.data.done.length} 次測驗紀錄，還原後會取代這台裝置目前的紀錄（${S.done.length} 次），確定嗎？`, "還原"))) return;
      S = { set: Object.assign({}, DEF, j.data.set || {}), done: j.data.done, open: j.data.open || null }; save();
      toast("已還原 " + S.done.length + " 次測驗紀錄"); vSettings();
    } catch (err) { toast("這不是學科測驗線上版的備份檔"); }
  };
  $("#clr").onclick = async () => {
    if (!(await ask("清除這台裝置上全部的測驗紀錄與錯題？清除後無法復原（建議先備份）。", "清除"))) return;
    S.done = []; S.open = null; save(); toast("已清除"); vSettings();
  };
}

/* ------------------------------------------------------------------ 路由 */
function fitTop() { document.documentElement.style.setProperty("--top", $(".top").offsetHeight + "px"); }
window.addEventListener("resize", fitTop);
function route() {
  fitTop();
  TTS.stop();
  if (location.hash !== "#run") stopTimer();
  const h = location.hash || "#home";
  const [name, arg] = h.slice(1).split("/");
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.getAttribute("href") === "#" + (name === "run" || name === "result" ? "quiz" : name)));
  $("#nav").classList.remove("open");
  const fn = { home: vHome, quiz: vQuiz, run: vRun, result: () => vResult(arg), review: vReview, growth: vGrowth, stats: vStats, learn: vLearn, settings: vSettings }[name] || vHome;
  fn();
  if (name !== "run") window.scrollTo({ top: 0 });
}
view.addEventListener("click", (e) => {          // 朗讀按鈕（題目、答案、解說）
  const b = e.target.closest("[data-say]"); if (b) speakQ(Number(b.dataset.say), b);
});
$("#menuBtn").onclick = () => $("#nav").classList.toggle("open");
$("#ver").textContent = "v" + B.v;
window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", () => { if (S.open) save(); });
route();
if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("../sw.js").catch(() => {});
