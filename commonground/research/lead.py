"""Deterministic Lead control flow for the bounded two-round research MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .feasibility import evaluate_cafe_feasibility
from .models import (
    Fact,
    FeasibilityResult,
    FollowUpDecision,
    MissingEvidence,
    ResearchBrief,
    ResearchResult,
    ResearchTask,
)
from .runner import ROLE_TOOL_ALLOWLISTS, ResearchRunner


MAX_FOLLOW_UP_TARGETS = 3


@dataclass(frozen=True)
class LeadRun:
    """Auditable output of one bounded Lead execution."""

    brief: ResearchBrief
    initial_tasks: tuple[ResearchTask, ...]
    round_one_results: tuple[ResearchResult, ...]
    follow_up_decision: FollowUpDecision | None
    round_two_tasks: tuple[ResearchTask, ...]
    round_two_results: tuple[ResearchResult, ...]
    feasibility_results: tuple[FeasibilityResult, ...]


class LeadOrchestrator:
    """Plan, fan out, and perform at most one evidence-driven follow-up round."""

    def __init__(self, runner: ResearchRunner) -> None:
        self._runner = runner

    async def run(self, brief: ResearchBrief) -> LeadRun:
        initial_tasks = self.build_initial_tasks(brief)
        round_one = await self._runner.run_initial_round(brief, initial_tasks)
        decision = self.choose_follow_up(brief, round_one)

        round_two_tasks: list[ResearchTask] = []
        round_two_results: list[ResearchResult] = []
        exact_cafe_ids: tuple[str, ...] = ()

        if decision is not None and decision.reason_code == "NO_FEASIBLE_INITIAL_CAFE":
            cafe_task = self._research_task(
                brief,
                round_number=2,
                agent="cafe_researcher",
                objective=(
                    "Search the selected MTA expansion areas without relaxing any "
                    "cafe constraint"
                ),
                candidate_ids=decision.selected_ids,
                dependencies=decision.dependencies,
            )
            round_two_tasks.append(cafe_task)
            cafe_result = await self._runner.run_task(
                brief, cafe_task, dependency_results=round_one
            )
            round_two_results.append(cafe_result)

            exact_cafe_ids = self._routeable_cafes(brief, cafe_result)[:MAX_FOLLOW_UP_TARGETS]
            coordinate_dependencies = self._coordinate_fact_ids(
                cafe_result.facts,
                exact_cafe_ids,
            )
            if exact_cafe_ids and coordinate_dependencies:
                transit_task = self._research_task(
                    brief,
                    round_number=2,
                    agent="transit_researcher",
                    objective=(
                        "Measure every traveler's arrival ETA to the selected exact "
                        "cafe destinations"
                    ),
                    candidate_ids=exact_cafe_ids,
                    dependencies=coordinate_dependencies,
                )
                round_two_tasks.append(transit_task)
                round_two_results.append(
                    await self._runner.run_task(
                        brief, transit_task, dependency_results=(cafe_result,)
                    )
                )

        elif decision is not None and decision.reason_code == "EXACT_DESTINATION_REQUIRED":
            exact_cafe_ids = tuple(decision.selected_ids)
            transit_task = self._research_task(
                brief,
                round_number=2,
                agent="transit_researcher",
                objective=(
                    "Replace area-center estimates with exact-cafe arrival ETAs for "
                    "every traveler"
                ),
                candidate_ids=exact_cafe_ids,
                dependencies=decision.dependencies,
            )
            round_two_tasks.append(transit_task)
            round_two_results.append(await self._runner.run_task(
                brief, transit_task, dependency_results=round_one
            ))

        facts = tuple(
            fact
            for result in (*round_one, *round_two_results)
            for fact in result.facts
        )
        missing = tuple(
            gap
            for result in (*round_one, *round_two_results)
            for gap in result.missing
        )
        feasibility = tuple(
            evaluate_cafe_feasibility(brief, cafe_id, facts, missing)
            for cafe_id in exact_cafe_ids
            if self._has_exact_route_evidence(cafe_id, facts, missing)
        )

        return LeadRun(
            brief=brief,
            initial_tasks=initial_tasks,
            round_one_results=round_one,
            follow_up_decision=decision,
            round_two_tasks=tuple(round_two_tasks),
            round_two_results=tuple(round_two_results),
            feasibility_results=feasibility,
        )

    @staticmethod
    def build_initial_tasks(brief: ResearchBrief) -> tuple[ResearchTask, ...]:
        candidate_ids = tuple(
            candidate.candidate_id for candidate in brief.initial_candidates
        )
        return (
            LeadOrchestrator._research_task(
                brief,
                round_number=1,
                agent="transit_researcher",
                objective="Measure arrival ETAs to every initial area center",
                candidate_ids=candidate_ids,
            ),
            LeadOrchestrator._research_task(
                brief,
                round_number=1,
                agent="cafe_researcher",
                objective=(
                    "Search initial areas for cafes and meeting-time opening evidence"
                ),
                candidate_ids=candidate_ids,
            ),
            LeadOrchestrator._research_task(
                brief,
                round_number=1,
                agent="expansion_researcher",
                objective=(
                    "Find a bounded set of non-duplicate MTA expansion candidates"
                ),
                candidate_ids=candidate_ids,
            ),
        )

    @staticmethod
    def choose_follow_up(
        brief: ResearchBrief,
        results: Iterable[ResearchResult],
    ) -> FollowUpDecision | None:
        records = tuple(results)
        if {result.agent for result in records} != {
            "transit_researcher",
            "cafe_researcher",
            "expansion_researcher",
        }:
            raise ValueError("follow-up policy requires all three initial role results")
        if any(result.round != 1 for result in records):
            raise ValueError("follow-up policy accepts round-1 results only")

        cafe_result = next(
            result for result in records if result.agent == "cafe_researcher"
        )
        promising_initial = LeadOrchestrator._routeable_cafes(
            brief, cafe_result
        )[:MAX_FOLLOW_UP_TARGETS]
        coordinate_dependencies = LeadOrchestrator._coordinate_fact_ids(
            cafe_result.facts,
            promising_initial,
        )
        if promising_initial and coordinate_dependencies:
            return FollowUpDecision(
                round=2,
                reason_code="EXACT_DESTINATION_REQUIRED",
                unresolved_predicate="Exact-cafe transit duration for every traveler",
                selected_ids=promising_initial,
                task_agents=("transit_researcher",),
                dependencies=coordinate_dependencies,
                expected_information_gain=(
                    "Replace area-center estimates with the route evidence required "
                    "for hard commute-limit decisions."
                ),
                omitted_candidate_reason=(
                    "Route at most three cafes with coordinates and passing known "
                    "constraints; an explicit missing-hours gap remains unknown."
                ),
            )

        expansion_result = next(
            result for result in records if result.agent == "expansion_researcher"
        )
        expansion_reasons = tuple(
            fact
            for fact in expansion_result.facts
            if fact.predicate == "expansion_selection_reason"
            and fact.candidate_id.startswith("area:mta:")
        )
        selected_reasons = tuple(
            sorted(expansion_reasons, key=lambda fact: fact.candidate_id)
        )[:MAX_FOLLOW_UP_TARGETS]
        if not selected_reasons:
            return None

        omitted_count = len(expansion_reasons) - len(selected_reasons)
        if omitted_count:
            omitted_reason = (
                f"{omitted_count} lower-priority expansion candidate(s) were omitted "
                "to preserve the three-target bound."
            )
        else:
            omitted_reason = (
                "The fixture exposes only one non-duplicate expansion station, so no "
                "lower-value station is queried."
                if len(selected_reasons) == 1
                else "Every available non-duplicate candidate fits the three-target bound."
            )

        return FollowUpDecision(
            round=2,
            reason_code="NO_FEASIBLE_INITIAL_CAFE",
            unresolved_predicate=(
                "Whether the MTA-backed expansion area contains a cafe that passes "
                "cafe constraints and exact-address commute limits"
            ),
            selected_ids=tuple(fact.candidate_id for fact in selected_reasons),
            task_agents=("cafe_researcher", "transit_researcher"),
            dependencies=tuple(fact.fact_id for fact in selected_reasons),
            expected_information_gain=(
                "Resolve cafe availability first, then use its exact coordinates to "
                "resolve every traveler's hard-limit check."
            ),
            omitted_candidate_reason=omitted_reason,
        )

    @staticmethod
    def _research_task(
        brief: ResearchBrief,
        *,
        round_number: int,
        agent: str,
        objective: str,
        candidate_ids: tuple[str, ...],
        dependencies: tuple[str, ...] = (),
    ) -> ResearchTask:
        agent_token = agent.removesuffix("_researcher")
        return ResearchTask.model_validate(
            {
                "task_id": (
                    f"task:{brief.session_id}:r{round_number}:{agent_token}:1"
                ),
                "research_id": brief.research_id,
                "round": round_number,
                "agent": agent,
                "objective": objective,
                "candidate_ids": candidate_ids,
                "dependencies": dependencies,
                "allowed_tools": tuple(sorted(ROLE_TOOL_ALLOWLISTS[agent])),
            }
        )

    @staticmethod
    def _routeable_cafes(brief: ResearchBrief, result: ResearchResult) -> tuple[str, ...]:
        passing = LeadOrchestrator._promising_cafes(brief, result.facts)
        missing_hours_ids = {
            gap.candidate_id for gap in result.missing
            if gap.field == "open_at_meeting_time"
        }
        pending_hours = LeadOrchestrator._promising_cafes(
            brief, result.facts, allow_missing_hours=True
        )
        # Complete cafe evidence gets priority. Unknown hours must not be upgraded to
        # open, but can still receive exact routing for an honest insufficient result.
        return passing + tuple(
            cafe_id for cafe_id in pending_hours
            if cafe_id not in passing and cafe_id in missing_hours_ids
        )

    @staticmethod
    def _promising_cafes(
        brief: ResearchBrief,
        facts: Iterable[Fact],
        *,
        allow_missing_hours: bool = False,
    ) -> tuple[str, ...]:
        by_cafe: dict[str, dict[str, Fact]] = {}
        for fact in facts:
            if fact.candidate_id.startswith("cafe:gplaces:"):
                by_cafe.setdefault(fact.candidate_id, {})[fact.predicate] = fact

        selected = []
        for cafe_id, predicates in sorted(by_cafe.items()):
            required = {"coordinates", "business_status"}
            if brief.cafe_constraints.require_open and not allow_missing_hours:
                required.add("open_at_meeting_time")
            if brief.cafe_constraints.min_rating > 0:
                required.add("rating")
            if brief.cafe_constraints.price_levels:
                required.add("price_level")
            if not required.issubset(predicates):
                continue
            if predicates["business_status"].value != "OPERATIONAL":
                continue
            if (
                brief.cafe_constraints.require_open
                and "open_at_meeting_time" in predicates
                and predicates["open_at_meeting_time"].value is not True
            ):
                continue
            rating = predicates.get("rating")
            if rating is not None and (
                not isinstance(rating.value, (int, float))
                or isinstance(rating.value, bool)
                or rating.value < brief.cafe_constraints.min_rating
            ):
                continue
            price = predicates.get("price_level")
            if price is not None and brief.cafe_constraints.price_levels and (
                price.value not in brief.cafe_constraints.price_levels
            ):
                continue
            selected.append(cafe_id)
        return tuple(selected)

    @staticmethod
    def _coordinate_fact_ids(
        facts: Iterable[Fact],
        cafe_ids: Iterable[str],
    ) -> tuple[str, ...]:
        selected = set(cafe_ids)
        return tuple(
            fact.fact_id
            for fact in facts
            if fact.candidate_id in selected and fact.predicate == "coordinates"
        )

    @staticmethod
    def _has_exact_route_evidence(
        cafe_id: str,
        facts: tuple[Fact, ...],
        missing: tuple[MissingEvidence, ...],
    ) -> bool:
        return any(
            fact.candidate_id == cafe_id
            and fact.predicate == "transit_duration_minutes"
            and fact.valid_for.get("destination_kind") == "exact_cafe"
            for fact in facts
        ) or any(
            gap.candidate_id == cafe_id
            and gap.field == "transit_duration_minutes"
            for gap in missing
        )
