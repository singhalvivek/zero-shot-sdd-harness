from collections.abc import Iterator

from google import genai
from google.genai import types


class GeminiProvider:
    # Spec names "gemini-3.1-pro"; the API exposes it as a -preview id. The bare
    # "gemini-3.1-pro" returns 404 NOT_FOUND, so default to the available preview.
    DEFAULT_MODEL = "gemini-3.1-pro-preview"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _config(self, system: str | None):
        return types.GenerateContentConfig(system_instruction=system) if system else None

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config(system),
        )
        return response.text

    def call_model_with_usage(self, prompt: str, *, system: str | None = None) -> dict:
        """Return text plus prompt/completion token counts from usage_metadata."""
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config(system),
        )
        usage = getattr(response, "usage_metadata", None)
        return {
            "text": response.text or "",
            "prompt_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
            "completion_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
        }

    def stream_model(self, prompt: str, *, system: str | None = None) -> Iterator[dict]:
        """Yield {text} chunks; final chunk is {usage: {prompt_tokens, completion_tokens}}.

        Token usage is read from the last streamed chunk's usage_metadata.
        """
        stream = self._client.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=self._config(system),
        )
        prompt_tokens = 0
        completion_tokens = 0
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield {"text": text}
            usage = getattr(chunk, "usage_metadata", None)
            if usage is not None:
                prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) or prompt_tokens
                completion_tokens = (
                    int(getattr(usage, "candidates_token_count", 0) or 0) or completion_tokens
                )
        yield {"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}
