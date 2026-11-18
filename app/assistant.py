"""The reasoning pipeline: understand -> verified rules -> retrieve -> reason -> verify."""
import datetime as dt
import logging
import re
import threading
import time

from . import answers, guard
from .config import load_json, settings
from .crawler import crawl, detect_conflicts
from .lang import detect
from .llm import LLM, LLMError
from .prompts import build_system
from .retrieval import Index, tokenize
from .store import Store
from .understand import build_state

log = logging.getLogger("uait")

DOMAIN = re.compile(
    r"uait|\buniversity\b|\bschool\b|\binstitute\b|\bcollege\b|\bcampus\b|\badmission\w*|\bapply\w*|\bapplication\w*|\btuition\b|\bfees?\b|"
    r"\bprogram\w*|\bcourses?\b|\bcertificate\b|\bdiploma\b|\bstudy\w*|\bstudents?\b|\bscholarship\w*|\bintake\b|\bdeadline\b|\bdocuments?\b|"
    r"\brequirements?\b|\bkigali\b|\brwanda\w*|\bai\b|\bartificial intelligence\b|\bmachine learning\b|\bdata science\b|\bjewel\w+|\bpiano\b|"
    r"\bpay\w*|\bpaid\b|\bpenalty\b|\binstal+ments?\b|\brecommendation\b|\bletters?\b|\bportfolio\b|\btranscripts?\b|\bpassport\b|\bkorean\b|\bcommunity academy\b|\bcareers?\b|\bjobs?\b|\binternships?\b|\bgraduat\w*|\bskills?\b|\bcurriculum\b|\bcapstone\b|\blearn\w*|\bteach\w*|\bcalendar\b|\btrimesters?\b|\bsemesters?\b|\bterms?\b|\bnews\b|\bpartner\w*|\bfaculty\b|\bhousing\b|\blibrary\b|\bvice chancellor\b|\bmission\b|\bvision\b|\bmodules?\b|\boutcomes?\b|\balumni\b|\bemploy\w*|\bsalary\b|\bsafe\w*|\bfacilit\w*|\blaptops?\b|\bschedule\b|\btimetable\b|\bexams?\b|\bgrad\w*|\bvisa\b|\bfood\b|\btransport\w*|\bcertificat\w*|\bmentor\w*|\bindustry\b|\bcompan\w+|\bpractical\b|\bprojects?\b|\bclass(es)?\b|\blecture\w*|\bduration\b|\bhow long\b|\bage\b|\blanguage\b|\bonline\b|\bwhy (uait|choose)\b|"
    r"납부|분할|연체|추천서|포트폴리오|입학|지원|학비|수업료|등록금|과정|학과|전공|학생|졸업|장학금|마감|서류|르완다|키갈리|대학|학교|인공지능|주얼리|피아노|한국어|컴퓨터|취업|인턴|커리큘럼|진로|기술|공부|배우|가르|학사|일정|교수|총장|파트너|소식|뉴스|기숙사|도서관", re.I)

# Intents that must ALWAYS use the fixed, verified answer (safety, money movement, restricted contacts).
# Every other intent is now answered by the model, using the verified answer as its source material.
LOCKED = {"injection", "fabricate", "payment_done", "payment_method", "payment_timing", "job_guarantee", "hope"}
SMALLTALK = {"greeting", "thanks", "identity", "off_topic"}  # v5: the model answers these naturally when it is connected

# "Unconfirmed" topics that UAIT's website does answer, so a no-model answer may use the stored website records.
ANSWERABLE = {"faculty", "leadership", "partnership", "vision_mission", "news_events", "scholarship"}

DETAIL_ASK = re.compile(
    r"\b(detail\w*|in depth|in-depth|elaborate|explain|comprehensive|thorough\w*|step[- ]by[- ]step|full (list|explanation|answer|process)|"
    r"tell me more|more info\w*|everything|breakdown|brief\w*|summar\w+|overview|list (all|the|every)|all the)\b|"
    r"자세히|상세|구체적|설명해|전부|모두 알려|요약|간단히", re.I)
UNITS = re.compile(r"(?<=[.!?。])\s+(?=[A-Z0-9\"'(\uac00-\ud7a3])|\n+")


def wants_detail(message: str) -> bool:
    return bool(DETAIL_ASK.search(message or ""))


def limit_sentences(text: str, n: int = 3) -> str:
    """Keep the first n sentences/lines. Leaves already-short answers untouched."""
    parts = [p.strip() for p in UNITS.split(text.strip()) if p and p.strip()]
    if len(parts) <= n:
        return text.strip()
    return " ".join(p.lstrip("-*• ").strip() for p in parts[:n])


