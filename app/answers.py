"""Verified, bilingual answers built from data/facts.json.

Anything that involves money, dates, contacts or programme status is rendered here from
structured facts, so it can never drift or be invented by a language model.
"""
import datetime as dt
import re

from .understand import PROGRAMMES, SUBJECTS, hits

SOURCES = {
    "fees": ("Published fees", "공개된 비용"),
    "contacts": ("Official contacts and location", "공식 연락처 및 위치"),
    "programmes": ("Programmes open for 2027/2028", "2027/2028 모집 과정"),
    "coming": ("Coming-soon programmes", "개설 예정 과정"),
    "dates": ("First Round application dates", "1차 지원 일정"),
    "apply": ("Official application process", "공식 지원 절차"),
    "docs": ("Application documents", "지원 서류"),
    "payment": ("Payment guidance", "납부 안내"),
    "community": ("Community Academy classes", "커뮤니티 아카데미 수업"),
    "hope": ("Hope Goat & Sheep Project", "Hope Goat & Sheep 프로젝트"),
    "auth": ("AI Technology authorization", "AI Technology 과정 인가"),
    "unconfirmed": ("Information not confirmed", "확인되지 않은 정보"),
}

UNCONFIRMED_LABELS = {
    "start_date": ("the class start date", "개강일"), "housing": ("student housing", "기숙사"),
    "library": ("library services", "도서관 서비스"), "counselling": ("counselling services", "상담 서비스"),
    "portal": ("the student portal", "학생 포털"),
    "placement": ("job-placement or internship percentages", "취업률·인턴십 비율"),
    "scholarship": ("scholarship amounts or availability", "장학금 금액·수혜 가능 여부"),
    "interview_exam": ("interview or exam dates", "면접·시험 일정"), "intake_size": ("intake sizes", "모집 인원"),
    "faculty": ("faculty and lecturer details", "교수진 정보"), "partnership": ("partnership details", "협력 기관 정보"),
    "leadership": ("leadership details", "학교 운영진 정보"), "vision_mission": ("the vision, mission and values", "비전·미션·가치"),
    "news_events": ("news and events", "소식·행사"),
}

UNCONFIRMED_LABELS["study_mode"] = ("part-time, online or evening study options", "파트타임·온라인·야간 수업 여부")

RELEVANCE = {
    "biology": ("Biology connects to AI through bioinformatics, genomics, healthcare and medical-imaging technology, and agricultural data. Understanding living systems is a real strength for AI projects in those areas.",
                "생물학은 생물정보학, 유전체학, 의료·헬스케어 기술, 의료 영상, 농업 데이터 분야에서 AI와 만납니다. 생명 현상에 대한 이해는 이런 분야의 AI 프로젝트에서 강점이 됩니다."),
    "mathematics": ("Mathematics is a strong foundation for AI: statistics, probability, linear algebra and calculus underpin machine learning.",
                    "수학은 AI의 탄탄한 기초입니다. 통계, 확률, 선형대수, 미적분이 머신러닝의 바탕이 됩니다."),
    "physics": ("Physics builds quantitative problem-solving and modelling skills that transfer to data science, robotics and sensor-based AI.",
                "물리학은 데이터 사이언스, 로보틱스, 센서 기반 AI에 활용되는 정량적 문제 해결과 모델링 능력을 길러 줍니다."),
    "chemistry": ("Chemistry gives you experience with data-driven experiments, which links to AI in materials science, drug discovery and lab analytics.",
                  "화학은 데이터 기반 실험 경험을 쌓게 해 주며, 소재 과학, 신약 개발, 실험 데이터 분석 분야의 AI와 이어집니다."),
    "computer": ("A computing background gives you a head start with programming and data, although the programme does not require prior coding experience.",
                 "컴퓨터 관련 배경은 프로그래밍과 데이터 다루기에서 유리하지만, 이 과정은 코딩 경험을 요구하지 않습니다."),
    "engineering": ("Engineering trains structured problem solving and systems thinking, which is very useful for building AI applications.",
                    "공학은 체계적인 문제 해결과 시스템 사고를 길러 주어 AI 응용 개발에 매우 유용합니다."),
    "business": ("Business and economics help you apply AI to real decisions such as forecasting, analytics and operations.",
                 "경영·경제 지식은 수요 예측, 분석, 운영 등 실제 의사결정에 AI를 적용하는 데 도움이 됩니다."),
    "arts": ("Art and design bring creativity and visual thinking that are useful for AI-assisted design, and they are also directly relevant to the Jewelry Design Certificate.",
             "미술·디자인은 AI 활용 디자인에 유용한 창의력과 시각적 사고를 길러 주며, Jewelry Design 자격과정과도 직접 관련됩니다."),
    "humanities": ("Languages and humanities help in natural-language technology and AI ethics.",
                   "언어와 인문학은 자연어 처리 기술과 AI 윤리 분야에 도움이 됩니다."),
    "health": ("Health and medicine connect to healthcare AI such as diagnostic support and patient-data analysis.",
               "보건·의학은 진단 보조, 환자 데이터 분석 같은 헬스케어 AI와 연결됩니다."),
    "agriculture": ("Agriculture connects to precision farming, crop monitoring and data-driven yield prediction.",
                    "농업은 정밀 농업, 작물 모니터링, 데이터 기반 수확량 예측과 연결됩니다."),
}
SUBJECT_NAMES = {
    "biology": ("Biology", "생물학"), "mathematics": ("Mathematics", "수학"), "physics": ("Physics", "물리학"),
    "chemistry": ("Chemistry", "화학"), "computer": ("Computing/ICT", "컴퓨터/ICT"), "engineering": ("Engineering", "공학"),
    "business": ("Business/Economics", "경영/경제"), "arts": ("Art/Design", "미술/디자인"),
    "humanities": ("Languages/Humanities", "언어/인문학"), "health": ("Health/Medicine", "보건/의학"),
    "agriculture": ("Agriculture", "농업"),
}


def L(lang, en, ko):
    return ko if lang == "ko" else en


def d(lang, iso):
    y, m, dd = (int(x) for x in iso.split("-"))
    if lang == "ko":
        return f"{y}년 {m}월 {dd}일"
    return f"{dd} {dt.date(y, m, dd).strftime('%B')} {y}"


def rwf(lang, n):
    return f"{n:,} RWF" if lang == "ko" else f"RWF {n:,}"


def usd(lang, n):
    return f"연 {n:,} USD" if lang == "ko" else f"USD {n:,} per year"


def prog_name(facts, pid, lang):
    for p in facts["programmes"]:
        if p["id"] == pid:
            return p["name"][lang]
    return pid


def src(key, url=None):
    en, ko = SOURCES[key]
    return {"title": {"en": en, "ko": ko}, "url": url}


