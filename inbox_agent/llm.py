"""The only place that talks to a model.

Everything else takes an `llm` object with one method, `complete(prompt, max_tokens)`,
so the tests and the demo can pass a scripted one and need no key.
"""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Reply:
    text: str
    truncated: bool = False  # the model stopped at max_tokens, so the text is cut off


class ChatAPI:
    """Any OpenAI-compatible /chat/completions endpoint (OpenAI, Gemini, Groq, Ollama...)."""

    def __init__(self, base_url, api_key, model, timeout=60, retries=4):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key, self.model, self.timeout, self.retries = api_key, model, timeout, retries

    def complete(self, prompt, max_tokens=600):
        # Free tiers allow a few requests a minute. A 429 or a 5xx means "wait", not "wrong".
        for attempt in range(self.retries + 1):
            try:
                return self._call(prompt, max_tokens)
            except urllib.error.HTTPError as err:
                if attempt == self.retries or not (err.code == 429 or err.code >= 500):
                    raise
                wait = err.headers.get("Retry-After", "")
                time.sleep(float(wait) if wait.isdigit() else 5 * 2 ** attempt)

    def _call(self, prompt, max_tokens):
        body = json.dumps({
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        request = urllib.request.Request(self.url, data=body, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "llm-inbox-agent/0.1",
        })
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            choice = json.load(response)["choices"][0]
        return Reply(choice["message"].get("content") or "", choice.get("finish_reason") == "length")


def from_env(path=".env"):
    """A ChatAPI built from LLM_BASE_URL, LLM_API_KEY and LLM_MODEL, or None when no key is set."""
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())
    if not os.environ.get("LLM_API_KEY"):
        return None
    return ChatAPI(os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
                   os.environ["LLM_API_KEY"],
                   os.environ.get("LLM_MODEL", "gpt-4o-mini"))


class Scripted:
    """A fake model for tests and the demo. `answer(prompt)` returns a str or a Reply."""

    def __init__(self, answer):
        self.answer = answer
        self.prompts = []

    def complete(self, prompt, max_tokens=600):
        self.prompts.append(prompt)
        out = self.answer(prompt)
        return out if isinstance(out, Reply) else Reply(out)
