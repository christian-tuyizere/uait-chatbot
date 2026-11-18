const I18N = {
  en: {
    title: "UAIT AI", tagline: "Online", basicShort: "Basic mode", newChat: "New chat", close: "Close", ask: "Your question",
    h1: "How can I help you today?",
    intro: "Ask about programmes, admissions, fees and student life. I answer from UAIT's official information, and I can't submit applications or grant admission.",
    placeholder: "Ask about UAIT…", disclaimer: "Information only. Never pay before official admission confirmation.",
    sources: "Sources", copy: "Copy", copied: "Copied",
    hello: "Hello! I'm the UAIT Official AI Assistant. Ask me about programmes, admissions, fees, documents or student life, in English or Korean.",
    error: "Sorry, I couldn't reach the assistant just now. Please try again in a moment. For urgent help, email admission@uait.ac.rw or call +250 788 23 7349.",
    smart: "Smart answers on", basic: "Basic answer: AI is busy, try again in a minute",
    cards: [["Programmes", "What's open for 2027/2028?", "What programs are open for the 2027 intake?"],
            ["How to apply", "Steps and documents", "How do I apply to UAIT?"],
            ["Fees", "Tuition and payment rules", "How much does AI Technology cost?"],
            ["Eligibility", "Does my background fit?", "I studied Biology. Can I study AI Technology at UAIT?"]]
  },
  ko: {
    title: "UAIT AI", tagline: "온라인", basicShort: "기본 모드", newChat: "새 대화", close: "닫기", ask: "질문 입력",
    h1: "무엇을 도와드릴까요?",
    intro: "과정, 입학, 학비, 학교생활에 대해 물어보세요. UAIT 공식 정보를 바탕으로 답하며, 지원서 제출이나 입학 승인은 할 수 없습니다.",
    placeholder: "UAIT에 대해 물어보세요…", disclaimer: "정보 안내 전용입니다. 공식 입학 확정 전에는 절대 납부하지 마세요.",
    sources: "출처", copy: "복사", copied: "복사됨",
    hello: "안녕하세요! 저는 UAIT 공식 AI 어시스턴트입니다. 과정, 입학, 학비, 서류, 학교생활에 대해 영어 또는 한국어로 물어보세요.",
    error: "죄송합니다. 지금은 어시스턴트에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요. 급한 문의는 admission@uait.ac.rw 또는 +250 788 23 7349로 연락해 주세요.",
    smart: "스마트 답변 켜짐", basic: "기본 답변: AI가 바쁩니다. 잠시 후 다시 시도해 주세요",
    cards: [["과정", "2027/2028 모집 과정은?", "2027학년도에 모집 중인 과정은 무엇인가요?"],
            ["지원 방법", "절차와 서류", "UAIT에 어떻게 지원하나요?"],
            ["학비", "수업료와 납부 규칙", "AI Technology 학비는 얼마인가요?"],
            ["지원 자격", "내 전공으로 가능할까요?", "저는 생물학을 전공했어요. UAIT의 AI Technology를 공부할 수 있나요?"]]
  }
};
const $ = id => document.getElementById(id);
const chat = $("chat"), messages = $("messages"), form = $("form"), input = $("input"), send = $("send"),
      chips = $("chips"), cards = $("cards"), welcome = $("welcome"), statusEl = $("status"), dotEl = $("dot");
let lang = localStorage.getItem("uait_lang") || ((navigator.language || "").startsWith("ko") ? "ko" : "en");
if (!I18N[lang]) lang = "en";
let history = [], busy = false, smart = null;

const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const toBottom = () => { chat.scrollTop = chat.scrollHeight; };

/* ---- safe rich text: **bold**, bullets, numbered lists, links, emails ---- */
function inline(text, parent) {
  const re = /(\*\*[^*]+\*\*)|(https?:\/\/[^\s)]+)|([\w.+-]+@[\w-]+\.[\w.-]*\w)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    if (m[1]) parent.append(el("strong", null, m[1].slice(2, -2)));
    else if (m[2]) { const url = m[2].replace(/[.,;:!?]+$/, ""); const a = el("a", null, url); a.href = url; a.target = "_blank"; a.rel = "noreferrer"; parent.append(a); if (url.length < m[2].length) parent.append(m[2].slice(url.length)); }
    else { const a = el("a", null, m[3]); a.href = "mailto:" + m[3]; parent.append(a); }
    last = re.lastIndex;
  }
  if (last < text.length) parent.append(text.slice(last));
}
function rich(text) {
  const box = document.createDocumentFragment(); let list = null, kind = null;
  const close = () => { list = kind = null; };
  text.split("\n").forEach(line => {
    const b = line.match(/^\s*[•\-*]\s+(.*)/), n = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (b || n) {
      const k = b ? "ul" : "ol";
      if (kind !== k) { list = el(k); box.append(list); kind = k; }
      const li = el("li"); inline((b || n)[1], li); list.append(li);
    } else if (!line.trim()) close();
    else { close(); const p = el("p"); inline(line, p); box.append(p); }
  });
  return box;
}

