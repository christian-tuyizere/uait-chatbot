"""Monitors the public UAIT website and keeps the stored pages up to date.

Design rules (from the project spec):
* only public pages on the allowed host are fetched, and robots.txt is respected;
* a broken link, a timeout or a server error is NEVER treated as a policy change;
* a page is only marked removed after repeated definite 404/410 answers;
* a page whose text suddenly collapses is treated as a technical glitch and ignored;
* new, changed and removed pages are logged, with version history in the store;
* facts that disagree with the owner-approved facts are recorded as conflicts.
"""
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\+?\s?250[\s\-]?\d[\d\s\-]{7,12}\d")
USD = re.compile(r"(?:USD|US\$|\$)\s?([\d][\d,]*)", re.I)
RWF = re.compile(r"(?:RWF|FRW)\s?([\d][\d,]*)|([\d][\d,]*)\s?(?:RWF|FRW)", re.I)


class _Extractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "head", "footer"}
    BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "tr", "section", "article", "footer", "header"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.title, self._skip, self._in_title = [], [], "", 0, False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP and tag != "head":
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and tag != "head" and self._skip:
            self._skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def parse_html(html: str):
    p = _Extractor()
    p.feed(html)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.parts))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return p.title.strip(), text, p.links


def default_fetch(url: str, timeout: int, user_agent: str):
    """Return (status, content_type, body). Never raises for HTTP errors."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
            return r.status, r.headers.get_content_type(), body
    except urllib.error.HTTPError as e:
        return e.code, "", ""


def default_pdf_text(url: str, timeout: int, user_agent: str):
    """Download a PDF and return its text, or None if pypdf is missing or anything fails."""
    try:
        import io
        from pypdf import PdfReader
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(15_000_000)
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
        return re.sub(r"[ \t]+", " ", text).strip() or None
    except Exception:
        return None


def _norm(url: str) -> str:
    url = urldefrag(url)[0].replace("://www.", "://", 1)  # www and non-www are the same page
    return url[:-1] if url.endswith("/") and urlparse(url).path not in ("", "/") else url


def _ok_link(url: str, host: str) -> bool:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not (u.hostname or "").endswith(host):
        return False
    return not re.search(r"\.(pdf|jpe?g|png|gif|webp|svg|zip|docx?|xlsx?|pptx?|mp4|mp3|css|js)$", u.path, re.I)


def crawl(store, cfg: dict, fetch=None, sleep=time.sleep, pdf_text=None):
    """Run one monitoring pass. `fetch(url) -> (status, content_type, body)` can be injected for tests."""
    host = cfg["allowed_host"]
    ua = cfg.get("user_agent", "UAITAssistantBot/1.0")
    fetch = fetch or (lambda u: default_fetch(u, cfg.get("timeout_seconds", 20), ua))
    robots = urllib.robotparser.RobotFileParser()
    try:
        status, _, body = fetch(f"https://{host}/robots.txt")
        robots.parse(body.splitlines() if status == 200 else [])
    except Exception:
        robots.parse([])
    queue = [_norm(u) for u in cfg["seeds"]] + [u for u in store.active_urls()]
    seen, result = set(), {"new": [], "changed": [], "removed": [], "errors": [], "suspicious": [], "unchanged": 0}
    while queue and len(seen) < cfg.get("max_pages", 60):
        url = _norm(queue.pop(0))
        if url in seen:
            continue
        seen.add(url)
        if not robots.can_fetch(ua, url):
            continue
        try:
            status, ctype, body = fetch(url)
        except Exception as e:  # network trouble: not a content change
            result["errors"].append(f"{url}: {type(e).__name__}")
            store.note_error(url)
            continue
        if status in (404, 410):
            if store.get_page(url) and store.note_missing(url, cfg.get("removal_after_missing_checks", 3)):
                result["removed"].append(url)
            continue
        if status != 200 or "html" not in (ctype or "html"):
            result["errors"].append(f"{url}: HTTP {status}")
            store.note_error(url)
            continue
        title, text, links = parse_html(body)
        old = store.get_page(url)
        if len(text) < cfg.get("min_text_chars", 200):
            result["suspicious"].append(f"{url}: too little text")
            continue
        if old and old["status"] == "active" and len(text) < cfg.get("suspicious_shrink_ratio", 0.3) * len(old["text"]):
            result["suspicious"].append(f"{url}: text shrank sharply, kept the previous version")
            store.touch(url)
            continue
        outcome = store.save_page(url, title or url, text)
        if outcome == "unchanged":
            result["unchanged"] += 1
        else:
            result[outcome].append(url)
        for href in links:
            nxt = _norm(urljoin(url, href))
            if _ok_link(nxt, host) and nxt not in seen:
                queue.append(nxt)
        sleep(cfg.get("delay_seconds", 0))
    # The official admission-guide PDF(s): only when text can be extracted (pypdf installed) and the site allows it.
    pdf_text = pdf_text or (lambda u: default_pdf_text(u, cfg.get("timeout_seconds", 20) * 2, ua)) if cfg.get("pdf_urls") else None
    for purl in cfg.get("pdf_urls", []) if pdf_text else []:
        if not robots.can_fetch(ua, purl):
            continue
        try:
            text = pdf_text(purl)
        except Exception:
            text = None
        if not text or len(text) < cfg.get("min_text_chars", 200):
            result["errors"].append(f"{purl}: PDF text not available")
            continue
        old = store.get_page(purl)
        if old and old["status"] == "active" and len(text) < cfg.get("suspicious_shrink_ratio", 0.3) * len(old["text"]):
            result["suspicious"].append(f"{purl}: PDF text shrank sharply, kept the previous version")
            continue
        outcome = store.save_page(purl, "UAIT Admission Guide (PDF)", text)
        if outcome == "unchanged":
            result["unchanged"] += 1
        else:
            result[outcome].append(purl)
    return result


def detect_conflicts(pages, facts: dict):
    """Compare published pages with the owner-approved facts. Disagreements are reported, never auto-resolved."""
    c = facts["contacts"]
    known_emails = {c["general_email"].lower(), c["admissions_email"].lower()}
    known_phones = {re.sub(r"\D", "", p) for p in c["phones"]}
    known_usd = {p["tuition_usd"] for p in facts["programmes"] if p.get("tuition_usd")}
    known_rwf = {facts["fees"]["application_rwf"], facts["fees"]["registration_rwf"]}
    out = []
    for pg in pages:
        text, url = pg["text"], pg["url"]
        for e in {m.lower() for m in EMAIL.findall(text)}:
            if e.endswith("@uait.ac.rw") and e not in known_emails:
                out.append({"topic": "contact", "severity": "high", "url": url,
                            "detail": f"Page shows {e}; approved facts list {c['admissions_email']} and {c['general_email']}."})
        for ph in {re.sub(r"\D", "", m) for m in PHONE.findall(text)}:
            if ph not in known_phones:
                out.append({"topic": "contact", "severity": "high", "url": url,
                            "detail": f"Page shows phone digits {ph} that are not in the approved facts."})
        low = text.lower()
        if "tuition" in low:
            found = {int(m.replace(",", "")) for m in USD.findall(text) if m.replace(",", "").isdigit()}
            extra = sorted(found - known_usd)
            if extra:
                out.append({"topic": "fees", "severity": "medium", "url": url,
                            "detail": f"USD amounts on a tuition page not in approved facts: {extra}"})
        if "application fee" in low or "registration" in low:
            found = set()
            for a, b in RWF.findall(text):
                v = (a or b).replace(",", "")
                if v.isdigit():
                    found.add(int(v))
            extra = sorted(found - known_rwf)
            if extra:
                out.append({"topic": "fees", "severity": "medium", "url": url,
                            "detail": f"RWF amounts not in approved facts: {extra}"})
    return out
