"""Evidence-only Writer for the fixed-data Project 2 vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .lead import LeadRun
from .models import Fact, MissingEvidence, Source


@dataclass(frozen=True)
class CitedClaim:
    """One user-visible statement and every record that supports it."""

    text: str
    fact_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    missing_ids: tuple[str, ...] = ()
    derived_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Writer claims cannot be empty")
        if not (
            self.fact_ids
            or self.source_ids
            or self.missing_ids
            or self.derived_ref
        ):
            raise ValueError("Every Writer claim must cite evidence or a derived record")


@dataclass(frozen=True)
class WriterReport:
    """Citation-auditable Writer output ready for `/chat` integration."""

    response: str
    claims: tuple[CitedClaim, ...]
    unknowns: tuple[CitedClaim, ...]
    recommended_cafe_id: str | None


class EvidenceWriter:
    """Render Lead evidence without adding model knowledge or relaxing constraints."""

    def write(self, run: LeadRun) -> WriterReport:
        facts, sources, missing = _evidence_indexes(run)
        comparison_claims = self._initial_comparison(run, facts, sources)
        follow_up_claims = self._follow_up_explanation(run, facts, sources)
        result_claims, recommended = self._result_claims(run, facts, sources)
        unknown_claims = tuple(
            self._claim(
                (
                    f"Unknown `{gap.field}` for `{gap.candidate_id}`: {gap.detail} "
                    f"Next action: {gap.next_action}"
                ),
                facts=facts,
                sources=sources,
                missing_ids=(gap.missing_id,),
            )
            for gap in sorted(missing.values(), key=lambda item: item.missing_id)
        )

        sections = [
            _section("Result", result_claims),
            _section("Why the initial candidates failed", comparison_claims),
            _section("What the targeted follow-up added", follow_up_claims),
            _section("Unknowns", unknown_claims),
        ]
        response = "\n\n".join(section for section in sections if section)
        report = WriterReport(
            response=response,
            claims=tuple(result_claims + comparison_claims + follow_up_claims),
            unknowns=unknown_claims,
            recommended_cafe_id=recommended,
        )
        validate_writer_report(report, run)
        return report

    def _initial_comparison(
        self,
        run: LeadRun,
        facts: Mapping[str, Fact],
        sources: Mapping[str, Source],
    ) -> list[CitedClaim]:
        claims: list[CitedClaim] = []
        limits = {
            traveler.traveler_id: traveler.max_commute_minutes
            for traveler in run.brief.travelers
        }
        traveler_names = {
            traveler.traveler_id: traveler.input_location
            for traveler in run.brief.travelers
        }
        candidate_names = {
            candidate.candidate_id: candidate.name
            for candidate in run.brief.initial_candidates
        }
        round_one_facts = tuple(
            fact for result in run.round_one_results for fact in result.facts
        )

        for candidate_id, candidate_name in candidate_names.items():
            exceeded = tuple(
                fact
                for fact in round_one_facts
                if fact.candidate_id == candidate_id
                and fact.predicate == "transit_duration_minutes"
                and fact.subject_id in limits
                and isinstance(fact.value, (int, float))
                and not isinstance(fact.value, bool)
                and fact.value > limits[fact.subject_id]
            )
            if exceeded:
                details = ", ".join(
                    (
                        f"{traveler_names[fact.subject_id]} {float(fact.value):g} > "
                        f"{limits[fact.subject_id]:g} minutes"
                    )
                    for fact in exceeded
                )
                claims.append(
                    self._claim(
                        f"{candidate_name} failed at the area-center stage: {details}.",
                        facts=facts,
                        sources=sources,
                        fact_ids=tuple(fact.fact_id for fact in exceeded),
                    )
                )

        closed = tuple(
            fact
            for fact in round_one_facts
            if fact.candidate_id.startswith("cafe:gplaces:")
            and fact.predicate == "open_at_meeting_time"
            and fact.value is False
        )
        for fact in closed:
            claims.append(
                self._claim(
                    (
                        f"Initial cafe `{fact.candidate_id}` was expected to be closed "
                        "at the requested meeting time."
                    ),
                    facts=facts,
                    sources=sources,
                    fact_ids=(fact.fact_id,),
                )
            )
        return claims

    def _follow_up_explanation(
        self,
        run: LeadRun,
        facts: Mapping[str, Fact],
        sources: Mapping[str, Source],
    ) -> list[CitedClaim]:
        claims: list[CitedClaim] = []
        if run.follow_up_decision is None:
            return claims

        decision = run.follow_up_decision
        claims.append(
            self._claim(
                (
                    f"Lead used its single follow-up round for "
                    f"`{decision.reason_code}` and selected "
                    f"{', '.join(f'`{item}`' for item in decision.selected_ids)}. "
                    f"Expected information gain: {decision.expected_information_gain}"
                ),
                facts=facts,
                sources=sources,
                fact_ids=decision.dependencies,
                derived_ref=f"follow-up:r{decision.round}:{decision.reason_code}",
            )
        )

        coordinate_dependencies = tuple(
            dependency
            for task in run.round_two_tasks
            if task.agent == "transit_researcher"
            for dependency in task.dependencies
            if dependency in facts and facts[dependency].predicate == "coordinates"
        )
        if coordinate_dependencies:
            claims.append(
                self._claim(
                    (
                        "Exact-address Transit was dispatched only after Cafe returned "
                        "the selected venue coordinates."
                    ),
                    facts=facts,
                    sources=sources,
                    fact_ids=coordinate_dependencies,
                    derived_ref="lead-policy:places-before-routes",
                )
            )
        return claims

    def _result_claims(
        self,
        run: LeadRun,
        facts: Mapping[str, Fact],
        sources: Mapping[str, Source],
    ) -> tuple[list[CitedClaim], str | None]:
        claims: list[CitedClaim] = []
        recommended: str | None = None

        if not run.feasibility_results:
            claims.append(self._claim(
                'No supported cafe recommendation is available from this bounded search. '
                'This does not prove that no feasible cafe exists elsewhere; inspect the evidence and unknowns below.',
                facts=facts, sources=sources,
                fact_ids=tuple(f.fact_id for f in facts.values() if f.predicate == 'cafe_search_results'),
                derived_ref='lead-policy:no-supported-recommendation',
            ))

        for feasibility in sorted(
            run.feasibility_results,
            key=lambda item: (item.status != "FEASIBLE", item.cafe_id),
        ):
            cafe_facts = tuple(
                fact for fact in facts.values() if fact.candidate_id == feasibility.cafe_id
            )
            by_predicate = {fact.predicate: fact for fact in cafe_facts}
            name_fact = by_predicate.get("name")
            label = (
                str(name_fact.value)
                if name_fact is not None
                else feasibility.cafe_id
            )
            name_ids = (name_fact.fact_id,) if name_fact else ()
            derived_ref = f"{feasibility.rule_version}:{feasibility.cafe_id}"

            if feasibility.status == "FEASIBLE":
                supporting = tuple(
                    fact.fact_id
                    for fact in cafe_facts
                    if fact.predicate
                    in {
                        "name",
                        "address",
                        "coordinates",
                        "rating",
                        "price_level",
                        "business_status",
                        "open_at_meeting_time",
                        "transit_duration_minutes",
                    }
                )
                claims.append(
                    self._claim(
                        (
                            f"Recommend {label} (`{feasibility.cafe_id}`): "
                            "`feasibility-v1` classifies it as FEASIBLE without "
                            "relaxing commute or cafe constraints."
                        ),
                        facts=facts,
                        sources=sources,
                        fact_ids=supporting,
                        derived_ref=derived_ref,
                    )
                )
                route_facts = tuple(
                    fact
                    for fact in cafe_facts
                    if fact.predicate == "transit_duration_minutes"
                    and fact.valid_for.get("destination_kind") == "exact_cafe"
                )
                if route_facts:
                    limits = {
                        traveler.traveler_id: traveler.max_commute_minutes
                        for traveler in run.brief.travelers
                    }
                    route_text = ", ".join(
                        (
                            f"{fact.subject_id} {float(fact.value):g}/"
                            f"{limits[fact.subject_id]:g} minutes"
                        )
                        for fact in route_facts
                    )
                    claims.append(
                        self._claim(
                            f"Exact-cafe commute checks all pass: {route_text}.",
                            facts=facts,
                            sources=sources,
                            fact_ids=tuple(fact.fact_id for fact in route_facts),
                            derived_ref=derived_ref,
                        )
                    )
                opening = by_predicate.get("open_at_meeting_time")
                if opening is not None and opening.provisional:
                    claims.append(
                        self._claim(
                            (
                                "Opening status is a future regular-schedule estimate, "
                                "not a guarantee; venue verification is still prudent."
                            ),
                            facts=facts,
                            sources=sources,
                            fact_ids=(opening.fact_id,),
                        )
                    )
                if recommended is None:
                    recommended = feasibility.cafe_id
                continue

            blocker_fact_ids = tuple(
                fact_id
                for reason in feasibility.reasons
                for fact_id in reason.input_fact_ids
            )
            blocker_missing_ids = tuple(
                missing_id
                for reason in feasibility.reasons
                for missing_id in reason.input_missing_ids
            )
            reason_codes = ", ".join(
                sorted({reason.code for reason in feasibility.reasons})
            )
            claims.append(
                self._claim(
                    (
                        f"Do not recommend {label} (`{feasibility.cafe_id}`): status "
                        f"is {feasibility.status}; supported blocker(s): {reason_codes}."
                    ),
                    facts=facts,
                    sources=sources,
                    fact_ids=tuple(dict.fromkeys((*name_ids, *blocker_fact_ids))),
                    missing_ids=tuple(dict.fromkeys(blocker_missing_ids)),
                    derived_ref=derived_ref,
                )
            )
        return claims, recommended

    @staticmethod
    def _claim(
        text: str,
        *,
        facts: Mapping[str, Fact],
        sources: Mapping[str, Source],
        fact_ids: Iterable[str] = (),
        missing_ids: Iterable[str] = (),
        derived_ref: str | None = None,
    ) -> CitedClaim:
        unique_facts = tuple(dict.fromkeys(fact_ids))
        unknown = [fact_id for fact_id in unique_facts if fact_id not in facts]
        if unknown:
            raise ValueError(f"Writer claim references unknown facts: {unknown}")
        source_ids = tuple(
            sorted(
                {
                    source_id
                    for fact_id in unique_facts
                    for source_id in facts[fact_id].source_ids
                }
            )
        )
        if any(source_id not in sources for source_id in source_ids):
            raise ValueError("Writer claim references an unavailable source")
        return CitedClaim(
            text=text,
            fact_ids=unique_facts,
            source_ids=source_ids,
            missing_ids=tuple(dict.fromkeys(missing_ids)),
            derived_ref=derived_ref,
        )


def _evidence_indexes(
    run: LeadRun,
) -> tuple[dict[str, Fact], dict[str, Source], dict[str, MissingEvidence]]:
    results = (*run.round_one_results, *run.round_two_results)
    facts: dict[str, Fact] = {}
    sources: dict[str, Source] = {}
    missing: dict[str, MissingEvidence] = {}
    for result in results:
        for fact in result.facts:
            if fact.fact_id in facts:
                raise ValueError(f"duplicate fact ID across results: {fact.fact_id}")
            facts[fact.fact_id] = fact
        for source in result.sources:
            existing = sources.get(source.source_id)
            if existing is not None and existing != source:
                raise ValueError(
                    f"conflicting source record across results: {source.source_id}"
                )
            sources[source.source_id] = source
        for gap in result.missing:
            if gap.missing_id in missing:
                raise ValueError(
                    f"duplicate missing-evidence ID across results: {gap.missing_id}"
                )
            missing[gap.missing_id] = gap
    return facts, sources, missing


def _citation(claim: CitedClaim) -> str:
    parts = []
    if claim.fact_ids:
        parts.append("facts=" + ",".join(claim.fact_ids))
    if claim.source_ids:
        parts.append("sources=" + ",".join(claim.source_ids))
    if claim.missing_ids:
        parts.append("missing=" + ",".join(claim.missing_ids))
    if claim.derived_ref:
        parts.append("derived=" + claim.derived_ref)
    return "[" + "; ".join(parts) + "]"


def _section(title: str, claims: Iterable[CitedClaim]) -> str:
    records = tuple(claims)
    if not records:
        return ""
    body = "\n".join(f"- {claim.text} {_citation(claim)}" for claim in records)
    return f"## {title}\n\n{body}"


def validate_writer_report(report: WriterReport, run: LeadRun) -> None:
    """Reject unsupported citations or evidence that is absent from rendered output."""

    facts, sources, missing = _evidence_indexes(run)
    derived_refs = {
        f"{result.rule_version}:{result.cafe_id}" for result in run.feasibility_results
    }
    if not run.feasibility_results:
        derived_refs.add('lead-policy:no-supported-recommendation')
    if run.follow_up_decision is not None:
        decision = run.follow_up_decision
        derived_refs.add(f"follow-up:r{decision.round}:{decision.reason_code}")
    if any(task.agent == 'transit_researcher' and any(
        dep in facts and facts[dep].predicate == 'coordinates' for dep in task.dependencies
    ) for task in run.round_two_tasks):
        derived_refs.add('lead-policy:places-before-routes')
    feasible_ids = {result.cafe_id for result in run.feasibility_results if result.status == 'FEASIBLE'}
    if report.recommended_cafe_id is not None and report.recommended_cafe_id not in feasible_ids:
        raise ValueError('Writer recommendation is not supported by a FEASIBLE result')
    for claim in (*report.claims, *report.unknowns):
        if claim.derived_ref is not None and claim.derived_ref not in derived_refs:
            raise ValueError('Writer report cites an unknown derived record')
        if any(fact_id not in facts for fact_id in claim.fact_ids):
            raise ValueError("Writer report cites an unknown fact")
        if any(source_id not in sources for source_id in claim.source_ids):
            raise ValueError("Writer report cites an unknown source")
        if any(missing_id not in missing for missing_id in claim.missing_ids):
            raise ValueError("Writer report cites an unknown missing-evidence record")
        expected_sources = tuple(
            sorted(
                {
                    source_id
                    for fact_id in claim.fact_ids
                    for source_id in facts[fact_id].source_ids
                }
            )
        )
        if claim.source_ids != expected_sources:
            raise ValueError("Writer claim source citations do not match its facts")
        for reference in (
            *claim.fact_ids,
            *claim.source_ids,
            *claim.missing_ids,
            *((claim.derived_ref,) if claim.derived_ref else ()),
        ):
            if reference not in report.response:
                raise ValueError(
                    f"Writer response omitted cited reference from text: {reference}"
                )
