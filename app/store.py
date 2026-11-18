"""SQLite storage for crawled pages, version history, conflicts and crawl logs."""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages(
  url TEXT PRIMARY KEY, title TEXT, text TEXT, content_hash TEXT,
  first_seen REAL, last_fetched REAL, last_changed REAL, version INTEGER DEFAULT 1,
  status TEXT DEFAULT 'active', missing_checks INTEGER DEFAULT 0, error_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS page_versions(
  url TEXT, version INTEGER, content_hash TEXT, text TEXT, fetched_at REAL,
  PRIMARY KEY(url, version));
CREATE TABLE IF NOT EXISTS conflicts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, severity TEXT, detail TEXT,
  url TEXT, detected_at REAL);
CREATE TABLE IF NOT EXISTS crawl_log(ts REAL, summary TEXT);
"""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: str):
        self.path = path
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---- pages ----
    def get_page(self, url):
        with self.conn() as c:
            r = c.execute("SELECT * FROM pages WHERE url=?", (url,)).fetchone()
            return dict(r) if r else None

    def active_urls(self):
        with self.conn() as c:
            return [r["url"] for r in c.execute("SELECT url FROM pages WHERE status='active'")]

    def active_pages(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM pages WHERE status='active'")]

    def save_page(self, url, title, text, now=None):
        """Insert or update. Returns 'new', 'changed' or 'unchanged'."""
        now = now or time.time()
        h = sha(text)
        old = self.get_page(url)
        with self.conn() as c:
            if not old:
                c.execute("INSERT INTO pages(url,title,text,content_hash,first_seen,last_fetched,last_changed,version) VALUES(?,?,?,?,?,?,?,1)",
                          (url, title, text, h, now, now, now))
                c.execute("INSERT INTO page_versions VALUES(?,?,?,?,?)", (url, 1, h, text, now))
                return "new"
            if old["content_hash"] == h and old["status"] == "active":
                c.execute("UPDATE pages SET last_fetched=?, missing_checks=0, error_count=0 WHERE url=?", (now, url))
                return "unchanged"
            v = old["version"] + 1
            c.execute("UPDATE pages SET title=?,text=?,content_hash=?,last_fetched=?,last_changed=?,version=?,status='active',missing_checks=0,error_count=0 WHERE url=?",
                      (title, text, h, now, now, v, url))
            c.execute("INSERT INTO page_versions VALUES(?,?,?,?,?)", (url, v, h, text, now))
            c.execute("DELETE FROM page_versions WHERE url=? AND version<=?", (url, v - 20))
            return "changed"

    def note_error(self, url):
        with self.conn() as c:
            c.execute("UPDATE pages SET error_count=error_count+1 WHERE url=?", (url,))

    def note_missing(self, url, threshold):
        """A definite 404/410. Only after `threshold` consecutive misses is the page marked removed."""
        with self.conn() as c:
            c.execute("UPDATE pages SET missing_checks=missing_checks+1 WHERE url=?", (url,))
            r = c.execute("SELECT missing_checks FROM pages WHERE url=?", (url,)).fetchone()
            if r and r["missing_checks"] >= threshold:
                c.execute("UPDATE pages SET status='removed' WHERE url=?", (url,))
                return True
        return False

    def touch(self, url, now=None):
        with self.conn() as c:
            c.execute("UPDATE pages SET last_fetched=? WHERE url=?", (now or time.time(), url))

    # ---- conflicts & logs ----
    def replace_conflicts(self, items):
        with self.conn() as c:
            c.execute("DELETE FROM conflicts")
            for i in items:
                c.execute("INSERT INTO conflicts(topic,severity,detail,url,detected_at) VALUES(?,?,?,?,?)",
                          (i["topic"], i["severity"], i["detail"], i.get("url"), time.time()))

    def conflicts(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM conflicts ORDER BY id")]

    def conflict_topics(self):
        return {c["topic"] for c in self.conflicts()}

    def log_crawl(self, summary: dict):
        with self.conn() as c:
            c.execute("INSERT INTO crawl_log VALUES(?,?)", (time.time(), json.dumps(summary)))

    def last_crawl(self):
        with self.conn() as c:
            r = c.execute("SELECT * FROM crawl_log ORDER BY ts DESC LIMIT 1").fetchone()
            return {"ts": r["ts"], **json.loads(r["summary"])} if r else None
