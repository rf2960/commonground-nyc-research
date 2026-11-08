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

__all__ = [
    "CONTRACT_VERSION",
    "CafeConstraints",
    "Candidate",
    "Coordinates",
    "Fact",
    "FeasibilityReason",
    "FeasibilityResult",
    "FollowUpDecision",
    "MissingEvidence",
    "ResearchBrief",
    "ResearchResult",
    "ResearchTask",
    "RULE_VERSION",
    "Source",
    "Traveler",
    "evaluate_all_cafes",
    "evaluate_cafe_feasibility",
]
