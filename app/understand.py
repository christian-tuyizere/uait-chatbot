"""Turns a message plus the conversation so far into a language, a state and an intent."""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .lang import detect


def rx(p):
    return re.compile(p, re.I)


SUBJECTS = {
    "biology": rx(r"\bbiolog\w*|\bbiomed\w*|\b(pcb|mcb)\b|생물|생명"),
    "mathematics": rx(r"\bmath(s|ematics)?\b|\b(mpc|pcm|mpg|meg|mcb)\b|수학"),
    "physics": rx(r"\bphysics\b|\b(pcb|mpc|pcm|mpg)\b|물리"),
    "chemistry": rx(r"\bchemistry\b|\b(pcb|mcb|pcm)\b|화학"),
    "computer": rx(r"\bcomputer science\b|\bcomputing\b|\bict\b|\binformation technology\b|\bprogramming\b|\bcoding\b|\bsoftware\b|\bmpc\b|컴퓨터|프로그래밍|코딩|소프트웨어"),
    "engineering": rx(r"\bengineering\b|엔지니어|공학"),
    "business": rx(r"\bbusiness\b|\bcommerce\b|\baccounting\b|\beconomics\b|\bfinance\b|\b(meg|heg)\b|경영|경제|회계"),
    "arts": rx(r"\bart\b|\barts\b|\bdesign\b|\bdrawing\b|\bcraft\w*|\bfashion\b|미술|디자인|예술|공예"),
    "humanities": rx(r"\bliterature\b|\bhistory\b|\blanguages?\b|\bhumanities\b|\bgeography\b|\bheg\b|문학|역사|언어|인문"),
    "health": rx(r"\bmedicine\b|\bmedical\b|\bnursing\b|\bhealth\w*|\bpharmac\w*|의학|간호|보건|약학"),
    "agriculture": rx(r"\bagricultur\w*|\bfarming\b|농업"),
}
LEVELS = {
    "a-level (A2) / senior 6": rx(r"\ba2\b|a-?level|advanced level|senior ?6|\bs6\b"),
    "o-level / senior 3": rx(r"o-?level|ordinary level|senior ?3|\bs3\b"),
    "high school": rx(r"high school|secondary school|고등학교"),
    "diploma": rx(r"\bdiploma\b|디플로마"),
    "bachelor's degree": rx(r"\bbachelor\w*|\bundergrad\w*|학사"),
    "master's degree": rx(r"\bmaster'?s?\b|석사"),
}
PROGRAMMES = {
    "ai": rx(r"\bai\b|artificial intelligence|machine learning|인공지능"),
    "jewelry": rx(r"jewel+e?ry|주얼리|보석"),
    "piano": rx(r"piano performance|피아노 ?연주"),
    "drone": rx(r"\bdrones?\b|드론"),
    "cyber": rx(r"cyber ?security|사이버 ?보안"),
    "advdip": rx(r"advanced diploma|고급 ?디플로마"),
}
CATEGORY = {
    "rwandan": rx(r"\brwandan\b|르완다 ?(사람|인|국적|학생)"),
    "international": rx(r"\binternational\b|\bforeign\w*|\babroad\b|outside rwanda|from (kenya|uganda|tanzania|burundi|drc|congo|nigeria|ghana|ethiopia|south africa|korea|south korea|india|china|usa|uk)\b|외국인|해외|국제 ?학생|한국(인|에서)|케냐|우간다|탄자니아|부룬디|콩고|나이지리아"),
}

