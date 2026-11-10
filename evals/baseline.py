"""Capture the required same-model, no-tools, no-system-prompt comparison."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import litellm


class BaselineCaptureError(ValueError):
    """The baseline model call failed or returned no text."""


def capture_no_tools_baseline(
    *,
    case_id: str,
    question: str,
    model: str,
    vertex_location: str,
    completion: Callable[..., Any] = litellm.completion,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Call the production model with exactly one user message and no tools/system."""

    try:
        reply = completion(
            model=model,
            vertex_location=vertex_location,
            messages=[{"role": "user", "content": question}],
        )
        content = reply.choices[0].message.content
    except Exception as error:
        raise BaselineCaptureError("baseline model call failed safely") from error
    if not isinstance(content, str) or not content.strip():
        raise BaselineCaptureError("baseline model returned no text")
    captured_at = now()
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise BaselineCaptureError("capture timestamp must include a timezone")
    return {
        "schema_version": "no-tools-baseline-v1",
        "case_id": case_id,
        "model": model,
        "captured_at": captured_at.isoformat(),
        "conditions": {
            "tools_enabled": False,
            "system_prompt_present": False,
            "input_is_question_only": True,
        },
        "question": question,
        "raw_output": content.strip(),
    }
