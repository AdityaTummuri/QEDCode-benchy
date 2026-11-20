"""Model clients for experiments.

Both conditions talk to the model through the same `MeteredClient` wrapper around the same
underlying QEDCode `ModelClient`, so usage is counted the same way and the same time limit applies.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

CHARS_PER_TOKEN = 3.5  # same rough estimate QEDCode uses; reported as "estimated" everywhere


class DeadlineExceeded(RuntimeError):
    """The condition used up its time limit."""


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens_est: int = 0
    completion_tokens_est: int = 0
    by_tag: dict[str, int] = field(default_factory=dict)

    @property
    def total_tokens_est(self) -> int:
        return self.prompt_tokens_est + self.completion_tokens_est


class MeteredClient:
    """Wraps a ModelClient: counts calls and estimated tokens, and enforces a deadline.

    The deadline is checked before each call and on every streamed token, so a slow model is cut
    off the same way in both conditions.
    """

    def __init__(self, inner, deadline: float | None = None) -> None:
        self.inner = inner
        self.name = inner.name
        self.context_tokens = inner.context_tokens
        self.deadline = deadline
        self.usage = Usage()
        self.transcript: list[dict] = []  # tag, temperature, prompt, reply (kept for local logs)

    def _check(self) -> None:
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise DeadlineExceeded("time limit reached")

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
        on_token: Callable[[str], None] | None = None,
        tag: str = "",
    ) -> str:
        self._check()

        def token_hook(piece: str) -> None:
            self._check()
            if on_token is not None:
                on_token(piece)

        reply = self.inner.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            on_token=token_hook,
            tag=tag,
        )
        prompt = "\n".join(str(m.get("content", "")) for m in messages)
        self.usage.calls += 1
        self.usage.prompt_tokens_est += estimate_tokens(prompt)
        self.usage.completion_tokens_est += estimate_tokens(reply)
        self.usage.by_tag[tag or "untagged"] = self.usage.by_tag.get(tag or "untagged", 0) + 1
        self.transcript.append(
            {"tag": tag, "temperature": temperature, "prompt": prompt, "reply": reply}
        )
        self._check()
        return reply

    def health(self) -> bool:
        return self.inner.health()

    def unload(self) -> None:  # the experiment owns the model's lifetime, not a condition
        pass


@dataclass
class ModelSpec:
    """How the user asked for a model, and what we can say about it publicly."""

    spec: str
    backend: str
    model: str
    scripted: bool = False  # True = not a real model; results are a pipeline self-test only


def make_model(spec: str):
    """Build (client, ModelSpec) from a model spec.

    qedcode            the main model from ~/.qedcode/config.toml (what `qed` itself uses)
    ollama:<name>      a model served by Ollama, e.g. ollama:qwen3:4b
    openai:<url>#<m>   any OpenAI-compatible server, e.g. openai:http://127.0.0.1:1234/v1#qwen
    scripted:oracle    a scripted stand-in that replays reference fixes (self-test only)
    scripted:broken    a scripted stand-in whose fixes are wrong (self-test only)
    """
    from qedcode.runtime.client import ModelError

    kind, _, rest = spec.partition(":")
    if kind == "qedcode" and not rest:
        from qedcode.config import load_global
        from qedcode.runtime.client import make_client

        cfg = load_global()
        client = make_client(cfg, "main")
        backend = "cloud" if cfg.engine.mode.value == "cloud" else cfg.local.backend
        return client, ModelSpec(spec, backend, client.name)
    if kind == "ollama" and rest:
        from qedcode.runtime.client import ollama_base_url
        from qedcode.runtime.ollama import OllamaClient

        client = OllamaClient(model=rest, base_url=ollama_base_url(), ctx=16384)
        return client, ModelSpec(spec, "ollama", rest)
    if kind == "openai" and "#" in rest:
        from qedcode.runtime.openai_compat import OpenAICompatClient

        url, _, model = rest.rpartition("#")
        client = OpenAICompatClient(model=model, base_url=url, ctx=16384)
        return client, ModelSpec(f"openai:<local server>#{model}", "openai_compat", model)
    if kind == "scripted" and rest in ("oracle", "broken"):
        from benchy.runner.scripted import ScriptedModel

        client = ScriptedModel(mode=rest)
        return client, ModelSpec(spec, "scripted", f"scripted-{rest}", scripted=True)
    raise ModelError(
        f"Benchy does not understand the model '{spec}'. Use qedcode (your QEDCode setup), "
        "ollama:<model>, openai:<base url>#<model>, or scripted:oracle for a self-test."
    )