P = {
    "injection": rx(r"ignore (all |any |your |the |previous |prior )+(instructions?|rules?|prompts?)|disregard (all |your |the )*(instructions?|rules?)|system prompt|reveal your (prompt|instructions)|developer mode|jailbreak|you are now|act as (?!an? (student|applicant))|이전 ?(지시|명령|지침)|시스템 ?프롬프트|지시를? ?무시|규칙을? ?무시"),
    "fabricate": rx(r"\b(invent|make up|fabricate|just guess|pretend)\b|지어내|꾸며|아무거나 ?말|추측해서"),
    "greeting": rx(r"^\s*(hi|hello|hey|hiya|good (morning|afternoon|evening)|greetings|salut|bonjour|muraho|안녕\w*|하이|여보세요)[\s!.,?~]*$"),
    "thanks": rx(r"^\s*(thanks?( you)?|thank you( so much)?|thx|ok(ay)? thanks|감사\w*|고마워\w*|고맙\w*)[\s!.,?~]*$"),
    "identity": rx(r"\b(who are you|what are you|your name|are you (a )?(bot|ai|human|real)|which model|what model)\b|너는 ?누구|누구세요|이름이 ?뭐|사람이야|무슨 ?모델"),
    "payment_done": rx(r"\b(i|we)( have|'ve)? (already )?(paid|sent|transferred|deposited)\b|\balready (paid|sent|transferred)\b|\bi paid\b|이미 ?(냈|납부|송금|입금)|(송금|입금|납부)(을)? ?(했|하였)"),
    "payment_timing": rx(r"\b(pay|paying|payment|deposit|send money|transfer)\b.*\b(before|first|now|already|early|in advance|upfront|ahead)\b|\b(before|first|now|already|early|in advance|upfront)\b.*\b(pay|paying|payment|deposit|send money|transfer)\b|when (should|do|can|must) i (have to )?pay|do i (have|need) to pay|(먼저|미리|지금|전에).*(납부|결제|송금|입금|돈|내야|내도|내나요)|(납부|결제|송금|입금).*(먼저|미리|지금|전에)|언제 ?(내|납부|결제|송금)"),
    "payment_method": rx(r"\b(bank|account number|iban|swift|mobile money|momo|mtn|ussd|how (do|can|to|should) (i |we )?pay|payment (method|option|channel|instruction|detail)s?|where (do|can|to|should) (i |we )?(pay|send)|send money|wire|deposit)\b|계좌|은행|송금|입금|납부 ?방법|결제 ?방법|모바일 ?머니|\bmtn\b|ussd|어떻게 ?(내|납부|결제)"),
    "job_guarantee": rx(r"(guarantee\w*|promise\w*|definitely|assured|sure to).{0,60}(job|employment|internship|placement|work|salary|hired)|(job|employment|internship|placement|salary).{0,60}(guarantee\w*|promise\w*|assured)|(취업|일자리|인턴|급여).{0,20}(보장|확정|약속)|(보장|약속).{0,20}(취업|일자리|인턴)"),
    "hope": rx(r"hope (goat|project|&|and)|호프 ?(프로젝트)?|hope goat|\bgoats?\b|\bsheep\b|livestock|염소|양 ?사육|가축"),
    "coming_soon": rx(r"piano performance|\bdrones?\b|cyber ?security|advanced diploma|coming soon|launch date|피아노 ?연주|드론|사이버 ?보안|고급 ?디플로마|개설 ?예정"),
    "community": rx(r"community academy|piano class|korean (language )?(class|course|lesson)s?|computer class|커뮤니티 ?아카데미|피아노 ?(클래스|수업)|한국어 ?(수업|클래스|강좌)|컴퓨터 ?(수업|클래스)"),
    "deadline": rx(r"\b(deadline|due date|closing date|close[sd]?|last day|application period|application dates?|round|opens? on|when (does|do|is|will|can) .{0,30}(appl\w+|intake|round|admission)|old deadline)\b|마감|지원 ?기간|접수 ?기간|언제까지|신청 ?기간|몇 ?월|1차"),
    "fees": rx(r"\b(tuition|fees?|cost|costs|price|prices|how much|expensive|cheap|afford|charge[sd]?|rwf|usd|payment plans?|instal+ments?|late (payment|fee)s?|penalty)\b|학비|수업료|등록금|비용|얼마|가격|요금|분할|연체"),
    "apply": rx(r"\b(how (do|can|to|should) (i |we )?(apply|join|enrol\w*|register)|application (process|steps?|form)|apply (to|for|at)|google form|admission process|walk[- ]?in|paper application|steps to apply|enrol\w*)\b|어떻게 ?(지원|입학|등록)|지원 ?(방법|절차)|입학 ?(절차|방법)|구글 ?폼|신청 ?방법"),
    "open_programs": rx(r"(which|what|any).{0,30}(programs?|programmes?|courses?|majors?).{0,30}(open|offer\w*|available|have|provide)|(programs?|programmes?|courses?) (are )?(open|available|offered)|what can i study|do you offer|what do you (teach|offer)|어떤.{0,10}(과정|학과|프로그램)|무슨.{0,10}(과정|학과|프로그램)|(모집|개설) ?(중|과정)"),
    "documents": rx(r"\b(documents?|papers|transcripts?|requirements?|what do i need|what should i (prepare|submit|bring)|passport|id copy|certificate required|recommendation|letters?|portfolio|optional)\b|서류|제출|구비|추천서|포트폴리오|필요한 ?(것|서류)|준비물"),
    "authorization": rx(r"\b(authori[sz]\w*|accredit\w*|rtb|tvet|recogni[sz]ed|legit\w*|licen[sc]ed|approved|real school|scam)\b|인가|공인|정식|합법|사기|승인"),
    "contact": rx(r"\b(contact|phone|email|e-mail|call|reach|office hours|opening hours|working hours|business hours|open hours|what time (do|are) you|address|telephone|whatsapp|where is (uait|the (campus|school|office|institute))|located|directions)\b|연락|문의|전화|이메일|메일|주소|오시는|사무실|운영 ?시간|위치"),
}