PAYMENT_HINT = re.compile(r"bank of kigali|mtn|mobile money|momo|ussd|account", re.I)


def _chunks(text, size=900, overlap=100):
    paras, out, cur = [p.strip() for p in text.split("\n") if p.strip()], [], ""
    for p in paras:
        if len(cur) + len(p) + 1 > size and cur:
            out.append(cur)
            tail = cur[-overlap:].split(" ", 1)[-1]
            cur = (tail + " " + p).strip()
        else:
            cur = (cur + "\n" + p).strip()
    if cur:
        out.append(cur)
    return out


class Assistant:
    def __init__(self, facts=None, seed=None, store=None, llm=None, cfg=None, crawl_cfg=None):
        self.facts = facts or load_json("facts.json")
        self.seed = (seed or load_json("knowledge_seed.json"))["records"]
        self.store = store or Store(settings.db_path)
        self.llm = llm if llm is not None else LLM(settings)
        self.crawl_cfg = crawl_cfg or load_json("crawl_config.json")
        self.lock = threading.Lock()
        self.last_llm_error = None
        self.compact = settings.llm_provider == "groq"  # Groq's free tier has a small tokens-per-minute budget: send a leaner prompt
        self.reload()

    # ---------- knowledge ----------
    def reload(self):
        docs = []
        for r in self.seed:
            for lang in ("en", "ko"):
                docs.append({"id": f"{r['id']}:{lang}", "rid": r["id"], "title": r["title"][lang], "text": r["content"][lang],
                             "keywords": r["keywords"], "source": "seed", "url": r.get("url"), "authority": r.get("authority", "owner"), "as_of": r["as_of"], "lang": lang})
        by_hash = {}
        for p in self.store.active_pages():  # the same content under two addresses is indexed once
            h = p["content_hash"]
            if h not in by_hash or len(p["url"]) < len(by_hash[h]["url"]):
                by_hash[h] = p
        pages = list(by_hash.values())
        for p in pages:
            for i, ch in enumerate(_chunks(p["text"])):
                docs.append({"id": f"web:{p['url']}#{i}", "title": p["title"], "text": ch, "keywords": [], "source": "web",
                             "url": p["url"], "as_of": time.strftime("%Y-%m-%d", time.localtime(p["last_fetched"])), "lang": "ko" if re.search(r"[\uac00-\ud7a3]", ch) else "en"})
        with self.lock:
            self.index, self.page_urls = Index(docs), [p["url"] for p in pages]

    def run_crawl(self):
        result = crawl(self.store, self.crawl_cfg)
        self.store.replace_conflicts(detect_conflicts(self.store.active_pages(), self.facts))
        self.store.log_crawl({k: (v if isinstance(v, int) else len(v)) for k, v in result.items()})
        self.reload()
        return result

    def status(self):
        lc = self.store.last_crawl()
        return {"pages": len(self.page_urls), "last_crawl": lc, "open_conflicts": len(self.store.conflicts()),
                "model_configured": self.llm.configured, "ai_busy": bool(self.last_llm_error), "last_llm_error": self.last_llm_error, "facts_as_of": self.facts["as_of"]}

    # ---------- main entry ----------
    def respond(self, message, history=None, ui_lang=None, today=None):
        today = today or dt.date.today()
        history = [h for h in (history or []) if isinstance(h, dict)][-12:]
        original = message
        st = build_state(message, history, ui_lang)
        fixed = self.index.fix_typos(message)  # "hw many yrs is the progam" -> "how many years is the program"
        if st.intent == "general" and fixed != message:  # only lean on the corrected text when the original was not understood
            st2 = build_state(fixed, history, ui_lang)
            if st2.intent != "general":
                st, message = st2, fixed
        st.detail = wants_detail(original)
        topics = self.store.conflict_topics()
        ctx = {"today": today, "message": message, "conflict_topics": topics, "detail": st.detail}
        intent = st.intent

        scope_check = False
        if intent == "general" and (self.llm.configured or not self._in_scope(message, st)):
            if self.llm.configured:
                scope_check = True  # the model decides: answer if education-related, polite redirect if not
            else:
                intent = "off_topic"

        rule_fallback, multi = None, []
        if self.llm.configured and intent in SMALLTALK:
            rule_fallback, intent, scope_check = intent, "general", True  # model replies; the canned line is only the fallback
        # Questions about things the verified file can't confirm: use website pages if they cover it.
        web_hits = []
        if intent == "unconfirmed":
            web_hits = [h for h in self.index.search(self._query(message, st), k=6)
                        if h["score"] >= 4.0 and h.get("rid") != "unconfirmed"]
            if not (self.llm.configured or st.topic in ANSWERABLE):
                web_hits = []  # without a model keep the cautious "can't confirm" answer, except for topics the website covers
            if web_hits:
                rule_fallback, intent = "unconfirmed", "rag"

        if self.llm.configured and intent in ("fees", "apply", "documents", "deadline", "contact", "open_programs", "join", "programme_status", "compare", "authorization"):
            from .understand import P
            multi = [n for n in ("fees", "deadline", "apply", "documents", "contact", "open_programs") if P[n].search(message)]
            if len(multi) >= 2 and len(message.split()) > 6:
                rule_fallback, intent = intent, "rag"  # several questions at once: let the model write one coherent answer from verified facts

        if intent in ("payment_method", "payment_timing"):
            ctx["payment_excerpt"] = self._payment_excerpt()

        draft = draft_brief = None
        if intent not in ("rag", "general", "assessment") or (intent == "assessment" and not self.llm.configured):
            fixed = answers.render(intent, st, self.facts, ctx)  # brief unless the visitor asked for detail
            if fixed:
                if self.llm.configured and intent not in LOCKED:
                    draft = answers.render_full(intent, st, self.facts, ctx) or fixed  # model reasons over the full verified text
                    draft_brief = fixed
                else:
                    return self._pack(fixed, st, "verified-rule", intent)

        found = [r for r in self.index.search(self._query(message, st), k=10) if r.get("lang", st.lang) in (st.lang, "en") or r["source"] == "web"]
        best = {}
        for r in found:  # one copy of each knowledge record, preferring the visitor's language
            if r["source"] == "seed":
                k = r["rid"]
                if k not in best or (r.get("lang") == st.lang and best[k].get("lang") != st.lang):
                    best[k] = dict(r, score=max(r["score"], best[k]["score"]) if k in best else r["score"])
        if st.programme in ("ai", "jewelry"):  # keep answers on the programme the visitor is asking about
            own, other = st.programme, ("jewelry" if st.programme == "ai" else "ai")
            for k, r in best.items():
                tag = lambda t: bool(re.search(rf"(^|-){t}(-|$)", k))
                if tag(own):
                    r["score"] *= 1.35
                elif tag(other):
                    r["score"] *= 0.35
        seeds = sorted(best.values(), key=lambda r: -r["score"])[:(4 if self.compact else 6) if self.llm.configured else 3]  # verified records always get a seat
        webs = [r for r in found if r["source"] == "web"][:(2 if self.compact else 4) if self.llm.configured else 2]
        retrieved = sorted(seeds + webs, key=lambda r: -r["score"])
        if not retrieved and not draft and intent != "assessment" and not st.assessing and not self.llm.configured:
            fixed = answers.render("unconfirmed", st, self.facts, ctx)
            return self._pack(fixed, st, "unconfirmed", "unconfirmed")

        if self.llm.configured:
            out = self._ask_llm(original, history, st, intent, retrieved, topics, today, draft=draft, scope_check=scope_check)
            if out:
                return self._pack(out, st, "model", intent)
            if draft:  # model unavailable or blocked by the guard: the brief verified answer is still correct
                return self._pack(draft_brief, st, "verified-rule", intent)
            if rule_fallback in SMALLTALK:
                return self._pack(answers.render(rule_fallback, st, self.facts, ctx), st, "verified-rule", rule_fallback)
            if scope_check and not retrieved:
                return self._pack(answers.render("off_topic", st, self.facts, ctx), st, "verified-rule", "off_topic")
            if rule_fallback:  # the model is unavailable: fall back to the verified rule answer(s)
                fixed = self._combined_rules(multi, st, ctx) if len(multi) >= 2 else answers.render(rule_fallback, st, self.facts, ctx)
                if fixed:
                    return self._pack(fixed, st, "verified-rule", rule_fallback)
        if intent == "assessment":
            return self._pack(answers.render("assessment", st, self.facts, ctx), st, "verified-rule", intent)
        if not retrieved:
            return self._pack(answers.render("unconfirmed", st, self.facts, ctx), st, "unconfirmed", "unconfirmed")
        return self._pack(self._knowledge_only(st, retrieved, message), st, "knowledge-only", intent)

    # ---------- helpers ----------
    def _combined_rules(self, intents, st, ctx):
        parts, srcs = [], []
        brief_ctx = dict(ctx, detail=False)
        for n in intents[:3]:
            r = answers.render(n, st, self.facts, brief_ctx)
            if r:
                first = [x for x in UNITS.split(r["answer"].strip()) if x.strip()][0]
                parts.append(first.strip())
                srcs += r["sources"]
        if not parts:
            return None
        return {"answer": " ".join(parts), "sources": srcs}

    def _in_scope(self, message, st):
        if DOMAIN.search(message) or DOMAIN.search(self.index.fix_typos(message)):
            return True
        if st.assessing or st.programme:
            return len(message.split()) <= 8  # short follow-ups continue the UAIT conversation
        return bool(st.subjects)

    def _query(self, message, st):
        q = message
        if len(message.split()) <= 6 and st.last_user_message:
            q += " " + st.last_user_message
        if st.programme:
            q += {"ai": " AI Technology", "jewelry": " Jewelry Design"}[st.programme]
        return q

    def _payment_excerpt(self):
        hits = [h for h in self.index.search("payment bank of kigali mtn mobile money ussd fees payments", k=6, source="web")
                if PAYMENT_HINT.search(h["text"])]
        if not hits:
            return None
        h = hits[0]
        return {"text": h["text"][:900], "url": h["url"], "date": h["as_of"]}

    SUGGEST = {
        "greeting": [("What programmes are open?", "어떤 과정이 열려 있나요?"), ("How do I apply?", "어떻게 지원하나요?"), ("How much is tuition?", "학비가 얼마예요?")],
        "join": [("What programmes are open?", "어떤 과정이 열려 있나요?"), ("What documents do I need?", "어떤 서류가 필요한가요?"), ("I studied Biology, can I join AI?", "저는 생물학을 전공했는데 AI 과정에 지원할 수 있나요?")],
        "open_programs": [("How do I apply?", "어떻게 지원하나요?"), ("What documents do I need?", "어떤 서류가 필요한가요?"), ("How much is tuition?", "학비가 얼마예요?")],
        "programme_status": [("How do I apply?", "어떻게 지원하나요?"), ("How much is tuition?", "학비가 얼마예요?"), ("What documents do I need?", "어떤 서류가 필요한가요?")],
        "compare": [("How do I apply?", "어떻게 지원하나요?"), ("What documents do I need?", "어떤 서류가 필요한가요?")],
        "fees": [("When do I pay?", "언제 납부하나요?"), ("How do I apply?", "어떻게 지원하나요?"), ("What is the deadline?", "마감일이 언제예요?")],
        "apply": [("What documents do I need?", "어떤 서류가 필요한가요?"), ("What is the deadline?", "마감일이 언제예요?"), ("How can I contact admissions?", "입학처에 어떻게 연락하나요?")],
        "documents": [("How do I apply?", "어떻게 지원하나요?"), ("What is the deadline?", "마감일이 언제예요?")],
        "deadline": [("How do I apply?", "어떻게 지원하나요?"), ("What documents do I need?", "어떤 서류가 필요한가요?")],
        "assessment": [("What documents do I need?", "어떤 서류가 필요한가요?"), ("How do I apply?", "어떻게 지원하나요?"), ("How can I contact admissions?", "입학처에 어떻게 연락하나요?")],
        "payment_method": [("How can I contact admissions?", "입학처에 어떻게 연락하나요?"), ("How much is tuition?", "학비가 얼마예요?")],
        "payment_timing": [("How much is tuition?", "학비가 얼마예요?"), ("How can I contact admissions?", "입학처에 어떻게 연락하나요?")],
        "contact": [("What programmes are open?", "어떤 과정이 열려 있나요?"), ("How do I apply?", "어떻게 지원하나요?")],
        "off_topic": [("What programmes are open?", "어떤 과정이 열려 있나요?"), ("How do I apply?", "어떻게 지원하나요?")],
    }

    def _pack(self, res, st, mode, intent):
        out = []
        for s in res.get("sources", []):
            t = s["title"] if isinstance(s["title"], str) else s["title"][st.lang]
            out.append({"title": t, "url": s.get("url"), "as_of": s.get("as_of")})
        sug = [ko if st.lang == "ko" else en for en, ko in self.SUGGEST.get(intent, self.SUGGEST["open_programs"] if intent in ("general", "rag", "unconfirmed", "coming_soon", "community") else [])]
        answer = res["answer"] if (st.detail or mode == "model") else limit_sentences(res["answer"], 3)  # v5: only canned/fallback answers are capped; model answers are written to fit the question
        return {"answer": answer, "sources": out, "mode": mode, "lang": st.lang, "intent": intent, "suggestions": sug[:3]}

    def _knowledge_only(self, st, retrieved, query=""):
        ref = answers.ref_short(st.lang, self.facts)
        seeds_ = [r for r in retrieved if r["source"] == "seed"]
        seed = ([r for r in seeds_ if r.get("lang") == st.lang] or seeds_)[:1]
        if not seed:
            msg = answers.L(st.lang, "I can't confirm that from the information I have. ", "제가 가진 정보로는 확인하기 어렵습니다. ")
            return {"answer": msg + ref, "sources": []}
        r = seed[0]
        text = r["text"]
        if st.detail and len(text) > 650:
            cut = text[:650]
            text = cut[:max(cut.rfind(". "), cut.rfind("다. "), 300) + 1].strip()
        if not st.detail:  # keep the stored-text fallback to the two sentences that best match the question
            text = self._pick_sentences(text, query)
        return {"answer": f"{text} {ref}" if not st.detail else f"{text}\n\n{answers.refer(st.lang, self.facts)}", "sources": [{"title": r["title"], "url": r.get("url"), "as_of": r.get("as_of")}]}

    CAREER_Q = re.compile(r"career|job|intern|employ|graduat|work|salary|hire|취업|진로|인턴|급여|졸업", re.I)

    @staticmethod
    def _trim(sentence, limit=260):
        if len(sentence) <= limit:
            return sentence
        cut = sentence[:limit]
        pos = max(cut.rfind("; "), cut.rfind(", "), cut.rfind(" "))
        return cut[:pos if pos > 80 else limit].rstrip(" ;,:") + "."

    def _pick_sentences(self, text, query, n=2):
        """Fallback when no model is available: the n stored sentences that best match the question.
        A 'does not guarantee' sentence always stays in for career questions."""
        sents = [x.strip() for x in UNITS.split(text) if x.strip()]
        q = set(tokenize(query or ""))
        order = sorted(range(len(sents)), key=lambda i: (-len(q & set(tokenize(sents[i]))), i))
        if self.CAREER_Q.search(query or ""):
            keep = [i for i, x in enumerate(sents) if re.search(r"guarantee", x, re.I)][:1]
            order = keep + [i for i in order if i not in keep]
        chosen = [sents[i] for i in sorted(order[:n])]
        budget = 600  # total characters for the fallback; the longest sentence is trimmed first
        while sum(len(x) for x in chosen) + len(chosen) > budget:
            k = max(range(len(chosen)), key=lambda j: len(chosen[j]))
            room = max(budget - (sum(len(x) for j, x in enumerate(chosen) if j != k) + len(chosen)), 160)
            trimmed = self._trim(chosen[k], room)
            if trimmed == chosen[k]:
                break
            chosen[k] = trimmed
        return " ".join(chosen)

    CORE_INTENTS = ("open_programs", "deadline", "fees", "apply", "documents", "authorization", "coming_soon", "community", "compare", "contact")

    def _core_block(self, st, today, topics):
        """Complete owner-verified knowledge on the main admissions topics. The model always sees all of it,
        so it can answer correctly even when the keyword matcher misread the question."""
        ctx = {"today": today, "message": "", "conflict_topics": topics, "detail": True}
        parts = []
        for name in self.CORE_INTENTS:
            r = answers.render_full(name, st, self.facts, ctx)
            if r:
                parts.append(f"## {name.replace('_', ' ')}\n{r['answer'].strip()}")
        return "\n\n".join(parts)

    def _facts_block(self, lang):
        f, a, c = self.facts, self.facts["admissions"], self.facts["contacts"]
        progs = "; ".join(f"{p['name']['en']} [{p['status']}]" + (f", tuition USD {p['tuition_usd']}/year" if p.get("tuition_usd") else "") for p in f["programmes"])
        return (f"Programmes: {progs}.\nFees: application RWF {f['fees']['application_rwf']:,} (non-refundable); admission/registration RWF {f['fees']['registration_rwf']:,}; "
                f"all fees payable only after official admission confirmation; {f['fees']['late_penalty_percent']}% late-payment penalty; payment plans via admissions.\n"
                f"Admissions round: {a['round']} {a['intake']}, {a['opens']} to {a['closes']} (deadline); class start date NOT confirmed.\n"
                f"Contacts: admissions {c['admissions_email']}; general {c['general_email']}; phones {', '.join(c['phones'])}; {f['institution']['office_hours']['en']}; {f['institution']['address']}.\n"
                f"Links: {a['how_to_apply_url']} ; {a['admission_requirements_url']} ; {a['fees_url']} ; {f['institution']['website']}")

    def _state_block(self, st):
        return (f"language={st.lang}; programme of interest={st.programme or 'not stated'}; subjects/background mentioned={', '.join(st.subjects) or 'none'}; "
                f"education level={', '.join(st.levels) or 'not stated'}; applicant category={st.category or 'not stated'}; "
                f"keyword guess of the topic (UNRELIABLE, ignore it when it conflicts with the visitor's words)={st.intent}; previous visitor question={st.last_user_message or 'none'}")

    def _ask_llm(self, message, history, st, intent, retrieved, topics, today, draft=None, scope_check=False):
        lang = st.lang
        ctx_parts, cap = [], 0
        for i, r in enumerate(retrieved, 1):
            if r["source"] == "seed" and r.get("authority", "owner") == "owner":
                label = "UAIT knowledge file (owner-verified)"
            elif r["source"] == "seed":
                label = f"UAIT official website content, collected {r['as_of']}" + (f" ({r['url']})" if r.get("url") else "")
            else:
                label = f"UAIT website page {r['url']}, retrieved {r['as_of']}"
            ctx_parts.append(f"[S{i}] {r['title']} - {label}\n{r['text'][:(1100 if self.compact else 1800)]}")
        ctx_block = "\n\n".join(ctx_parts)
        conflicts = "\n".join(f"- {c['topic']}: {c['detail']}" for c in self.store.conflicts()[:6]) if topics else ""
        note = ""
        if intent == "assessment":
            note = ("The visitor wants an admission suitability assessment. Give a clear verdict, link their background to the programme, "
                    "and name the most important missing item or next step (for example Rwandan vs international, or a document). Say admissions makes the official decision. "
                    "Keep it to a short paragraph.")
        if scope_check:
            note += ("\nSCOPE CHECK: greetings, thanks and small talk (\"how are you\", \"who are you\") deserve a warm, natural human reply, then a gentle offer to help with UAIT. "
                     "Anything about education, studying, skills, careers, admissions or UAIT: answer it properly. "
                     "Only if the question is clearly unrelated (e.g. sports results, coding homework) give a friendly one-line redirect to what you can help with.")
        if not retrieved and not draft:
            note += ("\nNo UAIT-specific source matched this question. Still answer it helpfully in 1-3 sentences using general knowledge about the field, "
                     "the programme type named in the conversation, and how such programmes usually work. Separate that clearly from UAIT facts: say plainly that "
                     "the UAIT-specific detail is not confirmed, never state UAIT specifics you were not given, and end by pointing to admissions.")
        core = "" if (self.compact and scope_check and not DOMAIN.search(message)) else self._core_block(st, today, topics)
        system = build_system(lang, today.isoformat(), self._facts_block(lang), self._state_block(st), ctx_block, conflicts, note, core)
        msgs = [{"role": h["role"], "content": str(h["content"])[:1500]} for h in history[-8:] if h.get("role") in ("user", "assistant") and h.get("content")]
        if not msgs or msgs[-1]["role"] != "user" or msgs[-1]["content"] != message:
            msgs.append({"role": "user", "content": message})
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        text = None
        for attempt in (1, 2):
            try:
                text = self.llm.complete(system, msgs)
                break
            except LLMError as e:
                self.last_llm_error = str(e)[:300]
                log.warning("LLM attempt %d failed: %s", attempt, e)
                if attempt == 2 or any(x in str(e) for x in ("429", "daily cap", "HTTP 40", "Timeout", "temporarily")):
                    return None
                time.sleep(1.0)
        allowed = guard.build_allowed(self.facts, system, self.page_urls, intent)
        bad = guard.violations(text, allowed)
        if bad:
            log.warning("Model answer had unverified details %s; removing those sentences", bad)
            cleaned = guard.redact(text, allowed)
            if not cleaned or guard.violations(cleaned, allowed):
                self.last_llm_error = "answer blocked by the safety check: " + ", ".join(bad[:4])
                return None
            text = cleaned
        self.last_llm_error = None
        text = text.strip()
        srcs = [{"title": r["title"], "url": r.get("url"), "as_of": r.get("as_of")} for r in retrieved[:3]]
        return {"answer": text, "sources": srcs}
