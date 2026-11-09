"""Validated evidence contracts shared by every Project 2 agent.

The models deliberately reject ambiguous or untraceable evidence before it reaches the
Lead or Writer. Provider adapters may return partial results, but every factual value
must still cite a source and every missing value must be represented explicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import parse_qs, urlparse

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_VERSION = "research-contract-v1"

NonEmptyStr = Annotated[str, Field(min_length=1)]
TravelerId = Annotated[str, Field(pattern=r"^traveler:[a-z0-9][a-z0-9-]*$")]
CandidateId = Annotated[
    str,
    Field(pattern=r"^(?:area:(?:initial|mta):[A-Za-z0-9._-]+|cafe:gplaces:[A-Za-z0-9._-]+)$"),
]
FactId = Annotated[str, Field(pattern=r"^fact:[a-z0-9_-]+:r[12]:[0-9]{3,}$")]
MissingId = Annotated[str, Field(pattern=r"^missing:[a-z0-9_-]+:r[12]:[0-9]{3,}$")]
SourceId = Annotated[str, Field(pattern=r"^source:[a-z0-9_-]+:[A-Za-z0-9._-]+$")]
ResearcherAgent = Literal[
    "transit_researcher",
    "cafe_researcher",
    "expansion_researcher",
]
AgentName = Literal[
    "lead",
    "transit_researcher",
    "cafe_researcher",
    "expansion_researcher",
    "writer",
]
ResultStatus = Literal["complete", "partial", "failed"]
MissingReasonCode = Literal[
    "PROVIDER_FIELD_MISSING",
    "ROUTE_UNAVAILABLE",
    "PROVIDER_ERROR",
    "DEPENDENCY_NOT_READY",
    "STALE_EVIDENCE",
    "VALIDATION_ERROR",
    "AGENT_EXECUTION_ERROR",
    "TIMEOUT",
]
FeasibilityStatus = Literal[
    "FEASIBLE",
    "COMMUTE_LIMIT_EXCEEDED",
    "CAFE_CONSTRAINT_FAILED",
    "EVIDENCE_INSUFFICIENT",
]


class ContractModel(BaseModel):
    """Strict, assignment-safe base for records crossing agent boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_unique(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    normalized = [value.casefold() for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must be unique")
    return values


def _require_aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include an explicit time zone or UTC offset")
    return value


def _contains_sensitive_key(value: Any) -> bool:
    sensitive = {"api_key", "apikey", "authorization", "password", "secret", "token"}
    if isinstance(value, dict):
        return any(
            str(key).casefold() in sensitive or _contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class Coordinates(ContractModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lng: Annotated[float, Field(ge=-180, le=180)]


class Traveler(ContractModel):
    traveler_id: TravelerId
    input_location: NonEmptyStr
    resolved_location: Coordinates
    max_commute_minutes: Annotated[float, Field(gt=0, le=300)]


class CafeConstraints(ContractModel):
    min_rating: Annotated[float, Field(ge=0, le=5)] = 0
    price_levels: tuple[Annotated[int, Field(ge=0, le=4)], ...] = ()
    require_open: bool = True

    @field_validator("price_levels")
    @classmethod
    def unique_price_levels(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if len(values) != len(set(values)):
            raise ValueError("price_levels must be unique")
        return values


class Candidate(ContractModel):
    candidate_id: Annotated[str, Field(pattern=r"^area:(?:initial|mta):[A-Za-z0-9._-]+$")]
    name: NonEmptyStr
    kind: Literal["initial_area", "expansion_area"]
    lat: Annotated[float, Field(ge=-90, le=90)]
    lng: Annotated[float, Field(ge=-180, le=180)]

    @model_validator(mode="after")
    def id_matches_kind(self) -> Candidate:
        prefix = "area:initial:" if self.kind == "initial_area" else "area:mta:"
        if not self.candidate_id.startswith(prefix):
            raise ValueError(f"{self.kind} candidate_id must start with {prefix}")
        return self


class ResearchBrief(ContractModel):
    research_id: Annotated[str, Field(pattern=r"^research:[A-Za-z0-9._-]+:[0-9]+$")]
    session_id: NonEmptyStr
    question: NonEmptyStr
    meeting_time: datetime
    travelers: Annotated[tuple[Traveler, ...], Field(min_length=2, max_length=6)]
    cafe_constraints: CafeConstraints
    initial_candidates: Annotated[tuple[Candidate, ...], Field(min_length=1, max_length=6)]
    max_follow_up_rounds: Literal[1] = 1

    @field_validator("meeting_time")
    @classmethod
    def meeting_time_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "meeting_time")

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> ResearchBrief:
        if not self.research_id.startswith(f"research:{self.session_id}:"):
            raise ValueError("research_id must contain the brief session_id")
        _require_unique(tuple(t.traveler_id for t in self.travelers), "traveler IDs")
        _require_unique(
            tuple(candidate.candidate_id for candidate in self.initial_candidates),
            "candidate IDs",
        )
        return self


class ResearchTask(ContractModel):
    task_id: Annotated[
        str,
        Field(pattern=r"^task:[A-Za-z0-9._-]+:r[12]:(?:transit|cafe|expansion):[0-9]+$"),
    ]
    research_id: Annotated[str, Field(pattern=r"^research:[A-Za-z0-9._-]+:[0-9]+$")]
    round: Literal[1, 2]
    agent: ResearcherAgent
    objective: NonEmptyStr
    candidate_ids: Annotated[tuple[CandidateId, ...], Field(min_length=1)]
    dependencies: tuple[FactId, ...] = ()
    allowed_tools: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def task_identity_is_consistent(self) -> ResearchTask:
        agent_token = {
            "transit_researcher": "transit",
            "cafe_researcher": "cafe",
            "expansion_researcher": "expansion",
        }[self.agent]
        expected_fragment = f":r{self.round}:{agent_token}:"
        if expected_fragment not in self.task_id:
            raise ValueError("task_id round/agent must match round and agent fields")
        task_session = self.task_id.split(":", 2)[1]
        research_session = self.research_id.rsplit(":", 1)[0].removeprefix("research:")
        if task_session != research_session:
            raise ValueError("task_id and research_id must refer to the same session")
        _require_unique(self.candidate_ids, "candidate IDs")
        _require_unique(self.dependencies, "dependencies")
        _require_unique(self.allowed_tools, "allowed tools")
        return self


class Fact(ContractModel):
    fact_id: FactId
    candidate_id: CandidateId
    subject_id: NonEmptyStr
    predicate: NonEmptyStr
    value: Any
    unit: str | None = None
    observed_at: datetime
    valid_for: dict[str, Any] = Field(default_factory=dict)
    source_ids: Annotated[tuple[SourceId, ...], Field(min_length=1)]
    provisional: bool = False

    @field_validator("value")
    @classmethod
    def value_is_present(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("missing values belong in MissingEvidence, not Fact")
        return value

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "observed_at")

    @field_validator("source_ids")
    @classmethod
    def source_ids_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _require_unique(values, "source IDs")


class Source(ContractModel):
    source_id: SourceId
    provider: NonEmptyStr
    title: NonEmptyStr
    url: AnyHttpUrl
    accessed_at: datetime
    request_summary: dict[str, Any]
    provider_record_ids: tuple[str, ...] = ()
    attribution: NonEmptyStr

    @field_validator("accessed_at")
    @classmethod
    def accessed_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "accessed_at")

    @field_validator("url")
    @classmethod
    def url_has_no_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        query_keys = {key.casefold() for key in parse_qs(urlparse(str(value)).query)}
        sensitive = {"api_key", "apikey", "authorization", "password", "secret", "token"}
        if query_keys & sensitive:
            raise ValueError("source URL must not contain credentials or access tokens")
        return value

    @field_validator("request_summary")
    @classmethod
    def request_summary_has_no_credentials(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_sensitive_key(value):
            raise ValueError("request_summary must not contain credential fields")
        return value

    @field_validator("provider_record_ids")
    @classmethod
    def provider_ids_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _require_unique(values, "provider record IDs")


class MissingEvidence(ContractModel):
    missing_id: MissingId
    candidate_id: CandidateId
    subject_id: str | None = None
    field: NonEmptyStr
    reason_code: MissingReasonCode
    detail: NonEmptyStr
    retryable: bool
    next_action: NonEmptyStr


class ResearchResult(ContractModel):
    task_id: Annotated[
        str,
        Field(pattern=r"^task:[A-Za-z0-9._-]+:r[12]:(?:transit|cafe|expansion):[0-9]+$"),
    ]
    agent: ResearcherAgent
    round: Literal[1, 2]
    status: ResultStatus
    facts: tuple[Fact, ...] = ()
    sources: tuple[Source, ...] = ()
    missing: tuple[MissingEvidence, ...] = ()
    candidate_ids_considered: Annotated[tuple[CandidateId, ...], Field(min_length=1)]
    summary: NonEmptyStr

    @model_validator(mode="after")
    def result_is_traceable(self) -> ResearchResult:
        agent_token = {
            "transit_researcher": "transit",
            "cafe_researcher": "cafe",
            "expansion_researcher": "expansion",
        }[self.agent]
        if f":r{self.round}:{agent_token}:" not in self.task_id:
            raise ValueError("task_id round/agent must match result round and agent")

        fact_ids = tuple(fact.fact_id for fact in self.facts)
        source_ids = tuple(source.source_id for source in self.sources)
        _require_unique(fact_ids, "fact IDs")
        _require_unique(source_ids, "source IDs")
        _require_unique(self.candidate_ids_considered, "considered candidate IDs")

        available_sources = set(source_ids)
        missing_sources = sorted(
            {
                source_id
                for fact in self.facts
                for source_id in fact.source_ids
                if source_id not in available_sources
            }
        )
        if missing_sources:
            raise ValueError(
                "facts reference source IDs absent from this result: "
                + ", ".join(missing_sources)
            )
        return self


class FollowUpDecision(ContractModel):
    round: Literal[2]
    reason_code: NonEmptyStr
    unresolved_predicate: NonEmptyStr
    selected_ids: Annotated[tuple[CandidateId, ...], Field(min_length=1, max_length=3)]
    task_agents: Annotated[tuple[ResearcherAgent, ...], Field(min_length=1)]
    dependencies: Annotated[tuple[FactId, ...], Field(min_length=1)]
    expected_information_gain: NonEmptyStr
    omitted_candidate_reason: NonEmptyStr

    @model_validator(mode="after")
    def decision_targets_are_unique(self) -> FollowUpDecision:
        _require_unique(self.selected_ids, "selected IDs")
        _require_unique(self.task_agents, "task agents")
        _require_unique(self.dependencies, "dependencies")
        return self


class FeasibilityReason(ContractModel):
    code: NonEmptyStr
    traveler_id: TravelerId | None = None
    actual_minutes: Annotated[float, Field(ge=0)] | None = None
    limit_minutes: Annotated[float, Field(gt=0)] | None = None
    input_fact_ids: tuple[FactId, ...] = ()
    input_missing_ids: tuple[MissingId, ...] = ()

    @field_validator("input_fact_ids")
    @classmethod
    def input_facts_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _require_unique(values, "input fact IDs")

    @field_validator("input_missing_ids")
    @classmethod
    def input_missing_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _require_unique(values, "input missing-evidence IDs")

    @model_validator(mode="after")
    def reason_has_evidence(self) -> FeasibilityReason:
        if not self.input_fact_ids and not self.input_missing_ids:
            raise ValueError("a feasibility reason must cite a fact or missing-evidence ID")
        return self


class FeasibilityResult(ContractModel):
    cafe_id: Annotated[str, Field(pattern=r"^cafe:gplaces:[A-Za-z0-9._-]+$")]
    status: FeasibilityStatus
    reasons: tuple[FeasibilityReason, ...] = ()
    rule_version: Annotated[str, Field(pattern=r"^feasibility-v[0-9]+$")]

    @model_validator(mode="after")
    def status_matches_reasons(self) -> FeasibilityResult:
        if self.status == "FEASIBLE" and self.reasons:
            raise ValueError("FEASIBLE results cannot contain blocker reasons")
        if self.status != "FEASIBLE" and not self.reasons:
            raise ValueError("non-feasible results require at least one reason")
        return self
