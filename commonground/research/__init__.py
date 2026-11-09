"""Shared contracts for the Project 2 Deep Research workflow."""

from .models import (
    CONTRACT_VERSION,
    CafeConstraints,
    Candidate,
    Coordinates,
    Fact,
    FeasibilityReason,
    FeasibilityResult,
    FollowUpDecision,
    MissingEvidence,
    ResearchBrief,
    ResearchResult,
    ResearchTask,
    Source,
    Traveler,
)
from .feasibility import RULE_VERSION, evaluate_all_cafes, evaluate_cafe_feasibility
from .lead import MAX_FOLLOW_UP_TARGETS, LeadOrchestrator, LeadRun
from .runner import ROLE_TOOL_ALLOWLISTS, ResearchContext, ResearchRunner
from .writer import CitedClaim, EvidenceWriter, WriterReport, validate_writer_report

__all__ = [
    "CONTRACT_VERSION",
    "CafeConstraints",
    "CitedClaim",
    "Candidate",
    "Coordinates",
    "Fact",
    "FeasibilityReason",
    "FeasibilityResult",
    "FollowUpDecision",
    "EvidenceWriter",
    "LeadOrchestrator",
    "LeadRun",
    "MAX_FOLLOW_UP_TARGETS",
    "MissingEvidence",
    "ResearchBrief",
    "ResearchResult",
    "ResearchTask",
    "RULE_VERSION",
    "ROLE_TOOL_ALLOWLISTS",
    "ResearchContext",
    "ResearchRunner",
    "Source",
    "Traveler",
    "WriterReport",
    "evaluate_all_cafes",
    "evaluate_cafe_feasibility",
    "validate_writer_report",
]
