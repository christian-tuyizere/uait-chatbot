"""Small dependency-free BM25 search that works for English and Korean."""
import difflib
import math
import re
from collections import Counter, defaultdict

from .lang import expand_korean

STOP = set("""a an the is are was were be been of to in on at for and or but do does did can could would
should i you we it this that with as by from about me my your our what how when where which who whom
please tell am if so not no yes there their they them has have had will may might also than then about many much some any""".split())
LATIN_WORD = re.compile(r"[a-z0-9]+")
HANGUL_RUN = re.compile(r"[\uac00-\ud7a3]+")
NORMALISE = {"course": "program", "courses": "program", "certificate": "program", "programme": "program", "programmes": "program", "jewellery": "jewelry", "apply": "appli",
             "applying": "appli", "applied": "appli", "application": "appli", "applications": "appli",
             "applicant": "appli", "applicants": "appli"}


# Slang, text-speak and common misspellings, fixed before matching.
ABBREV = {"yrs": "years", "yr": "year", "mths": "months", "mnths": "months", "hw": "how", "wat": "what", "wht": "what", "wen": "when", "abt": "about", "pls": "please",
          "plz": "please", "u": "you", "ur": "your", "r": "are", "cource": "course", "cources": "courses", "progam": "program", "progams": "programs", "pogram": "program",
          "prog": "program", "uni": "university", "req": "requirements", "reqs": "requirements", "docs": "documents", "doc": "document", "appli": "apply", "adm": "admission",
          "admision": "admission", "admissions": "admission", "fee's": "fees", "jewelery": "jewelry", "jewellry": "jewelry", "juwelry": "jewelry", "tution": "tuition", "tuiton": "tuition"}
# Words that mean the same thing for search purposes (added to the query, never shown).
SYNONYMS = {"long": ["duration", "year", "month"], "duration": ["year", "month", "long"], "year": ["duration", "month", "long"], "month": ["duration", "year"],
            "cost": ["fee", "tuition"], "price": ["fee", "tuition"], "cheap": ["fee"], "pay": ["fee"], "job": ["career"], "work": ["career"], "employ": ["career"],
            "teacher": ["faculty"], "lecturer": ["faculty"], "professor": ["faculty"], "begin": ["start"], "enrol": ["appli", "join"], "register": ["appli"],
            "eligible": ["requirement"], "qualify": ["requirement"], "need": ["requirement", "document"], "paper": ["document"], "age": ["requirement"],
            "hostel": ["housing"], "dorm": ["housing"], "stay": ["housing"], "certificate": ["program"], "degree": ["program", "diploma"]}


def _stem(w: str) -> str:
    w = NORMALISE.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def tokenize(text: str):
    text = text.lower()
    toks = [_stem(w) for w in (ABBREV.get(x, x) for x in LATIN_WORD.findall(text)) if w not in STOP and len(w) > 1]
    for run in HANGUL_RUN.findall(text):
        if len(run) == 1:
            toks.append(run)
            continue
        toks.append(run)
        toks.extend(run[i:i + 2] for i in range(len(run) - 1))
    return toks


class Index:
    def __init__(self, docs):
        """docs: list of dicts with at least id, title, text, source ('seed'|'web')."""
        self.docs = docs
        self.k1, self.b = 1.5, 0.75
        self.tf = []
        self.df = defaultdict(int)
        for d in docs:
            head = (d.get("title", "") + " ") * 2 + " ".join(d.get("keywords", [])) + " "
            counts = Counter(tokenize(head + d["text"]))
            self.tf.append(counts)
            for t in counts:
                self.df[t] += 1
        self.words = {w for d in docs for w in re.findall(r"[a-z]{4,}", (d.get("title", "") + " " + d["text"] + " " + " ".join(d.get("keywords", []))).lower())}
        self.lengths = [sum(c.values()) for c in self.tf]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0

    def fix_typos(self, text: str) -> str:
        """Fix slang and near-miss spellings against the words UAIT's own knowledge uses ('yrs' -> 'years', 'progam' -> 'program')."""
        def fix(m):
            w = m.group(0)
            low = w.lower()
            if low in ABBREV:
                return ABBREV[low]
            if len(low) < 5 or low in self.words or low in STOP:
                return w
            near = difflib.get_close_matches(low, [x for x in self.words if x[0] == low[0] and abs(len(x) - len(low)) <= 2], n=1, cutoff=0.9)  # strict: a real word like "rector" must not become "director"
            return near[0] if near else w
        return re.sub(r"[A-Za-z']+", fix, text)

    def search(self, query: str, k: int = 5, source=None):
        q = tokenize(self.fix_typos(query) + " " + expand_korean(query))
        q = q + [x for t in q for x in SYNONYMS.get(t, [])]
        if not q or not self.docs:
            return []
        n = len(self.docs)
        scored = []
        for i, d in enumerate(self.docs):
            if source and d.get("source") != source:
                continue
            c, score = self.tf[i], 0.0
            for t in set(q):
                f = c.get(t)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg))
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [dict(d, score=round(s, 3)) for s, d in scored[:k]]
