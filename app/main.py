"""FastAPI server: chat API, static frontend, status, and protected admin endpoints."""
import hmac
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .assistant import Assistant
from .config import STATIC_DIR, settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uait")
assistant = Assistant()


def _crawl_loop():
    time.sleep(5)
    while True:
        try:
            r = assistant.run_crawl()
            log.info("Website check done: new=%d changed=%d removed=%d errors=%d", len(r["new"]), len(r["changed"]), len(r["removed"]), len(r["errors"]))
        except Exception:
            log.exception("Website check failed; the previous knowledge stays in use")
        time.sleep(max(1, settings.crawl_interval_hours) * 3600)


@asynccontextmanager
async def lifespan(app):
    if assistant.llm.configured:
        log.info("AI model: CONNECTED (%s). Smart answers are on.", ", ".join(p.name for p in assistant.llm.providers))
    else:
        log.warning("AI model: OFF. Open the .env file, paste your key after LLM_API_KEY=, and restart. The assistant still answers from verified facts.")
    if settings.crawl_on_start:
        threading.Thread(target=_crawl_loop, daemon=True).start()
    yield


app = FastAPI(title="UAIT Official AI Assistant", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class Turn(BaseModel):
    role: str
    content: str = Field(max_length=3000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: List[Turn] = []
    lang: Optional[str] = None


_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def _limited(ip: str) -> bool:
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return True
        q.append(now)
        if len(_hits) > 5000:
            for k in [k for k, v in _hits.items() if not v][:1000]:
                _hits.pop(k, None)
    return False


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/status")
def status():
    s = assistant.status()
    return {"last_crawl": s["last_crawl"], "pages": s["pages"], "facts_as_of": s["facts_as_of"], "smart": s["model_configured"], "ai_busy": s["ai_busy"], "last_error": (s["last_llm_error"] or "")[:160]}


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?"))
    if _limited(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute.")
    msg = req.message.strip()
    if not msg or len(msg) > settings.max_message_chars:
        raise HTTPException(status_code=400, detail="Message is empty or too long.")
    history = [t.model_dump() for t in req.history[-12:]]
    return assistant.respond(msg, history, req.lang)


def _admin(token: Optional[str]):
    if not settings.admin_token or not token or not hmac.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/admin/recrawl")
def recrawl(x_admin_token: Optional[str] = Header(default=None)):
    _admin(x_admin_token)
    r = assistant.run_crawl()
    return {k: (v if isinstance(v, int) else v[:20]) for k, v in r.items()}


@app.get("/admin/report")
def report(x_admin_token: Optional[str] = Header(default=None)):
    _admin(x_admin_token)
    return {"status": assistant.status(), "conflicts": assistant.store.conflicts(),
            "owner_confirmation_needed": assistant.facts["owner_confirmation_needed"]}
