"""Minimal LLM API client (CMU AI Gateway / OpenAI-compatible).

Auth: set ``CMU_GATEWAY_API_KEY`` in the environment.
The gateway exposes an OpenAI-compatible endpoint that routes to Gemini.
Structured JSON output is enforced via ``response_format`` which LiteLLM
translates to Gemini's native ``responseJsonSchema``.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_BASE_URL = "https://ai-gateway.andrew.cmu.edu/v1"
_DEFAULT_MODEL = "gemini/gemini-3.1-pro-preview"


@dataclass
class GenerationResult:
    text: str
    model: str


class GeminiClient:
    def __init__(self, model: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("openai is not installed. Run: uv sync") from e

        api_key = os.environ.get("CMU_GATEWAY_API_KEY")
        if not api_key:
            raise RuntimeError("Set CMU_GATEWAY_API_KEY before running annotation.")

        self._client = OpenAI(api_key=api_key, base_url=_BASE_URL)
        self.model = model or os.environ.get("LLM_MODEL", _DEFAULT_MODEL)

    def generate(
        self,
        prompt: str,
        image_path: Path,
        *,
        response_json_schema: Mapping[str, Any] | None = None,
    ) -> GenerationResult:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if mime_type is None:
            mime_type = "image/jpeg"

        image_data = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
        data_url = f"data:{mime_type};base64,{image_data}"

        response_format: dict[str, Any] = {"type": "json_object"}
        if response_json_schema is not None:
            response_format["response_schema"] = response_json_schema

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            temperature=0.2,
            max_tokens=8192,
            response_format=response_format,
        )

        text = (response.choices[0].message.content or "").strip()
        return GenerationResult(text=text, model=self.model)

    def generate_text(
        self,
        prompt: str,
        *,
        response_json_schema: Mapping[str, Any] | None = None,
        max_output_tokens: int = 8192,
    ) -> GenerationResult:
        response_format: dict[str, Any] = {"type": "json_object"}
        if response_json_schema is not None:
            response_format["response_schema"] = response_json_schema

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_output_tokens,
            response_format=response_format,
        )

        text = (response.choices[0].message.content or "").strip()
        return GenerationResult(text=text, model=self.model)
