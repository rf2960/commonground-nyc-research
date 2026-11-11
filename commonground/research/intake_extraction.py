"""Evidence-checked natural-language extraction for partial research intake."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable

import litellm
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .intake import ResearchIntake, TravelerIntake
from .models import CafeConstraints


_MIN_RATING = re.compile(
    r"\b(?:rated\s+at\s+least\s+|rating\s+at\s+least\s+|minimum\s+rating\s+(?:of\s+)?)"
    r"(\d+(?:\.\d+)?)(?=\s|[.,!?](?!\d)|$)",
    re.IGNORECASE,
)
_PRICE_LEVEL = re.compile(
    r"\bprice\s+level\s+([0-4])\b|\b(very expensive|inexpensive|moderate|expensive|free)"
    r"(?:[-\s]priced?\b|\s+price\b)",
    re.IGNORECASE,
)
_PRICE_NAMES = {"free": 0, "inexpensive": 1, "moderate": 2, "expensive": 3, "very expensive": 4}


EXTRACTION_SYSTEM_PROMPT = """You extract only explicit meeting-research inputs.
Return one JSON object and no prose. Never infer or invent a person, origin, commute
limit, date, time, or timezone. Every extracted value must include an exact quote copied
from one of the user messages. For meeting_time, return RFC 3339 with an explicit UTC
offset only when the user explicitly supplied a date, clock time, and timezone; otherwise
return null. Preserve an origin as the exact quoted text. A commute limit may be returned
only when the quote explicitly connects that person to a one-way minute limit.

Shape:
{
  "meeting_time": "RFC3339 with offset or null",
  "meeting_time_quote": "exact quote or null",
  "travelers": [
    {
      "identity_quote": "exact person label from the user",
      "origin_quote": "exact origin text or null",
      "max_commute_minutes": 35,
      "limit_quote": "exact quote or null"
    }
  ]
}
"""


class IntakeExtractionError(ValueError):
    """Model output was unavailable, invalid, or unsupported by user text."""


class _RawTraveler(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_quote: str = Field(min_length=1)
    origin_quote: str | None = None
    max_commute_minutes: float | None = Field(default=None, gt=0, le=300)
    limit_quote: str | None = None


class _RawExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meeting_time: str | None = None
    meeting_time_quote: str | None = None
    travelers: tuple[_RawTraveler, ...] = ()


def _has_quote(corpus: str, quote: str | None, field: str) -> str:
    if not isinstance(quote, str) or not quote.strip():
        raise IntakeExtractionError(f"{field} requires an exact user quote")
    normalized = quote.strip()
    if normalized.casefold() not in corpus.casefold():
        raise IntakeExtractionError(f"{field} quote was not found in user messages")
    return normalized


def _traveler_id(identity_quote: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", identity_quote.casefold()).strip("-")
    if not slug:
        raise IntakeExtractionError("traveler identity cannot form a stable ID")
    return f"traveler:{slug}"


def _cafe_constraints(corpus: str) -> CafeConstraints:
    """Read explicit rating and price phrases even when the extractor omits them."""
    ratings = [float(match[1]) for match in _MIN_RATING.finditer(corpus)]
    prices = [
        int(match[1]) if match[1] is not None else _PRICE_NAMES[match[2].casefold()]
        for match in _PRICE_LEVEL.finditer(corpus)
    ]
    if ratings and ratings[-1] > 5:
        raise IntakeExtractionError("minimum cafe rating must be at most five")
    return CafeConstraints(
        min_rating=ratings[-1] if ratings else 0,
        price_levels=(prices[-1],) if prices else (),
    )


def intake_from_extraction_payload(
    payload: dict[str, Any],
    user_messages: list[str] | tuple[str, ...],
) -> ResearchIntake:
    """Validate model JSON against verbatim evidence before creating an intake."""

    if not user_messages or any(not isinstance(item, str) for item in user_messages):
        raise IntakeExtractionError("at least one user message is required")
    corpus = "\n".join(user_messages)
    try:
        raw = _RawExtraction.model_validate(payload)
    except ValidationError as error:
        raise IntakeExtractionError("intake extraction violated its JSON schema") from error

    meeting_time = None
    if raw.meeting_time is not None:
        _has_quote(corpus, raw.meeting_time_quote, "meeting_time")
        try:
            meeting_time = datetime.fromisoformat(raw.meeting_time)
        except ValueError as error:
            raise IntakeExtractionError("meeting_time is not valid RFC 3339") from error
        if meeting_time.tzinfo is None or meeting_time.utcoffset() is None:
            raise IntakeExtractionError("meeting_time lacks an explicit UTC offset")
    elif raw.meeting_time_quote is not None:
        raise IntakeExtractionError("meeting_time_quote must be null when time is null")

    travelers = []
    seen: set[str] = set()
    for item in raw.travelers:
        identity = _has_quote(corpus, item.identity_quote, "traveler identity")
        traveler_id = _traveler_id(identity)
        if traveler_id in seen:
            raise IntakeExtractionError("extracted traveler identities are not unique")
        seen.add(traveler_id)

        origin = None
        if item.origin_quote is not None:
            origin = _has_quote(corpus, item.origin_quote, f"{traveler_id} origin")

        if item.max_commute_minutes is not None:
            _has_quote(corpus, item.limit_quote, f"{traveler_id} commute limit")
        elif item.limit_quote is not None:
            raise IntakeExtractionError(
                f"{traveler_id} limit_quote must be null when the limit is null"
            )
        travelers.append(
            TravelerIntake(
                traveler_id=traveler_id,
                input_location=origin,
                max_commute_minutes=item.max_commute_minutes,
            )
        )

    return ResearchIntake(
        question=user_messages[-1].strip(),
        meeting_time=meeting_time,
        travelers=tuple(travelers),
        cafe_constraints=_cafe_constraints(corpus),
    )


def extract_research_intake(
    user_messages: list[str] | tuple[str, ...],
    *,
    model: str,
    vertex_location: str,
    completion: Callable[..., Any] = litellm.completion,
) -> ResearchIntake:
    """Call one no-tool extractor, then reject fields unsupported by verbatim quotes."""

    if not user_messages:
        raise IntakeExtractionError("at least one user message is required")
    try:
        reply = completion(
            model=model,
            vertex_location=vertex_location,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"user_messages": list(user_messages)},
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
    except Exception as error:
        raise IntakeExtractionError("intake model call failed safely") from error
    try:
        content = reply.choices[0].message.content
        payload = json.loads(content)
    except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise IntakeExtractionError("model returned invalid intake JSON") from error
    if not isinstance(payload, dict):
        raise IntakeExtractionError("model returned a non-object intake payload")
    return intake_from_extraction_payload(payload, user_messages)
