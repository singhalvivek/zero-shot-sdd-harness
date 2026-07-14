import re
import time

from google import genai
from google.genai import types

_RATE_LIMIT_BACKOFF_SECONDS = 15


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from a model response.

    Handles both a fenced block (```python ... ```) and stray leading/trailing
    fence markers. Returns the inner code, stripped.
    """
    if not text:
        return ""
    t = text.strip()
    # Prefer the contents of the first fenced block if one exists.
    m = re.search(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", t, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Otherwise strip a stray opening/closing fence.
    t = re.sub(r"^```(?:python|py)?[ \t]*\r?\n?", "", t)
    t = re.sub(r"\r?\n?```\s*$", "", t)
    return t.strip()


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "resource_exhausted" in s or "rate limit" in s


class GeminiProvider:
    """Gemini provider constructed per-run with the chosen model_id.

    The key is passed explicitly to genai.Client(api_key=...). Retries once on a
    transient 429 RESOURCE_EXHAUSTED with backoff (free-tier keys have low RPM).
    """

    DEFAULT_MODEL = "gemini-3.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise RuntimeError("AGENT_GEMINI_API_KEY is not set")
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _generate_content(self, prompt: str, config):
        try:
            return self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )
        except Exception as exc:  # noqa: BLE001 — retry only on rate limit
            if _is_rate_limit(exc):
                time.sleep(_RATE_LIMIT_BACKOFF_SECONDS)
                return self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
            raise

    def generate(self, prompt: str, *, system: str | None = None) -> dict:
        """Return the model output with usage.

        Returns {"text": <fences-stripped>, "raw": <raw>, "usage": {...}}.
        """
        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )
        response = self._generate_content(prompt, config)
        raw = response.text or ""
        return {
            "text": strip_code_fences(raw),
            "raw": raw,
            "usage": self._extract_usage(response),
        }

    @staticmethod
    def _extract_usage(response) -> dict:
        um = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(um, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(um, "candidates_token_count", 0) or 0)
        total = int(getattr(um, "total_token_count", 0) or 0)
        if not total:
            total = prompt_tokens + completion_tokens
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        }

    # Backwards-compatible plain-text call used by the generic LLMClient.
    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self.generate(prompt, system=system)["text"]