def refer(lang, facts):
    c, i = facts["contacts"], facts["institution"]
    return L(lang,
             f"To confirm, contact UAIT: admissions {c['admissions_email']}, general enquiries {c['general_email']}, "
             f"phone {c['phones'][0]} or {c['phones'][1]} ({i['office_hours']['en']}).",
             f"확인이 필요하시면 UAIT에 문의해 주세요. 입학 문의 {c['admissions_email']}, 일반 문의 {c['general_email']}, "
             f"전화 {c['phones'][0]} 또는 {c['phones'][1]} ({i['office_hours']['ko']}).")


def verify_note(lang, topics, key):
    if key in topics:
        return L(lang,
                 "\n\nNote: the published website currently shows details that differ from my verified information. Please confirm directly with UAIT before relying on this.",
                 "\n\n참고: 공식 웹사이트에 게시된 내용 중 제가 가진 확인된 정보와 다른 부분이 있습니다. 이 내용에 의존하기 전에 UAIT에 직접 확인해 주세요.")
    return ""


def open_names(facts, lang):
    return [p["name"][lang] for p in facts["programmes"] if p["status"] == "open"]


def soon_names(facts, lang):
    return [p["name"][lang] for p in facts["programmes"] if p["status"] == "coming_soon"]


def dates_line(lang, facts, today):
    a = facts["admissions"]
    rk = a.get("round_ko", "1차 모집")
    closes = dt.date.fromisoformat(a["closes"])
    opens = dt.date.fromisoformat(a["opens"])
    if today > closes:
        return L(lang, f"The {a['round']} for {a['intake']} closed on {d('en', a['closes'])}. Please ask admissions about the next round.",
                 f"{a['intake']}학년도 {rk}은 {d('ko', a['closes'])}에 마감되었습니다. 다음 모집은 입학처에 문의해 주세요.")
    left = (closes - today).days
    extra_en = f" That is {left} day{'s' if left != 1 else ''} from today." if today >= opens else ""
    extra_ko = f" 오늘부터 {left}일 남았습니다." if today >= opens else ""
    return L(lang, f"The {a['round']} for the {a['intake']} intake runs from {d('en', a['opens'])} to {d('en', a['closes'])}, which is the application deadline.{extra_en}",
             f"{a['intake']}학년도 {rk}은 {d('ko', a['opens'])}부터 {d('ko', a['closes'])}까지이며, {d('ko', a['closes'])}이 지원 마감일입니다.{extra_ko}")


