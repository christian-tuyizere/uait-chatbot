"""Output verifier: blocks invented contact details, money amounts, account numbers and links.

A language model answer is only shown if every email, phone number, amount, long number,
USSD code and URL it contains is either in the owner-approved facts or in the sources that
were given to the model for this question.
"""
import re

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\+?\d[\d\s\-().]{7,}\d")
MONEY_A = re.compile(r"(USD|US\$|\$|RWF|FRW)\s?(\d[\d,]*(?:\.\d+)?)", re.I)
MONEY_B = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s?(USD|RWF|FRW)\b", re.I)
LONGNUM = re.compile(r"(?<![\d,.])\d{8,}(?![\d])")
USSD = re.compile(r"\*\d[\d*#]*#")
URL = re.compile(r"https?://[^\s)\]>\"']+")


def _cur(c):
    c = c.upper()
    return "USD" if c in ("USD", "US$", "$") else "RWF"


def _amounts(text):
    out = set()
    for cur, num in MONEY_A.findall(text):
        out.add((_cur(cur), num.replace(",", "").rstrip(".")))
    for num, cur in MONEY_B.findall(text):
        out.add((_cur(cur), num.replace(",", "").rstrip(".")))
    return out


def _digits(s):
    return re.sub(r"\D", "", s)


def build_allowed(facts, context_text: str, known_urls, intent: str):
    c = facts["contacts"]
    emails = {c["general_email"].lower(), c["admissions_email"].lower()}
    phones = {_digits(p) for p in c["phones"]}
    amounts = {("USD", str(p["tuition_usd"])) for p in facts["programmes"] if p.get("tuition_usd")}
    amounts |= {("RWF", str(facts["fees"]["application_rwf"])), ("RWF", str(facts["fees"]["registration_rwf"]))}
    urls = {u.rstrip("/") for u in known_urls} | {facts["institution"]["website"].rstrip("/")}
    urls |= {v.rstrip("/") for k, v in facts["admissions"].items() if k.endswith("_url")}
    restricted_e = {e.lower() for r in c["restricted"].values() for e in r["emails"]}
    restricted_p = {_digits(p) for r in c["restricted"].values() for p in r["phones"]}
    deprecated = {e.lower() for e in c["deprecated_emails"]}
    # What the model was shown for this question is also allowed (except deprecated addresses).
    emails |= {e.lower() for e in EMAIL.findall(context_text)} - deprecated
    phones |= {_digits(p) for p in PHONE.findall(context_text) if len(_digits(p)) >= 9}
    amounts |= _amounts(context_text)
    urls |= {u.rstrip("/.,;") for u in URL.findall(context_text)}
    nums = set(re.findall(r"\d{8,}", context_text.replace(" ", "")))
    ussd = set(USSD.findall(context_text))
    if intent == "hope":
        emails |= restricted_e
        phones |= restricted_p
        restricted_e = restricted_p = set()
    return {"emails": emails, "phones": phones, "amounts": amounts, "urls": urls, "nums": nums, "ussd": ussd,
            "restricted_e": restricted_e, "restricted_p": restricted_p, "deprecated": deprecated}


def violations(answer: str, allowed: dict):
    bad = []
    for e in {x.lower() for x in EMAIL.findall(answer)}:
        if e in allowed["deprecated"] or e in allowed["restricted_e"] or e not in allowed["emails"]:
            bad.append(f"email:{e}")
    for p in PHONE.findall(answer):
        dg = _digits(p)
        if len(dg) < 9:
            continue
        if dg in allowed["restricted_p"] or not any(dg in a or a in dg for a in allowed["phones"]):
            bad.append(f"phone:{dg}")
    for a in _amounts(answer):
        if a not in allowed["amounts"]:
            bad.append(f"amount:{a[0]} {a[1]}")
    flat = answer.replace(" ", "")
    for n in LONGNUM.findall(answer):
        if n not in allowed["nums"] and not any(n in _digits(p) for p in allowed["phones"]):
            bad.append(f"number:{n}")
    for u in USSD.findall(flat):
        if u not in allowed["ussd"]:
            bad.append(f"ussd:{u}")
    for u in URL.findall(answer):
        u = u.rstrip("/.,;:")
        if u not in allowed["urls"]:
            bad.append(f"url:{u}")
    return bad


def redact(answer: str, allowed: dict):
    """Drop only the sentences that carry unverified details; keep the rest of the answer."""
    import re as _re
    lines = []
    for line in answer.strip().split("\n"):
        parts = _re.split(r"(?<=[.!?])\s+", line)
        kept = [x for x in parts if x and not violations(x, allowed)]
        lines.append(" ".join(kept).strip())
    return "\n".join(lines).strip()