UNCONFIRMED = {
    "start_date": rx(r"start date|classes? (begin|start)|semester (start|begin)|when (will|do|does).{0,30}(start|begin)|term (start|begin)|개강|수업 ?시작"),
    "housing": rx(r"housing|accommodation|dorm\w*|hostel|residence|기숙사|숙소"),
    "library": rx(r"\blibrary\b|도서관"),
    "counselling": rx(r"counsel\w*|상담"),
    "portal": rx(r"student portal|\bportal\b|포털"),
    "placement": rx(r"placement (rate|percentage)|job rate|percent\w* .{0,30}(jobs?|employed)|취업률"),
    "scholarship": rx(r"scholarship|financial aid|bursary|grant\b|장학금"),
    "interview_exam": rx(r"interview date|exam date|entrance exam|interview|면접|시험 ?일정"),
    "study_mode": rx(r"part[- ]?time|full[- ]?time|online (class|course|study|learning)|evening (class|course)|weekend (class|course)|distance learning|remote (class|study)|온라인 ?(수업|강의|과정)|야간|파트 ?타임|주말 ?(수업|반)"),
    "intake_size": rx(r"intake size|how many students|class size|seats|모집 ?인원|정원"),
    "faculty": rx(r"faculty|lecturer|professor|who teaches|instructors?|teachers?|dean|교수|교직원|강사"),
    "partnership": rx(r"partner\w*|collaborat\w*|협력|제휴|파트너"),
    "leadership": rx(r"leadership|rector|director|founder|president|chancellor|principal|총장|학장|설립자"),
    "vision_mission": rx(r"\bvision\b|\bmission\b|\bvalues\b|비전|미션|교육 ?목표"),
    "news_events": rx(r"\bnews\b|\bevents?\b|announcement|소식|뉴스|행사|공지"),
}

JOIN = rx(r"\b(can|could|may) (i|we) (join|enrol\w*|enroll|attend|get (in|into|admitted)|be admitted|study (at|in) uait)\b|\bhow (do|can|should) (i|we) join\b|\b(want|like|wish|hope) to (join|attend|study at|enrol\w*)\b|\b(join|attend) uait\b|\bwho can (apply|join)\b|\bam i (eligible|allowed|able to (join|apply))\s*[?.!]*$|입학할 ?수|들어갈 ?수|입학하고 ?싶|다니고 ?싶")
ELIG = rx(r"\b(can|could|may|should|would|will|do|does|am|is|are) (i|we)\b|\bqualif\w*|\beligib\w*|\bsuitable\b|\bfit\b|\bchance\b|\badmit\w*|\bgood enough\b|\bbackground\b|\bstudied\b|\bgraduat\w*|\bmy (degree|combination|major)\b|\bhelp\w*|\brelevant\b|\buseful\b|\bconnect\w*|\brelate\w*|할 ?수 ?있|도움|가능|자격|적합|합격|전공|공부했|졸업|배경|괜찮")
BACKGROUND_STMT = rx(r"\bi (studied|majored|graduated|have studied)\b|\bi (finished|completed) (my )?(a-?level|o-?level|senior|high school|secondary|diploma|degree|bachelor)|\bi have (a|an) (degree|diploma)\b|\bmy background\b|(을|를) ?(전공|공부)했|전공했|졸업했")
CONTENT_Q = rx(r"what (will|do|can|would) (i|we|students?) (learn|study|cover)|what (is|are) (taught|covered)|\\bcurriculum\\b|\\bsyllabus\\b|무엇을 ?(배우|공부)|뭘 ?배우|커리큘럼")
NEEDS = rx(r"\bwhat (do|does|should|must|would|will) (i|we|a student|an applicant|one)\b.{0,20}\b(need|require|bring|prepare|submit|provide|have)\b|\bwhat('s| is| are) (needed|required|the requirements?|the entry requirements?)\b|\b(requirements?|prerequisites?) (to|for)\b|\bwhat to (prepare|bring|submit)\b|\bneeded to (apply|join|enrol\\w*|get in)\b|\b(need|require\\w*) to (apply|join|get (in|into|admitted))\b|필요한 ?(것|서류|조건)|입학 ?(조건|요건|자격)|지원 ?(자격|조건)")
WH = rx(r"^\s*(what|how|which|why|who|where|when)\b")
FOLLOWUP = rx(r"^\s*(what|how) about\b|^\s*and\b|^\s*(그럼|그러면|그리고|그럼요|그건|그것은)")


@dataclass
class State:
    lang: str = "en"
    programme: Optional[str] = None
    subjects: List[str] = field(default_factory=list)
    levels: List[str] = field(default_factory=list)
    category: Optional[str] = None
    prior_intents: List[str] = field(default_factory=list)
    assessing: bool = False
    intent: str = "general"
    topic: Optional[str] = None
    last_user_message: Optional[str] = None
    detail: bool = False


