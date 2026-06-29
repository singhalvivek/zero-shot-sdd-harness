from collections.abc import Iterator

import anthropic as _sdk


class AnthropicProvider:
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk.Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _kwargs(self, prompt: str, system: str | None) -> dict:
        kwargs: dict = dict(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        return kwargs

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        msg = self._client.messages.create(**self._kwargs(prompt, system))
        return msg.content[0].text

    def call_model_with_usage(self, prompt: str, *, system: str | None = None) -> dict:
        msg = self._client.messages.create(**self._kwargs(prompt, system))
        return {
            "text": msg.content[0].text,
            "prompt_tokens": int(getattr(msg.usage, "input_tokens", 0) or 0),
            "completion_tokens": int(getattr(msg.usage, "output_tokens", 0) or 0),
        }

    def stream_model(self, prompt: str, *, system: str | None = None) -> Iterator[dict]:
        prompt_tokens = 0
        completion_tokens = 0
        with self._client.messages.stream(**self._kwargs(prompt, system)) as stream:
            for text in stream.text_stream:
                if text:
                    yield {"text": text}
            final = stream.get_final_message()
            prompt_tokens = int(getattr(final.usage, "input_tokens", 0) or 0)
            completion_tokens = int(getattr(final.usage, "output_tokens", 0) or 0)
        yield {"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}