def render_full(intent, st, facts, ctx):
    """Long verified answer (used when the visitor asks for detail, and as reference material for the model)."""
    lang, today = st.lang, ctx["today"]
    c, a, fe = facts["contacts"], facts["admissions"], facts["fees"]
    topics = ctx.get("conflict_topics", set())
    ref = refer(lang, facts)
    site = facts["institution"]["website"]

    if intent == "greeting":
        return {"answer": L(lang, "Hello! Welcome to UAIT. I'm the UAIT Official AI Assistant. I can help with programmes, admissions, fees, application documents and student activities. What would you like to know?",
                            "안녕하세요! UAIT에 오신 것을 환영합니다. 저는 UAIT 공식 AI 어시스턴트입니다. 과정, 입학, 학비, 지원 서류, 학생 활동에 대해 도와드릴 수 있어요. 무엇이 궁금하신가요?"), "sources": []}
    if intent == "thanks":
        return {"answer": L(lang, "You're welcome! Is there anything else about UAIT I can help you with?", "천만에요! UAIT에 대해 더 궁금한 점이 있으신가요?"), "sources": []}
    if intent == "identity":
        return {"answer": L(lang, "I'm the UAIT Official AI Assistant, a digital assistant for the United African Institute of Technology. I answer questions about admissions, programmes, fees, documents and activities in English and Korean, using UAIT's verified information and its official website. I can't submit applications or make official admission decisions.",
                            "저는 United African Institute of Technology(UAIT)의 공식 AI 어시스턴트입니다. UAIT의 확인된 정보와 공식 웹사이트를 바탕으로 입학, 과정, 학비, 서류, 활동에 대한 질문에 영어와 한국어로 답해 드립니다. 지원서를 대신 제출하거나 공식 입학 결정을 내릴 수는 없습니다."), "sources": []}
    if intent in ("injection", "fabricate"):
        return {"answer": L(lang, f"I can't invent or change official UAIT information, and I can't set aside my safety rules. What I can confirm: only {' and '.join(open_names(facts, 'en'))} are open for the {a['intake']} {a['round']} (deadline {d('en', a['closes'])}); {', '.join(soon_names(facts, 'en'))} are coming soon with no confirmed launch dates. {ref}",
                            f"공식 UAIT 정보를 지어내거나 바꿀 수 없고, 안전 규칙을 무시할 수도 없습니다. 확인된 내용은 다음과 같습니다. {a['intake']}학년도 {a.get('round_ko', '1차 모집')}에는 {', '.join(open_names(facts, 'ko'))}만 모집 중이며(마감 {d('ko', a['closes'])}), {', '.join(soon_names(facts, 'ko'))}은(는) 개설 예정이고 일정은 확정되지 않았습니다. {ref}"),
                "sources": [src("programmes"), src("coming")]}
    if intent == "off_topic":
        return {"answer": L(lang, "I'm the UAIT Official AI Assistant. I can help you with questions about UAIT, including admissions, academic programmes, fees, student opportunities and institutional activities. How can I help you with UAIT?",
                            "저는 UAIT 공식 AI 어시스턴트입니다. 입학, 학업 과정, 학비, 학생 기회, 학교 활동 등 UAIT와 관련된 질문을 도와드릴 수 있습니다. UAIT에 대해 무엇을 도와드릴까요?"), "sources": []}

    if intent == "contact":
        text = L(lang,
                 f"United African Institute of Technology (UAIT)\nAddress: {facts['institution']['address']}\nWebsite: {site}\nAdmissions: {c['admissions_email']}\nGeneral enquiries: {c['general_email']}\nPhone: {c['phones'][0]} / {c['phones'][1]}\nOffice hours: {facts['institution']['office_hours']['en']}",
                 f"United African Institute of Technology (UAIT)\n주소: {facts['institution']['address']}\n웹사이트: {site}\n입학 문의: {c['admissions_email']}\n일반 문의: {c['general_email']}\n전화: {c['phones'][0]} / {c['phones'][1]}\n운영 시간: {facts['institution']['office_hours']['ko']}")
        return {"answer": text + verify_note(lang, topics, "contact"), "sources": [src("contacts", site)]}

    if intent == "fees":
        progs = [p for p in facts["programmes"] if p["status"] == "open" and (st.programme in (None, p["id"]))]
        lines = [L(lang, f"{p['name']['en']} tuition: {usd('en', p['tuition_usd'])}", f"{p['name']['ko']} 수업료: {usd('ko', p['tuition_usd'])}") for p in progs]
        lines.append(L(lang, f"Application fee: {rwf('en', fe['application_rwf'])} (non-refundable)", f"지원비: {rwf('ko', fe['application_rwf'])} (환불 불가)"))
        lines.append(L(lang, f"Admission/registration fee: {rwf('en', fe['registration_rwf'])}", f"입학·등록비: {rwf('ko', fe['registration_rwf'])}"))
        body = "\n".join("• " + x for x in lines)
        tail = L(lang,
                 f"\n\nAll applicable fees are payable only after official admission confirmation, and paying does not guarantee admission. Tuition is due before the start of each semester; USD tuition may be paid in RWF at the applicable exchange rate, payment plans are available through admissions, and a {fe['late_penalty_percent']}% late-payment penalty is stated. I don't convert amounts myself because that needs a verified exchange rate.\n\n{ref}",
                 f"\n\n모든 해당 비용은 공식 입학 확정 통보 이후에만 납부하며, 납부가 입학을 보장하지는 않습니다. 수업료는 매 학기 시작 전에 납부하고, USD 수업료는 적용 환율로 RWF로 낼 수 있으며, 분할 납부는 입학처를 통해 가능하고, 납부 지연 시 {fe['late_penalty_percent']}% 연체료가 명시되어 있습니다. 검증된 환율이 필요하므로 금액을 직접 환산하지는 않습니다.\n\n{ref}")
        head = L(lang, "Here are the published UAIT fees:\n", "공개된 UAIT 비용은 다음과 같습니다.\n")
        return {"answer": head + body + tail + verify_note(lang, topics, "fees"), "sources": [src("fees", a["fees_url"])]}

    if intent in ("payment_timing", "payment_method"):
        warn = L(lang, "Important: pay only after you receive official admission confirmation from UAIT. Never send money before admission is confirmed, and if you're unsure whether a payment request is genuine, contact admissions first.",
                 "중요: UAIT의 공식 입학 확정 통보를 받은 후에만 납부하세요. 입학이 확정되기 전에는 절대 송금하지 마시고, 납부 요청이 진짜인지 확신이 서지 않으면 먼저 입학처에 문의하세요.")
        lead = ""
        if intent == "payment_timing":
            lead = L(lang, "No. Please don't pay before official admission confirmation. This applies to the application fee, the admission/registration fee and tuition, and paying does not guarantee admission.\n\n",
                     "아니요. 공식 입학 확정 통보 전에는 납부하지 마세요. 지원비, 입학·등록비, 수업료 모두 해당되며, 납부가 입학을 보장하지는 않습니다.\n\n")
        owner = facts["payment"].get("official_instructions") or []
        parts = [lead + warn]
        if owner:
            parts.append(L(lang, "Official payment instructions:\n", "공식 납부 안내:\n") + "\n".join(owner))
        else:
            parts.append(L(lang, f"The published payment options are {' and '.join(facts['payment']['published_methods'])}. For the exact account details and mobile-money steps, use the official Fees & Payments page: {a['fees_url']}. I don't repeat account numbers or codes from memory, so please verify them on the live official page before you send any money.",
                           f"공개된 납부 방법은 Bank of Kigali 송금과 MTN 모바일 머니입니다. 정확한 계좌 정보와 모바일 머니 절차는 공식 '수업료 및 납부' 페이지({a['fees_url']})에서 확인하세요. 계좌번호나 코드는 송금 전에 최신 공식 페이지에서 직접 확인(verify)하셔야 하므로 기억에 의존해 알려드리지 않습니다."))
        ex = ctx.get("payment_excerpt")
        if ex and not owner:
            parts.append(L(lang, f"Latest published instructions (retrieved {ex['date']} from {ex['url']}):\n{ex['text']}",
                           f"최근 게시된 안내({ex['date']}, {ex['url']}에서 확인):\n{ex['text']}"))
        if intent == "payment_method":
            parts.append(L(lang, "If the website seems to ask for the application fee earlier than after admission confirmation, confirm with admissions before sending any money.",
                           "웹사이트에서 지원비를 입학 확정 전에 내라고 안내하는 것처럼 보이면, 송금하기 전에 입학처에 확인하세요."))
        parts.append(ref)
        return {"answer": "\n\n".join(parts) + verify_note(lang, topics, "contact"), "sources": [src("payment", a["fees_url"])]}

    if intent == "payment_done":
        return {"answer": L(lang, f"If you have already sent money, please contact admissions right away and keep your receipt or proof of payment so they can check it. I can't verify payments or confirm admission myself. UAIT asks for fees only after official admission confirmation, so if you paid to an account or number that was not given on the official Fees & Payments page ({a['fees_url']}), tell admissions and your bank or mobile-money provider immediately.\n\n{ref}",
                            f"이미 송금하셨다면 영수증 또는 송금 증빙을 보관하시고 바로 입학처에 연락해 확인을 받으세요. 저는 납부 내역을 확인하거나 입학을 확정할 수 없습니다. UAIT는 공식 입학 확정 후에만 비용을 안내하므로, 공식 '수업료 및 납부' 페이지({a['fees_url']})에 없는 계좌나 번호로 보내셨다면 즉시 입학처와 은행 또는 모바일 머니 업체에 알려 주세요.\n\n{ref}"),
                "sources": [src("payment", a["fees_url"])]}
    if intent == "job_guarantee":
        return {"answer": L(lang, f"UAIT lists career placement assistance for AI Technology, and past international internship experiences are documented for Jewelry Design. UAIT does not guarantee a job, a salary, an internship or an overseas placement, and no verified placement percentage is available. {ref}",
                            f"UAIT는 AI Technology 과정에 취업 지원을 제공한다고 안내하고 있으며, Jewelry Design 과정에는 과거 해외 인턴십 사례가 기록되어 있습니다. 그러나 취업, 급여, 인턴십, 해외 배치는 보장되지 않으며 검증된 취업률도 없습니다. {ref}"),
                "sources": [src("programmes")]}
    if intent == "hope":
        h = c["restricted"]["hope_project"]
        return {"answer": L(lang, f"The Hope Goat & Sheep Project is a separate university-led livestock initiative. It is not an academic certificate programme and not a Community Academy course. For questions about the project only: {h['emails'][0]} or {h['phones'][0]}. Please don't use these contacts for admissions; for admissions use {c['admissions_email']}.",
                            f"Hope Goat & Sheep 프로젝트는 대학이 주도하는 별도의 가축 사육 사업으로, 학위·자격과정이나 커뮤니티 아카데미 수업이 아닙니다. 프로젝트 관련 문의만 {h['emails'][0]} 또는 {h['phones'][0]}로 연락하세요. 입학 문의에는 사용하지 마시고, 입학은 {c['admissions_email']}로 문의해 주세요."),
                "sources": [src("hope")]}

    if intent == "coming_soon":
        named = hits(PROGRAMMES, ctx["message"])
        named = [n for n in named if n in ("piano", "drone", "cyber", "advdip")]
        names = [prog_name(facts, n, lang) for n in named] or soon_names(facts, lang)
        return {"answer": L(lang, f"{', '.join(names)} {'is' if len(names) == 1 else 'are'} listed as coming soon and not currently open for applications for the {a['intake']} intake. No launch date is confirmed. At the moment only {' and '.join(open_names(facts, 'en'))} accept applications. {ref}",
                            f"{', '.join(names)}: 개설 예정 과정으로, {a['intake']}학년도에는 아직 지원할 수 없습니다. 개설 일정은 확정되지 않았습니다. 현재 지원 가능한 과정은 {', '.join(open_names(facts, 'ko'))}뿐입니다. {ref}"),
                "sources": [src("coming")]}
    if intent == "community":
        fee_q = re.search(r"fee|cost|how much|price|tuition|얼마|비용|수강료", ctx["message"], re.I)
        base = L(lang, "The Community Academy offers Piano Class, Korean Language and Computer Class. To join, contact admissions directly rather than using the certificate application Google Form.",
                 "커뮤니티 아카데미에서는 피아노 클래스, 한국어, 컴퓨터 수업을 운영합니다. 수강 신청은 자격과정 지원 구글 폼이 아니라 입학처에 직접 문의해 주세요.")
        extra = L(lang, " Class fees are not published, so please request the current amount from admissions.", " 수강료는 공개되어 있지 않으니 입학처에 현재 금액을 문의해 주세요.") if fee_q else ""
        return {"answer": f"{base}{extra} {ref}", "sources": [src("community")]}

    if intent == "join":
        return {"answer": L(lang,
                f"Yes, you can apply to UAIT. Two programmes are open for the {a['intake']} intake: {' and '.join(open_names(facts, 'en'))}. {dates_line('en', facts, today)}\n\nTo join:\n1. Check that you meet the published requirements: secondary-school certificates and transcripts (A2 or equivalent), a national ID or passport copy, a self-introduction and a Statement of Learning Commitment.\n2. Apply only through the official Google Form linked from {a['how_to_apply_url']}.\n3. Wait for official admission confirmation, and pay fees only after that.\n\nTell me which programme interests you and your education background (and whether you are Rwandan or international), and I'll tell you how your profile fits what UAIT asks. {ref}",
                f"네, UAIT에 지원하실 수 있습니다. {a['intake']}학년도에는 {', '.join(open_names(facts, 'ko'))} 두 과정이 모집 중입니다. {dates_line('ko', facts, today)}\n\n입학 절차:\n1. 공개된 요건을 확인하세요: 중등교육(A2 또는 이에 준하는 학력) 졸업증명서와 성적증명서, 신분증 또는 여권 사본, 자기소개서, 학습 의지 진술서.\n2. {a['how_to_apply_url']}에 연결된 공식 구글 폼으로만 지원하세요.\n3. 공식 입학 확정 통보를 기다리고, 비용은 그 이후에만 납부하세요.\n\n관심 있는 과정과 학력(르완다 지원자인지 외국인인지도)을 알려 주시면, UAIT 요건에 비추어 어떤지 안내해 드릴게요. {ref}"),
                "sources": [src("programmes"), src("apply", a["how_to_apply_url"])]}
    if intent == "compare":
        pa, pj = (prog_name(facts, "ai", lang), prog_name(facts, "jewelry", lang))
        return {"answer": L(lang,
                f"Both are one-year certificate programmes open for the {a['intake']} intake.\n\n• {pa}: tuition USD 2,000 per year. An intensive programme on artificial intelligence, machine learning, data science, neural networks, AI application development, AI ethics and a capstone project on an African challenge. No prior coding experience is required.\n• {pj}: tuition USD 1,500 per year. Combines traditional craftsmanship with modern design: metalworking, gemology, stone setting, CAD, 3D printing, business and marketing, ethical sourcing, portfolio development and exhibitions. No prior experience is required.\n\nChoose AI Technology if you want to build technology skills; choose Jewelry Design if you want a creative, hands-on craft career. The application fee (RWF 50,000) and admission/registration fee (RWF 150,000) are the same for both. {ref}",
                f"두 과정 모두 {a['intake']}학년도에 모집 중인 1년 자격과정입니다.\n\n• {pa}: 수업료 연 2,000 USD. 인공지능, 머신러닝, 데이터 사이언스, 신경망, AI 응용 개발, AI 윤리, 아프리카의 과제를 다루는 캡스톤 프로젝트로 구성된 집중 과정입니다. 코딩 경험은 필요하지 않습니다.\n• {pj}: 수업료 연 1,500 USD. 전통 공예 기술과 현대 디자인을 결합하며 금속 가공, 보석학, 보석 세팅, CAD, 3D 프린팅, 비즈니스·마케팅, 윤리적 소싱, 포트폴리오 제작, 전시를 다룹니다. 사전 경험은 필요하지 않습니다.\n\n기술 역량을 키우고 싶다면 AI Technology, 창의적이고 손으로 하는 공예 분야 진로를 원한다면 Jewelry Design이 어울립니다. 지원비(50,000 RWF)와 입학·등록비(150,000 RWF)는 두 과정이 같습니다. {ref}"),
                "sources": [src("programmes")]}
    if intent == "programme_status":
        pid = st.programme or "ai"
        return {"answer": L(lang, f"Yes. {prog_name(facts, pid, 'en')} is open for the {a['intake']} intake. {dates_line('en', facts, today)} Apply only through the official Google Form linked from {a['how_to_apply_url']}. {ref}",
                            f"네, {prog_name(facts, pid, 'ko')} 모집이 {a['intake']}학년도에 진행 중입니다. {dates_line('ko', facts, today)} 지원은 {a['how_to_apply_url']}에 연결된 공식 구글 폼으로만 가능합니다. {ref}"),
                "sources": [src("programmes"), src("dates")]}
    if intent == "open_programs":
        return {"answer": L(lang, f"For the {a['intake']} {a['round']}, the open programmes are: {', '.join(open_names(facts, 'en'))}. {dates_line('en', facts, today)} Coming soon (not open yet): {', '.join(soon_names(facts, 'en'))}. {ref}",
                            f"{a['intake']}학년도 {a.get('round_ko', '1차 모집')}에 모집 중인 과정: {', '.join(open_names(facts, 'ko'))}. {dates_line('ko', facts, today)} 개설 예정(아직 지원 불가): {', '.join(soon_names(facts, 'ko'))}. {ref}"),
                "sources": [src("programmes"), src("coming")]}
    if intent == "deadline":
        return {"answer": L(lang, f"{dates_line('en', facts, today)} The class start date is not confirmed yet. Don't rely on older deadlines for this intake. {ref}",
                            f"{dates_line('ko', facts, today)} 개강일은 아직 확정되지 않았습니다. 이번 모집에는 이전 마감일을 기준으로 삼지 마세요. {ref}"),
                "sources": [src("dates")]}
    if intent == "apply":
        steps_en = [f"Download and read the Admission Guide from {site}.", f"Open the official application Google Form linked from {a['how_to_apply_url']}.", "Prepare the required documents in PDF format.", "Submit the application online.", "Wait for shortlisting, an interview where applicable, and official admission confirmation.", "Pay applicable fees only after official admission confirmation."]
        steps_ko = [f"{site} 에서 입학 안내서(Admission Guide)를 내려받아 읽습니다.", f"{a['how_to_apply_url']} 에 연결된 공식 지원 구글 폼을 엽니다.", "필요한 서류를 PDF로 준비합니다.", "온라인으로 제출합니다.", "서류 선발, 필요한 경우 면접, 공식 입학 확정 통보를 기다립니다.", "해당 비용은 공식 입학 확정 통보 후에만 납부합니다."]
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(steps_ko if lang == "ko" else steps_en, 1))
        tail = L(lang, "\n\nOnly applications submitted through the official Google Form are considered; walk-in and paper applications are not accepted. I can't provide the form link myself, so please take it from the official How to Apply page.",
                 "\n\n공식 구글 폼으로 제출한 지원서만 심사되며 방문 접수와 서면 지원은 받지 않습니다. 구글 폼 링크는 제가 직접 알려드릴 수 없으니 공식 '지원 방법' 페이지에서 확인하세요.")
        return {"answer": L(lang, "How to apply:\n", "지원 방법:\n") + steps + tail + "\n\n" + dates_line(lang, facts, today), "sources": [src("apply", a["how_to_apply_url"])]}
    if intent == "documents":
        return {"answer": L(lang, f"For certificate programmes, UAIT lists: the completed online application form; a self-introduction about your motivation, interests and career goals; a Statement of Learning Commitment (maximum one page); academic certificates and transcripts for secondary education (A2) or equivalent; and a copy of your national ID or passport.\n\nOptional: AI Technology applicants may add a recommendation letter and evidence of interest in technology; Jewelry Design applicants may add portfolio samples and a recommendation letter.\n\nRwandan and international applicants may have additional, different requirements listed at {a['admission_requirements_url']}. I keep those two groups separate, so please tell me which one you are or confirm with admissions. Send sensitive documents only through the official application, never in this chat. {ref}",
                            f"자격과정 지원 서류: 온라인 지원서 작성 완료본, 지원 동기·관심 분야·진로 목표를 담은 자기소개서, 학습 의지 진술서(최대 1쪽), 중등교육(A2) 또는 이에 준하는 학력의 졸업증명서와 성적증명서, 신분증 또는 여권 사본.\n\n선택 서류: AI Technology 지원자는 추천서와 기술에 대한 관심을 보여 주는 자료를, Jewelry Design 지원자는 포트폴리오와 추천서를 추가할 수 있습니다.\n\n르완다 지원자와 외국인 지원자에게는 서로 다른 추가 요건이 {a['admission_requirements_url']}에 안내되어 있습니다. 두 그룹을 구분해서 안내해 드리니 어느 쪽인지 알려 주시거나 입학처에 확인해 주세요. 민감한 서류는 이 채팅이 아니라 공식 지원 절차로만 제출하세요. {ref}"),
                "sources": [src("docs", a["admission_requirements_url"])]}
    if intent == "authorization":
        z = facts["authorization"]
        return {"answer": L(lang, f"UAIT announced {z['body']} authorization for its {z['programme']} Program on {d('en', z['announced'])}. This applies to that programme only and should not be read as a broader accreditation claim. {ref}",
                            f"UAIT는 {d('ko', z['announced'])}에 1년 단기 AI Technology 과정에 대해 르완다 TVET 위원회(Rwanda TVET Board)의 인가를 받았다고 발표했습니다. 해당 과정에만 해당하며 더 넓은 범위의 인증으로 해석해서는 안 됩니다. {ref}"),
                "sources": [src("auth")]}
    if intent == "unconfirmed":
        en, ko = UNCONFIRMED_LABELS.get(st.topic, ("that detail", "해당 정보"))
        return {"answer": L(lang, f"I can't confirm {en} from the verified UAIT information available to me, and I don't want to guess. That doesn't mean it doesn't exist at UAIT. {ref} Official announcements are also posted at {site}.",
                            f"{ko} 관련 내용은 제가 가진 확인된 UAIT 정보로는 확인할 수 없어서, 추측으로 답하고 싶지 않습니다. UAIT에 해당 항목이 없다는 뜻은 아닙니다. {ref} 공식 공지는 {site} 에서도 확인할 수 있습니다."),
                "sources": [src("unconfirmed")]}
    if intent == "assessment":
        return assessment(st, facts, ctx)
    return None


