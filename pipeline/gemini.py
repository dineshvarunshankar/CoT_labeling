"""Minimal Gemini API client.

The pipeline uses one auth path: set `GEMINI_API_KEY` in the environment.
Gemini is asked to return JSON directly.
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass
class GenerationResult:
    text: str
    model: str


class GeminiClient:
    def __init__(self, model: str | None = None) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise ImportError("google-genai is not installed. Run: uv sync") from e

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Set GEMINI_API_KEY before running annotation.")

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")

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

        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                self._types.Part.from_bytes(
                    data=Path(image_path).read_bytes(),
                    mime_type=mime_type,
                ),
                prompt,
            ],
            config=self._types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_json_schema=response_json_schema,
            ),
        )

        return GenerationResult(text=(response.text or "").strip(), model=self.model)

    def generate_text(
        self,
        prompt: str,
        *,
        response_json_schema: Mapping[str, Any] | None = None,
        max_output_tokens: int = 32768,
    ) -> GenerationResult:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
                response_json_schema=response_json_schema,
            ),
        )

        return GenerationResult(text=(response.text or "").strip(), model=self.model)
