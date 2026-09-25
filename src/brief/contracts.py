from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from pydantic.alias_generators import to_camel


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True, strict=True)


Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500, pattern=r"^[^\r\n]+$")]


class Source(Contract):
    id: str
    url: str
    title: str
    description: str
    content: str
    markdown_url: str | None = None  # Verified by extraction, never guessed by the model.


class Decision(Contract):
    id: str
    kind: Literal["preference", "fact"]
    statement: str
    active: bool
    needs_review: bool = False
    review_sources: list[Source] = Field(default_factory=list)


class RefreshBaseline(Contract):
    markdown: str
    added_source_ids: list[str]
    changed_source_ids: list[str]
    removed_source_ids: list[str]


class GenerationInput(Contract):
    site_url: str
    sources: list[Source]
    decisions: list[Decision]
    dismissed_topics: list[str]
    mode: Literal["generate", "questions"]
    max_questions: int = Field(ge=0, le=3)
    refresh_baseline: RefreshBaseline | None = None

    @field_validator("sources", "decisions")
    @classmethod
    def unique_ids(cls, items: list[Source] | list[Decision]) -> list[Source] | list[Decision]:
        if len({item.id for item in items}) != len(items):
            raise ValueError("Duplicate IDs")
        return items


class Claim(Contract):
    text: Line
    evidence_ids: list[str] = Field(min_length=1)


class Link(Contract):
    source_id: str
    label: Line
    description: Line | None


class Section(Contract):
    title: Line
    links: list[Link] = Field(min_length=1)


class Shortcut(Contract):
    """A parent-level entry point that stays direct even when a child guide repeats it."""

    source_id: str
    reason: Line
    decision_ids: list[str]


class Guide(Contract):
    title: Line
    summary: Claim | None
    context: list[Claim] = Field(max_length=12)
    sections: list[Section] = Field(max_length=20)
    # Structural bound only. Owner-directed entry points come first, so this never
    # silently outranks explicit direction; see docs/GUIDES_AND_RUN_DETAILS.md.
    shortcuts: list[Shortcut] = Field(max_length=3)

    @model_validator(mode="before")
    @classmethod
    def absent_shortcuts(cls, data: Any) -> Any:
        """Documents saved before shortcuts existed have none; the field stays schema-required."""
        return {**data, "shortcuts": []} if isinstance(data, dict) and "shortcuts" not in data else data


class Question(Contract):
    topic: Line
    question: Line
    rationale: Line
    evidence_ids: list[str] = Field(min_length=1)
    options: list[Line] = Field(min_length=2, max_length=3)
    recommended_option: int | None = Field(ge=0, le=2)


class GenerationResult(Contract):
    guide: Guide | None
    explanation: Line
    questions: list[Question] = Field(max_length=3)


def validate_result(raw: object, context: GenerationInput) -> GenerationResult:
    """Product invariants; evidence existence does not establish factual entailment."""
    result = GenerationResult.model_validate(raw)
    if (context.mode == "generate") != (result.guide is not None):
        raise ValueError("Generation requires a guide; question-only requests must not mutate it")
    if len(result.questions) > context.max_questions:
        raise ValueError("Question budget exceeded")
    sources = {s.id for s in context.sources}
    decision_ids = {d.id for d in context.decisions}
    if sources & decision_ids:
        raise ValueError("Source and decision IDs must not overlap")
    evidence = sources | {d.id for d in context.decisions if d.active}

    def check_evidence(ids: list[str]) -> None:
        if unknown := set(ids) - evidence:
            raise ValueError(f"Unknown/inactive evidence: {sorted(unknown)}")

    topics = set(context.dismissed_topics)
    for question in result.questions:
        check_evidence(question.evidence_ids)
        if question.topic in topics:
            raise ValueError(f"Repeated/dismissed question topic: {question.topic}")
        topics.add(question.topic)
        if question.recommended_option is not None and question.recommended_option >= len(question.options):
            raise ValueError("Recommended answer does not exist")
    if result.guide:
        for claim in ([result.guide.summary] if result.guide.summary else []) + result.guide.context:
            check_evidence(claim.evidence_ids)
            if set(claim.evidence_ids) & {d.id for d in context.decisions if d.needs_review}:
                raise ValueError("Decision awaiting review cannot establish a factual claim")
        used = set()
        for section in result.guide.sections:
            for link in section.links:
                if link.source_id not in sources:
                    raise ValueError(f"Unknown source: {link.source_id}")
                if link.source_id in used:
                    raise ValueError(f"Duplicate source: {link.source_id}")
                used.add(link.source_id)
        # Retention only means "do not delegate this link", so it must be a real link here.
        active_decisions = {d.id for d in context.decisions if d.active}
        marked: set[str] = set()
        for shortcut in result.guide.shortcuts:
            if shortcut.source_id not in used:
                raise ValueError(f"Shortcut is not linked in the guide: {shortcut.source_id}")
            if shortcut.source_id in marked:
                raise ValueError(f"Duplicate shortcut: {shortcut.source_id}")
            marked.add(shortcut.source_id)
            if unknown := set(shortcut.decision_ids) - active_decisions:
                raise ValueError(f"Shortcut cites unknown/inactive direction: {sorted(unknown)}")
    return result