def assessment(st, facts, ctx):
    lang, a, c = st.lang, facts["admissions"], facts["contacts"]
    ref = refer(lang, facts)
    pid = st.programme
    subs = st.subjects[-3:]
    subj_txt = ", ".join(SUBJECT_NAMES[s][1 if lang == "ko" else 0] for s in subs) or L(lang, "your stated background", "말씀해 주신 배경")
    rel = " ".join(RELEVANCE[s][1 if lang == "ko" else 0] for s in subs if s in RELEVANCE)
    if pid == "jewelry":
        prog = L(lang, "Jewelry Design Certificate: a one-year programme where no prior experience is required; a portfolio of drawings or craft work is a helpful optional addition.",
                 "Jewelry Design 자격과정: 사전 경험이 필요 없는 1년 과정이며, 그림이나 공예 작품 포트폴리오는 선택으로 제출하면 도움이 됩니다.")
        prep = L(lang, "Helpful preparation: sketching, basic design and measurement skills, and a small portfolio.", "도움이 되는 준비: 스케치, 기초 디자인·측정 능력, 간단한 포트폴리오.")
    elif pid == "ai" or pid is None:
        prog = L(lang, "AI Technology Certificate: a one-year, intensive programme. Prior coding experience is not required.",
                 "AI Technology 자격과정: 1년 집중 과정이며 코딩 경험은 필요하지 않습니다.")
        prep = L(lang, "Helpful preparation: basic mathematics (algebra and statistics), basic computer skills, and one or two small projects or online courses you can show as evidence of interest.",
                 "도움이 되는 준비: 기초 수학(대수, 통계), 기본 컴퓨터 활용 능력, 관심을 보여 줄 수 있는 작은 프로젝트나 온라인 강의 한두 개.")
    missing = []
    if not st.category:
        missing.append(L(lang, "whether you are a Rwandan or an international applicant (the published requirements differ)", "르완다 지원자인지 외국인 지원자인지(공개된 요건이 서로 다릅니다)"))
    if not st.levels:
        missing.append(L(lang, "your secondary-school level or certificate (A2 or equivalent)", "중등교육 수준 또는 졸업 자격(A2 또는 이에 준하는 학력)"))
    missing.append(L(lang, "any extra items listed for your applicant category", "지원자 유형별 추가 항목"))
    ask = "" if pid else L(lang, "\n\nWhich programme are you considering: AI Technology or Jewelry Design?", "\n\n어느 과정을 고려하고 계신가요? AI Technology 또는 Jewelry Design인가요?")
    text = L(lang,
             f"I can give you an evidence-based view against UAIT's published information, but I can't make the official admission decision.\n\n• Programme: {prog}\n• Your background ({subj_txt}): {rel}\n• What UAIT asks for: secondary-school certificates and transcripts (A2 or equivalent), a national ID or passport copy, a self-introduction and a Statement of Learning Commitment; optional items include a recommendation letter and evidence of interest. Rwandan and international applicants may have additional, different requirements at {a['admission_requirements_url']}.\n• Still to check: {'; '.join(missing)}.\n• {prep}\n• Next steps: {dates_line('en', facts, ctx['today'])} Apply through the official Google Form from {a['how_to_apply_url']}. For an official eligibility decision, contact admissions at {c['admissions_email']}.{ask}",
             f"UAIT가 공개한 정보를 바탕으로 근거 있는 의견을 드릴 수는 있지만, 공식 입학 결정은 제가 내릴 수 없습니다.\n\n• 과정: {prog}\n• 배경({subj_txt}): {rel}\n• UAIT 요구 사항: 중등교육(A2 또는 이에 준하는 학력) 졸업증명서와 성적증명서, 신분증 또는 여권 사본, 자기소개서, 학습 의지 진술서. 추천서와 관심을 보여 주는 자료는 선택입니다. 르완다 지원자와 외국인 지원자에게는 {a['admission_requirements_url']}에 서로 다른 추가 요건이 있을 수 있습니다.\n• 추가 확인 필요: {'; '.join(missing)}.\n• {prep}\n• 다음 단계: {dates_line('ko', facts, ctx['today'])} {a['how_to_apply_url']}의 공식 구글 폼으로 지원하세요. 공식 자격 판단은 입학처({c['admissions_email']})에 문의하세요.{ask}")
    return {"answer": text, "sources": [src("programmes"), src("docs", a["admission_requirements_url"])]}


