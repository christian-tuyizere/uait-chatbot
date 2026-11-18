"""Language detection and a small Korean->English glossary used for retrieval."""
import re

HANGUL = re.compile(r"[\uac00-\ud7a3]")
LATIN = re.compile(r"[A-Za-z]")


def detect(text: str):
    """Return 'ko', 'en' or None when the text has no letters to judge by."""
    ko = len(HANGUL.findall(text))
    en = len(LATIN.findall(text))
    if ko == 0 and en == 0:
        return None
    # Korean text often contains Latin words (UAIT, AI), so Hangul wins at a low share.
    return "ko" if ko >= 2 and ko * 8 >= en else "en"


# Korean term -> English search words. Lets a Korean question find English web pages.
GLOSSARY = {
    "학비": "tuition fee", "수업료": "tuition fee", "등록금": "tuition fee registration",
    "비용": "fee cost", "입학": "admission", "지원": "apply application",
    "마감": "deadline", "서류": "documents", "과정": "program", "학과": "program",
    "프로그램": "program", "장학금": "scholarship", "연락": "contact", "문의": "contact",
    "이메일": "email", "전화": "phone", "주소": "address", "위치": "location",
    "주얼리": "jewelry", "보석": "jewelry gemology", "피아노": "piano", "한국어": "korean",
    "컴퓨터": "computer", "인공지능": "ai artificial intelligence", "졸업": "graduate",
    "취업": "job career placement", "인턴": "internship", "납부": "payment pay",
    "결제": "payment pay", "계좌": "bank account", "모바일": "mobile money", "송금": "payment transfer",
    "자격": "requirement eligibility", "요건": "requirement", "외국인": "international",
    "국제": "international", "르완다": "rwandan rwanda", "기숙사": "housing accommodation",
    "도서관": "library", "상담": "counseling", "개강": "start date classes", "인가": "authorization",
    "승인": "authorization", "교수": "faculty", "교직원": "faculty staff", "협력": "partnership",
    "파트너": "partnership", "소식": "news", "뉴스": "news", "행사": "event",
    "학생": "student", "대학": "university", "모집": "open admission intake",
}


def expand_korean(text: str) -> str:
    extra = [en for ko, en in GLOSSARY.items() if ko in text]
    return " ".join(extra)