function addUser(text) {
  const row = el("div", "row user"); row.append(el("div", "bubble", text)); messages.append(row); toBottom();
}
function addBot(text, sources = []) {
  const t = I18N[lang], row = el("div", "row bot"), bubble = el("div", "bubble");
  row.append(el("div", "avatar", "U"), bubble); bubble.append(rich(text));
  const meta = el("div", "meta");
  const seen = new Set();
  sources.forEach(s => { if (seen.has(s.title)) return; seen.add(s.title);
    const pill = s.url ? el("a", "pill", s.title) : el("span", "pill", s.title); if (s.url) { pill.href = s.url; pill.target = "_blank"; pill.rel = "noreferrer"; } meta.append(pill); });
  const copy = el("button", "copy", t.copy); copy.type = "button";
  copy.onclick = async () => { try { await navigator.clipboard.writeText(text); copy.textContent = t.copied; setTimeout(() => copy.textContent = t.copy, 1500); } catch (e) {} };
  meta.append(copy); bubble.append(meta);
  messages.append(row); toBottom();
}
function typing() {
  const row = el("div", "row bot"), b = el("div", "bubble"), d = el("span", "typing");
  d.append(el("i"), el("i"), el("i")); b.append(d); row.append(el("div", "avatar", "U"), b); messages.append(row); toBottom(); return row;
}
function setChips(list) {
  chips.replaceChildren();
  (list || []).forEach(q => { const c = el("button", "chip", q); c.type = "button"; c.onclick = () => ask(q); chips.append(c); });
}

async function ask(text) {
  text = (text || "").trim(); if (!text || busy) return;
  busy = true; send.disabled = true; welcome.hidden = true; setChips([]);
  addUser(text); history.push({ role: "user", content: text });
  input.value = ""; autosize(); const wait = typing();
  try {
    const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: history.slice(-9, -1), lang }) });
    const data = await res.json(); if (!res.ok) throw new Error(data.detail || "error");
    wait.remove(); addBot(String(data.answer), data.sources || []); history.push({ role: "assistant", content: data.answer });
    setChips(data.suggestions);
    smart = data.mode !== "knowledge-only"; applyLang();
  } catch (e) { wait.remove(); addBot(I18N[lang].error); }
  busy = false; send.disabled = false; input.focus(); toBottom();
}
function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 130) + "px"; }

const ICONS = [
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 9 12 4 2 9l10 5 10-5z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 14l2 2 4-4"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M16 15h2"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="4"/><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6M16 11l2 2 4-4"/></svg>'
];
const GO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';

function applyLang() {
  const t = I18N[lang]; document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(n => n.textContent = t[n.dataset.i18n]);
  document.querySelectorAll(".seg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  input.placeholder = t.placeholder;
  cards.replaceChildren();
  t.cards.forEach(([title, sub, q], i) => {
    const c = el("button", "card"); c.type = "button";
    const ico = el("span", "card-ico"); ico.innerHTML = ICONS[i % ICONS.length];
    const txt = el("span", "card-txt"); txt.append(el("b", null, title), el("span", null, sub));
    const go = el("span", "card-go"); go.innerHTML = GO;
    c.append(ico, txt, go); c.onclick = () => ask(q); cards.append(c);
  });
  statusEl.textContent = smart === false ? t.basicShort : t.tagline;
  dotEl.dataset.state = smart === false ? "basic" : "ok";
  $("newChat").title = t.newChat; $("closeBtn").title = t.close;
}
function reset() { history = []; messages.replaceChildren(); welcome.hidden = false; setChips([]); chat.scrollTop = 0; }

document.querySelectorAll(".seg button").forEach(b => b.onclick = () => { lang = b.dataset.lang; localStorage.setItem("uait_lang", lang); applyLang(); });
$("newChat").onclick = () => { reset(); input.focus(); };
form.onsubmit = e => { e.preventDefault(); ask(input.value); };
input.oninput = autosize;
input.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } };

if (window.parent !== window) { $("closeBtn").hidden = false; $("closeBtn").onclick = () => parent.postMessage({ uaitClose: true }, "*"); }
applyLang();
fetch("/api/status").then(r => r.json()).then(s => { smart = !!s.smart; applyLang(); }).catch(() => {});