# ---------------------------------------------------------------------------
# Brief answers: at most three sentences, aimed at the exact question.
# ---------------------------------------------------------------------------
def ref_short(lang, facts):
    c = facts["contacts"]
    return L(lang, f"Admissions: {c['admissions_email']}, {c['phones'][0]}.", f"입학 문의: {c['admissions_email']}, {c['phones'][0]}.")


def _closed(facts, today):
    return today > dt.date.fromisoformat(facts["admissions"]["closes"])


def render_brief(intent, st, facts, ctx):
    lang, today = st.lang, ctx["today"]
    c, a, fe = facts["contacts"], facts["admissions"], facts["fees"]
    msg = ctx.get("message", "")
    rs, site = ref_short(lang, facts), facts["institution"]["website"]
    ai, jw = prog_name(facts, "ai", lang), prog_name(facts, "jewelry", lang)
    opens = f"{ai} {L(lang, 'and', '과정과')} {jw}" if lang == "ko" else f"{ai} and {jw}"
    closes_en, closes_ko = d("en", a["closes"]), d("ko", a["closes"])

    def out(text, *keys):
        return {"answer": text, "sources": [src(k, a["how_to_apply_url"] if k == "apply" else None) for k in keys]}

    if intent == "greeting":
        return out(L(lang, "Hello! I'm the UAIT Official AI Assistant, here for questions about programmes, admissions, fees and documents. What would you like to know?",
                     "안녕하세요! 저는 UAIT 공식 AI 어시스턴트입니다. 과정, 입학, 학비, 서류에 대해 물어보세요. 무엇이 궁금하신가요?"))
    if intent in ("injection", "fabricate"):
        return out(L(lang, f"I can't invent or change official UAIT information. Only {' and '.join(open_names(facts, 'en'))} are open for {a['intake']} (deadline {closes_en}), and {', '.join(soon_names(facts, 'en'))} are coming soon with no dates.",
                     f"공식 UAIT 정보를 지어내거나 바꿀 수는 없습니다. {a['intake']}학년도에는 {', '.join(open_names(facts, 'ko'))}만 모집 중이며(마감 {closes_ko}), {', '.join(soon_names(facts, 'ko'))}은(는) 개설 예정이고 일정은 없습니다."), "programmes", "coming")
    if intent == "contact":
        return out(L(lang, f"Admissions: {c['admissions_email']}; general enquiries: {c['general_email']}; phone: {c['phones'][0]} or {c['phones'][1]} ({facts['institution']['office_hours']['en']}); address: {facts['institution']['address']}.",
                     f"입학 문의: {c['admissions_email']}, 일반 문의: {c['general_email']}, 전화: {c['phones'][0]} 또는 {c['phones'][1]} ({facts['institution']['office_hours']['ko']}), 주소: {facts['institution']['address']}.") + verify_note(lang, ctx.get("conflict_topics", set()), "contact"), "contacts")
    if intent == "fees":
        only = [p for p in facts["programmes"] if p["status"] == "open" and st.programme in (None, p["id"])]
        tui = L(lang, " and ".join(f"{p['name']['en']} is USD {p['tuition_usd']:,} per year" for p in only), " 그리고 ".join(f"{p['name']['ko']}은 연 {p['tuition_usd']:,} USD" for p in only))
        q = {k: bool(re.search(v, msg, re.I)) for k, v in {
            "app": r"application fee|apply fee|지원비|지원 ?수수료", "reg": r"registration|admission fee|등록비|입학비",
            "tui": r"tuition|학비|수업료", "plan": r"payment plan|instal+ments?|분할", "late": r"late|penalty|연체",
            "rwf": r"\brwf\b|exchange|in francs|환율"}.items()}
        parts = []
        if q["app"] and not q["tui"]:
            parts.append(L(lang, f"The application fee is {rwf('en', fe['application_rwf'])} and is non-refundable.", f"지원비는 {rwf('ko', fe['application_rwf'])}이며 환불되지 않습니다."))
        elif q["reg"] and not q["tui"]:
            parts.append(L(lang, f"The admission/registration fee is {rwf('en', fe['registration_rwf'])}.", f"입학·등록비는 {rwf('ko', fe['registration_rwf'])}입니다."))
        elif q["plan"] or q["late"] or q["rwf"]:
            bits_en, bits_ko = [], []
            if q["rwf"] or not (q["plan"] or q["late"]):
                bits_en.append("USD tuition may be paid in RWF at the applicable exchange rate"); bits_ko.append("USD 수업료는 적용 환율로 RWF 납부가 가능합니다")
            if q["plan"]:
                bits_en.append("payment plans are available through admissions"); bits_ko.append("분할 납부는 입학처를 통해 가능합니다")
            if q["late"]:
                bits_en.append(f"a {fe['late_penalty_percent']}% late-payment penalty applies"); bits_ko.append(f"납부 지연 시 {fe['late_penalty_percent']}% 연체료가 있습니다")
            parts.append(L(lang, "; ".join(bits_en).capitalize() + ".", ", ".join(bits_ko) + "."))
        else:
            parts.append(L(lang, f"Tuition: {tui}.", f"수업료: {tui}입니다."))
            parts.append(L(lang, f"There is also a non-refundable application fee of {rwf('en', fe['application_rwf'])} and an admission/registration fee of {rwf('en', fe['registration_rwf'])}.",
                           f"별도로 지원비는 {rwf('ko', fe['application_rwf'])}(환불 불가), 입학·등록비는 {rwf('ko', fe['registration_rwf'])}입니다."))
        parts.append(L(lang, "All fees are payable only after official admission confirmation.", "모든 비용은 공식 입학 확정 통보 후에만 납부합니다."))
        return out(" ".join(parts) + verify_note(lang, ctx.get("conflict_topics", set()), "fees"), "fees")
    if intent == "payment_timing":
        return out(L(lang, f"No, please don't pay before official admission confirmation. This applies to the application fee, the registration fee and tuition, and paying does not guarantee admission. If a payment request seems doubtful, check with {c['admissions_email']} first.",
                     f"아니요, 공식 입학 확정 통보 전에는 납부하지 마세요. 지원비, 입학·등록비, 수업료 모두 해당되며 납부가 입학을 보장하지는 않습니다. 납부 요청이 의심스러우면 먼저 {c['admissions_email']}에 확인하세요."), "payment")
    if intent == "payment_method":
        return out(L(lang, f"The published options are {' and '.join(facts['payment']['published_methods'])}; the exact details are on the official Fees & Payments page ({a['fees_url']}), so verify them there before sending any money. Pay only after official admission confirmation.",
                     f"공개된 납부 방법은 Bank of Kigali 송금과 MTN 모바일 머니이며, 정확한 정보는 공식 수업료 및 납부 페이지({a['fees_url']})에서 송금 전에 반드시 확인(verify)하세요. 납부는 공식 입학 확정 통보 후에만 하세요."), "payment")
    if intent == "payment_done":
        return out(L(lang, f"Contact admissions right away and keep your receipt or proof of payment so they can check it. I can't verify payments or confirm admission myself. If you paid an account not shown on the official Fees & Payments page ({a['fees_url']}), also tell your bank or mobile-money provider. {rs}",
                     f"바로 입학처에 연락하시고 영수증 또는 송금 증빙을 보관하세요. 저는 납부 내역을 확인하거나 입학을 확정할 수 없습니다. 공식 수업료 및 납부 페이지({a['fees_url']})에 없는 계좌로 보내셨다면 은행이나 모바일 머니 업체에도 알려 주세요. {rs}"), "payment")
    if intent == "job_guarantee":
        return out(L(lang, "UAIT lists career support for AI Technology and past international internships for Jewelry Design, but it does not guarantee a job, salary, internship or overseas placement. No verified placement percentage is available.",
                     "UAIT는 AI Technology 과정의 취업 지원과 Jewelry Design 과정의 과거 해외 인턴십 사례를 안내하지만, 취업·급여·인턴십·해외 배치는 보장하지 않습니다. 검증된 취업률도 없습니다."), "programmes")
    if intent == "hope":
        h = c["restricted"]["hope_project"]
        return out(L(lang, f"The Hope Goat & Sheep Project is a separate university-led livestock initiative, not a certificate programme or Community Academy course. For the project only, contact {h['emails'][0]} or {h['phones'][0]}. Please don't use these contacts for admissions; use {c['admissions_email']}.",
                     f"Hope Goat & Sheep 프로젝트는 대학이 주도하는 별도의 가축 사육 사업으로, 자격과정이나 커뮤니티 아카데미 수업이 아닙니다. 프로젝트 문의만 {h['emails'][0]} 또는 {h['phones'][0]}로 하세요. 입학 문의에는 사용하지 말고 {c['admissions_email']}를 이용하세요."), "hope")
    if intent == "coming_soon":
        named = [n for n in hits(PROGRAMMES, msg) if n in ("piano", "drone", "cyber", "advdip")]
        names = [prog_name(facts, n, lang) for n in named] or soon_names(facts, lang)
        return out(L(lang, f"{', '.join(names)} {'is' if len(names) == 1 else 'are'} coming soon and not currently open for the {a['intake']} intake, with no confirmed launch date. Only {' and '.join(open_names(facts, 'en'))} accept applications now.",
                     f"{', '.join(names)}: 개설 예정 과정으로 {a['intake']}학년도에는 아직 지원할 수 없고 개설 일정도 확정되지 않았습니다. 지금은 {', '.join(open_names(facts, 'ko'))}만 지원할 수 있습니다."), "coming")
    if intent == "community":
        fee_q = re.search(r"fee|cost|how much|price|tuition|얼마|비용|수강료", msg, re.I)
        extra = L(lang, " Class fees are not published, so ask admissions for the current amount.", " 수강료는 공개되어 있지 않으니 입학처에 문의하세요.") if fee_q else ""
        return out(L(lang, f"The Community Academy offers Piano Class, Korean Language and Computer Class, and you join by contacting admissions directly, not through the certificate Google Form.{extra}",
                     f"커뮤니티 아카데미는 피아노, 한국어, 컴퓨터 수업을 운영하며, 자격과정 구글 폼이 아니라 입학처에 직접 문의해 신청합니다.{extra}"), "community")
    if intent == "join":
        if _closed(facts, today):
            return out(L(lang, f"The {a['round']} for {a['intake']} closed on {closes_en}, so please ask admissions about the next round. {rs}",
                         f"{a['intake']}학년도 {a.get('round_ko', '1차 모집')}은 {closes_ko}에 마감되었으니 다음 모집은 입학처에 문의하세요. {rs}"), "programmes", "apply")
        return out(L(lang, f"Yes, you can: {ai} and {jw} are open for the {a['intake']} intake until {closes_en}, and neither needs prior experience. Apply only through the official Google Form on {a['how_to_apply_url']}, and pay fees only after admission is confirmed. Tell me which programme and your education background (Rwandan or international) and I'll say how you fit.",
                     f"네, 가능합니다. {a['intake']}학년도에 {opens}이 {closes_ko}까지 모집 중이며 사전 경험은 필요하지 않습니다. {a['how_to_apply_url']}에 연결된 공식 구글 폼으로만 지원하고, 비용은 입학 확정 후에 납부하세요. 관심 과정과 학력(르완다/외국인)을 알려 주시면 어떻게 맞는지 말씀드릴게요."), "programmes", "apply")
    if intent == "compare":
        return out(L(lang, f"Both are one-year certificates open for {a['intake']}: {ai} (USD 2,000 per year) covers AI, machine learning and data science with no coding experience needed, while {jw} (USD 1,500 per year) covers metalworking, gemology, CAD and 3D printing. Choose AI Technology for technology skills or Jewelry Design for a creative, hands-on craft career.",
                     f"두 과정 모두 {a['intake']}학년도에 모집 중인 1년 자격과정입니다. {ai}(연 2,000 USD)은 코딩 경험 없이 AI, 머신러닝, 데이터 사이언스를 배우고, {jw}(연 1,500 USD)은 금속 가공, 보석학, CAD, 3D 프린팅을 다룹니다. 기술 역량이 목표라면 AI Technology, 창의적인 공예 진로라면 Jewelry Design을 선택하세요."), "programmes")
    if intent == "programme_status":
        pid = st.programme or "ai"
        return out(L(lang, f"Yes, {prog_name(facts, pid, 'en')} is open for the {a['intake']} intake. {dates_line('en', facts, today)} Apply only through the official Google Form on {a['how_to_apply_url']}.",
                     f"네, {prog_name(facts, pid, 'ko')} 모집이 {a['intake']}학년도에 진행 중입니다. {dates_line('ko', facts, today)} 지원은 {a['how_to_apply_url']}에 연결된 공식 구글 폼으로만 가능합니다."), "programmes", "dates")
    if intent == "open_programs":
        return out(L(lang, f"{ai} and {jw} are open for the {a['intake']} {a['round']}, with the deadline on {closes_en}. {', '.join(soon_names(facts, 'en'))} are coming soon and not open yet.",
                     f"{a['intake']}학년도 {a.get('round_ko', '1차 모집')}에는 {opens}이 모집 중이며 마감은 {closes_ko}입니다. {', '.join(soon_names(facts, 'ko'))}은(는) 개설 예정(아직 지원 불가)입니다."), "programmes", "coming")
    if intent == "deadline":
        return out(f"{dates_line(lang, facts, today)} " + L(lang, "The class start date is not confirmed yet.", "개강일은 아직 확정되지 않았습니다."), "dates")
    if intent == "apply":
        return out(L(lang, f"Download the Admission Guide from {site}, then submit your application and PDF documents through the official Google Form linked from the How to Apply page ({a['how_to_apply_url']}). Walk-in and paper applications are not accepted, and fees are paid only after official admission confirmation. {dates_line('en', facts, today)}",
                     f"{site}에서 입학 안내서를 내려받은 뒤, {a['how_to_apply_url']}에 연결된 공식 구글 폼으로 지원서와 PDF 서류를 제출하세요. 방문·서면 접수는 받지 않으며 비용은 공식 입학 확정 후에만 납부합니다. {dates_line('ko', facts, today)}"), "apply")
    if intent == "documents":
        wants_opt = re.search(r"optional|recommendation|letters?|portfolio|추천서|포트폴리오|선택", msg, re.I)
        core = L(lang, "The required documents are the online application form, a self-introduction, a one-page Statement of Learning Commitment, secondary-school (A2 or equivalent) certificates and transcripts, and a national ID or passport copy.",
                 "필수 서류는 온라인 지원서, 자기소개서, 학습 의지 진술서(1쪽), 중등교육(A2 또는 이에 준하는 학력) 졸업증명서와 성적증명서, 신분증 또는 여권 사본입니다.")
        extra_en = {"ai": "evidence of interest in technology", "jewelry": "portfolio samples"}.get(st.programme)
        extra_ko = {"ai": "기술에 대한 관심 자료", "jewelry": "포트폴리오"}.get(st.programme)
        opt = (L(lang, f"A recommendation letter is optional, as are {extra_en}.", f"추천서와 {extra_ko}는 선택 사항입니다.") if extra_en else
               L(lang, "A recommendation letter is optional, as are evidence of tech interest (AI Technology) or portfolio samples (Jewelry Design).",
                 "추천서는 선택이며, AI Technology는 기술에 대한 관심 자료, Jewelry Design은 포트폴리오를 선택으로 추가할 수 있습니다."))
        tail = L(lang, f"Rwandan and international applicants may have extra requirements at {a['admission_requirements_url']}, so tell me which you are.",
                 f"르완다/외국인 지원자는 {a['admission_requirements_url']}에 추가 요건이 있을 수 있으니 어느 쪽인지 알려 주세요.")
        return out(" ".join([opt, tail]) if wants_opt else " ".join([core, opt, tail]), "docs")
    if intent == "authorization":
        z = facts["authorization"]
        return out(L(lang, f"UAIT announced {z['body']} authorization for its {z['programme']} on {d('en', z['announced'])}. This applies to that programme only and should not be read as a broader accreditation claim.",
                     f"UAIT는 {d('ko', z['announced'])}에 1년 단기 AI Technology 과정에 대해 르완다 TVET 위원회(Rwanda TVET Board)의 인가를 받았다고 발표했습니다. 해당 과정에만 해당하며 더 넓은 범위의 인증으로 해석해서는 안 됩니다."), "auth")
    if intent == "unconfirmed":
        en, ko = UNCONFIRMED_LABELS.get(st.topic, ("that detail", "해당 정보"))
        return out(L(lang, f"I can't confirm {en} from the verified UAIT information I have, and I don't want to guess; that doesn't mean it doesn't exist. {rs}",
                     f"{ko} 관련 내용은 제가 가진 확인된 UAIT 정보로는 확인할 수 없어 추측하지 않겠습니다. UAIT에 없다는 뜻은 아닙니다. {rs}"), "unconfirmed")
    if intent == "assessment":
        return assessment_brief(st, facts, ctx)
    return None