def hits(table, text):
    return [k for k, r in table.items() if r.search(text)]


def classify(msg: str, assessing: bool = False):
    """Return (intent, topic). First match wins; order matters."""
    words = len(msg.split())
    if P["injection"].search(msg):
        return "injection", None
    if P["fabricate"].search(msg):
        return "fabricate", None
    if words <= 8:
        for name in ("greeting", "thanks"):
            if P[name].search(msg):
                return name, None
    if P["identity"].search(msg):
        return "identity", None
    if P["payment_done"].search(msg):
        return "payment_done", None
    if P["payment_timing"].search(msg) and (P["payment_method"].search(msg) or re.search(r"\bpay\w*|납부|결제|송금|입금|돈|내야|내도|내나요", msg, re.I)):
        return "payment_timing", None
    if P["payment_method"].search(msg):
        return "payment_method", None
    if P["job_guarantee"].search(msg):
        return "job_guarantee", None
    if P["hope"].search(msg):
        return "hope", None
    if P["coming_soon"].search(msg):
        return "coming_soon", None
    if P["community"].search(msg):
        return "community", None
    if re.search(r"\b(contact|phone|email|e-mail|call|reach|whatsapp|working hours|business hours|opening hours|office hours)\b|연락|문의|전화|이메일|운영 ?시간", msg, re.I):
        return "contact", None
    subj = bool(hits(SUBJECTS, msg) or hits(LEVELS, msg))
    if CONTENT_Q.search(msg) and not BACKGROUND_STMT.search(msg):
        return "general", None  # a question about programme content, not an eligibility check
    if (subj and ELIG.search(msg)) or BACKGROUND_STMT.search(msg) or (assessing and subj and (words <= 8 or FOLLOWUP.search(msg))):
        return "assessment", None
    if re.search(r"\bwhich (programme|program|course|one)\b.{0,30}\b(should|better|best|choose|pick|suit\w*|right for)\b|어느 ?(과정|쪽).{0,10}(좋|추천|선택)", msg, re.I):
        return "compare", None
    if NEEDS.search(msg):
        return "documents", None  # "what do I need to apply/join" asks for requirements, not "is it open" or "can I join"
    if JOIN.search(msg) and not subj:
        return "join", None
    if len(hits({k: v for k, v in PROGRAMMES.items() if k in ("ai", "jewelry")}, msg)) == 2 and re.search(r"differen\w*|compar\w*|versus|\bvs\.?\b|which (one|is better)|차이|비교", msg, re.I):
        return "compare", None
    if not (WH.search(msg) and not re.search(r"\b(open|available|accepting|still)\b|모집", msg, re.I)) and hits({k: v for k, v in PROGRAMMES.items() if k in ("ai", "jewelry")}, msg) and re.search(
            r"\b(open|apply|applying|available|intake|admission|enrol\w*|join|register|accept\w*)\b|지원|모집|입학|등록|가능", msg, re.I):
        return "programme_status", None
    if P["deadline"].search(msg):
        return "deadline", None
    for topic, r in UNCONFIRMED.items():
        if r.search(msg):
            return "unconfirmed", topic
    for name in ("fees", "apply", "open_programs", "documents", "authorization", "contact"):
        if P[name].search(msg):
            return name, None
    return "general", None


def build_state(message: str, history, ui_lang: Optional[str] = None) -> State:
    user_msgs = [h["content"] for h in (history or []) if h.get("role") == "user" and isinstance(h.get("content"), str)]
    # Language: this message wins; otherwise the latest earlier message; otherwise the UI choice.
    lang = detect(message)
    if lang is None:
        for m in reversed(user_msgs):
            lang = detect(m)
            if lang:
                break
    st = State(lang=lang or (ui_lang if ui_lang in ("en", "ko") else "en"))
    prior, assessing = [], False
    for m in user_msgs:
        it, _ = classify(m, assessing)
        prior.append(it)
        assessing = assessing or it == "assessment"
    st.prior_intents, st.assessing = prior, assessing
    for m in user_msgs + [message]:
        for p in hits({k: v for k, v in PROGRAMMES.items() if k in ("ai", "jewelry")}, m):
            st.programme = p
        for s in hits(SUBJECTS, m):
            if s in st.subjects:
                st.subjects.remove(s)
            st.subjects.append(s)
        for lv in hits(LEVELS, m):
            if lv not in st.levels:
                st.levels.append(lv)
        for c in hits(CATEGORY, m):
            st.category = c
    st.intent, st.topic = classify(message, assessing)
    st.last_user_message = user_msgs[-1] if user_msgs else None
    return st
