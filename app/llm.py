"""Provider-agnostic language model client. Swap providers with environment variables only."""
import re
import threading
import time


class LLMError(Exception):
    pass


def strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in text:
        text = text.split("<think>")[0]
    return text.strip()


PRESETS = {  # provider name -> (kind, base_url)
    "gemini": ("openai", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "groq": ("openai", "https://api.groq.com/openai/v1"),
    "openrouter": ("openai", "https://openrouter.ai/api/v1"),
}
SKIP_WORDS = ("lite", "image", "tts", "audio", "live", "embed", "vision", "robotics", "computer", "thinking", "learnlm", "gemma", "nano")


def pick_gemini_models(ids):
    """Choose usable general 'flash' models from a model list, newest and most stable first."""
    import re as _re
    out = []
    for i in ids:
        i = i.split("/")[-1]
        if "flash" in i and not any(w in i for w in SKIP_WORDS):
            out.append(i)

    def key(i):
        nums = tuple(int(n) for n in _re.findall(r"\d+", i)[:3]) or (0,)
        unstable = any(w in i for w in ("preview", "exp", "latest"))
        return (not unstable, nums)
    return sorted(set(out), key=key, reverse=True)


GROQ_SKIP = ("whisper", "guard", "tts", "orpheus", "embed", "distil", "safeguard", "compound", "vision")
GROQ_PREFER = ("gpt-oss-120b", "llama-3.3-70b", "llama-4-maverick", "qwen3-32b", "llama-4-scout", "gpt-oss-20b", "llama-3.1-8b")


def pick_groq_models(ids):
    ok = [i for i in ids if i and not any(w in i for w in GROQ_SKIP)]

    def rank(i):
        for n, p in enumerate(GROQ_PREFER):
            if p in i:
                return n
        return len(GROQ_PREFER)
    return sorted(set(ok), key=lambda i: (rank(i), i))


def explain_http(code: int, body: str = "") -> str:
    hint = {400: "the key or model name was rejected", 401: "the API key is not valid", 403: "the key is not allowed to use this model or region",
            404: "the model name was not found", 429: "the free rate limit was reached; wait a minute or lower the traffic"}.get(code, "the provider returned an error")
    return f"HTTP {code}: {hint}. {body[:160]}".strip()


class Provider:
    def __init__(self, kind, model, base_url, api_key, timeout, name=""):
        preset = PRESETS.get(kind)
        self.name = name or kind
        if preset:
            kind, base_url = preset[0], base_url or preset[1]
        self.kind, self.model, self.base_url, self.api_key, self.timeout = kind, model, (base_url or "").rstrip("/"), api_key, timeout
        self.auto = self.name in ("gemini", "groq")  # a missing model name triggers discovery of what the key can use
        self._discovered = False
        self.candidates = [model] if model else []

    def _headers(self):
        h = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        if "googleapis.com" in self.base_url:
            h["x-goog-api-key"] = self.api_key
        return h

    @property
    def ready(self):
        if self.kind == "anthropic":
            return bool(self.api_key)
        if self.kind == "openai":
            return bool(self.api_key and self.base_url and (self.model or self.auto))
        return False

    def _discover(self, httpx):
        self._discovered = True
        try:
            r = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=min(self.timeout, 10))
            r.raise_for_status()
            ids = [m.get("id", "") for m in r.json().get("data", [])]
            found = pick_groq_models(ids)[:4] if self.name == "groq" else pick_gemini_models([i for i in ids])[:3]
        except Exception:
            found = []
        if not found:  # listing failed: use well-known names instead of giving up
            found = ["openai/gpt-oss-120b", "llama-3.1-8b-instant"] if self.name == "groq" else ["gemini-2.5-flash", "gemini-2.0-flash"]
        self.candidates = found

    def complete(self, system, messages, max_tokens=900, temperature=0.3):
        import httpx  # imported lazily so the rest of the app and the tests need no network library
        try:
            if self.kind == "anthropic":
                r = httpx.post(self.base_url or "https://api.anthropic.com/v1/messages",
                               headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                               json={"model": self.model or "claude-haiku-5-5", "max_tokens": max_tokens, "temperature": temperature,
                                     "system": system, "messages": messages}, timeout=self.timeout)
                r.raise_for_status()
                return strip_thinking("".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text"))
            if self.auto and not self.candidates:
                self._discover(httpx)
            last, tried = None, set()
            queue = list(self.candidates)
            while queue:
                model = queue.pop(0)
                tried.add(model)
                r = httpx.post(f"{self.base_url}/chat/completions", headers=self._headers(),
                               json={"model": model, "max_tokens": max_tokens, "temperature": temperature,
                                     "messages": [{"role": "system", "content": system}, *messages]}, timeout=self.timeout)
                if r.status_code in (400, 404) and self.auto:
                    last = explain_http(r.status_code, r.text)
                    if model in self.candidates:
                        self.candidates.remove(model)
                    if not queue and not self._discovered:  # the named model is not available: ask the provider what is
                        self._discover(httpx)
                    queue = [m for m in self.candidates if m not in tried] if not queue else queue
                    continue
                r.raise_for_status()
                self.model = model
                text = strip_thinking(r.json()["choices"][0]["message"].get("content") or "")
                if text:
                    return text
                last = "the model returned an empty answer"
            raise LLMError(last or "no model available")
        except LLMError:
            raise
        except httpx.HTTPStatusError as e:
            raise LLMError(explain_http(e.response.status_code, e.response.text))
        except Exception as e:  # network error, timeout...
            raise LLMError(f"{type(e).__name__}: {str(e)[:140]}")


class LLM:
    """Tries the primary provider, then the fallback. Enforces a daily call cap to protect free quotas."""

    def __init__(self, settings):
        s = settings
        self.providers = [p for p in (
            Provider(s.llm_provider, s.llm_model, s.llm_base_url, s.llm_api_key, s.llm_timeout, name=s.llm_provider),
            Provider(s.llm2_provider, s.llm2_model, s.llm2_base_url, s.llm2_api_key, s.llm_timeout, name=s.llm2_provider)) if p.ready]
        self.cap, self._day, self._count, self._lock = s.daily_llm_cap, time.strftime("%Y-%m-%d"), 0, threading.Lock()
        self._down_until, self._down_msg = 0.0, ""

    @property
    def configured(self):
        return bool(self.providers)

    def _allow(self):
        with self._lock:
            today = time.strftime("%Y-%m-%d")
            if today != self._day:
                self._day, self._count = today, 0
            if self._count >= self.cap:
                return False
            self._count += 1
            return True

    def complete(self, system, messages, **kw):
        if not self.providers:
            raise LLMError("no provider configured")
        if time.time() < self._down_until:  # circuit breaker: do not make visitors wait for a model that just failed
            raise LLMError("model temporarily unavailable: " + self._down_msg)
        if not self._allow():
            raise LLMError("daily cap reached")
        last = None
        for p in self.providers:
            try:
                out = p.complete(system, messages, **kw)
                if out:
                    return out
            except LLMError as e:
                last = e
        self._down_msg = str(last)[:200] if last else "empty answer"
        self._down_until = time.time() + (20 if "429" in self._down_msg else 45)
        raise last or LLMError("empty answer")