def _first_sentence(text):
    return re.split(r"(?<=[.。])\s+", text.strip())[0] if text else ""


def assessment_brief(st, facts, ctx):
    lang, a = st.lang, facts["admissions"]
    ko = lang == "ko"
    pid = st.programme or "ai"
    name = prog_name(facts, pid, lang)
    subs = st.subjects[-3:]
    subj_txt = ", ".join(SUBJECT_NAMES[s][1 if ko else 0] for s in subs) or L(lang, "stated", "말씀하신")
    rel = _first_sentence(RELEVANCE[subs[-1]][1 if ko else 0]) if subs and subs[-1] in RELEVANCE else ""
    need = L(lang, "no prior coding experience is needed" if pid == "ai" else "no prior experience is needed and a small portfolio helps",
             "코딩 경험은 필요하지 않습니다" if pid == "ai" else "사전 경험은 필요 없고 작은 포트폴리오가 도움이 됩니다")
    s1 = L(lang, f"Your {subj_txt} background can work for the {name}, since {need}.", f"{subj_txt} 배경은 {name}에 지원하기에 무리가 없으며, {need}.")
    if st.programme is None:
        s3 = L(lang, "Tell me which programme interests you and whether you are a Rwandan or an international applicant; admissions makes the official admission decision.",
               "관심 있는 과정과 르완다 지원자인지 외국인 지원자인지 알려 주시고, 공식 입학 결정은 입학처에서 합니다.")
    elif not st.category:
        s3 = L(lang, "Tell me whether you are a Rwandan or an international applicant for the exact document list; admissions makes the official admission decision.",
               "르완다 지원자인지 외국인 지원자인지 알려 주시면 정확한 서류 목록을 안내하며, 공식 입학 결정은 입학처에서 합니다.")
    else:
        cat = {"rwandan": ("a Rwandan", "르완다"), "international": ("an international", "외국인")}[st.category]
        s3 = L(lang, f"As {cat[0]} applicant, check your extra requirements at {a['admission_requirements_url']}; admissions makes the official admission decision.",
               f"{cat[1]} 지원자는 {a['admission_requirements_url']}에서 추가 요건을 확인하시고, 공식 입학 결정은 입학처에서 합니다.")
    return {"answer": " ".join(x for x in (s1, rel, s3) if x), "sources": [src("programmes"), src("docs", a["admission_requirements_url"])]}


def render(intent, st, facts, ctx):
    """Brief (max three sentences) unless the visitor asked for detail."""
    if not ctx.get("detail"):
        r = render_brief(intent, st, facts, ctx)
        if r:
            return r
    return render_full(intent, st, facts, ctx)
