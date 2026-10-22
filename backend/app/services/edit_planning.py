"""Read-only diagnosis and selectable action plans for the editing Agent."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.schemas.ir import CoursePackage, Slide


class EditFinding(BaseModel):
    id: str
    title: str
    detail: str
    tone: str = "neutral"


class PlannedAction(BaseModel):
    id: str
    title: str
    detail: str
    prompt: str
    target_id: str | None = None
    selected: bool = True


class EditPlan(BaseModel):
    request: str
    summary: str
    findings: list[EditFinding] = Field(default_factory=list)
    actions: list[PlannedAction] = Field(default_factory=list)


def _densest_slide(slides: list[Slide]) -> Slide | None:
    candidates = [slide for slide in slides if slide.layout != "title"]
    return max(candidates, key=lambda slide: len(slide.bullets) + bool(slide.speaker_notes)) if candidates else None


def _animation_target(slides: list[Slide], request: str) -> Slide | None:
    """Recognize the deliberately narrow request emitted by the animation CTA."""
    if "animation" not in request.lower():
        return None
    match = re.search(r"\bslide\s+(?:s)?(\d+)\b", request, flags=re.IGNORECASE)
    if not match:
        return None
    slide_id = f"s{match.group(1)}"
    return next((slide for slide in slides if slide.id == slide_id), None)


def plan_edit(package: CoursePackage, request: str, target: str = "slides") -> EditPlan:
    """Inspect IR only; selecting a result later still uses the existing patch review flow."""
    slides = package.slide_deck.slides if package.slide_deck else []
    findings: list[EditFinding] = []
    actions: list[PlannedAction] = []
    if target != "slides":
        findings.append(EditFinding(id="target", title="Review the selected material", detail="The Agent will inspect the selected assessment material before proposing an editable patch."))
        actions.append(PlannedAction(id="review-selected", title="Improve the selected material", detail="Read the selected material and propose only the smallest useful changes.", prompt=f"Teacher request: {request}. First read the selected {target} material. Then propose only the smallest useful patches, explaining the teaching reason for each."))
        return EditPlan(request=request, summary="This is a read-only plan. Selected actions still create reviewable proposed patches only.", findings=findings, actions=actions)
    if not slides:
        return EditPlan(request=request, summary="There are no slides to inspect yet.", findings=[EditFinding(id="no-slides", title="No slides available", detail="Generate courseware before asking the Agent to plan an edit.", tone="warning")])
    animation_target = _animation_target(slides, request)
    if animation_target is not None:
        return EditPlan(
            request=request,
            summary=f"Animation proposal is limited to slide {animation_target.order}; its teaching content will not be changed.",
            findings=[EditFinding(
                id=f"animation-{animation_target.id}",
                title=f"Animate slide {animation_target.order}",
                detail="Reveal only existing content in a teaching order. The resulting patch remains reviewable before it applies.",
                tone="info",
            )],
            actions=[PlannedAction(
                id=f"animate-{animation_target.id}",
                title=f"Generate animation for slide {animation_target.order}",
                detail="Read this slide, then propose a short reveal or emphasis sequence without changing its teaching content.",
                prompt=(
                    f"First read slide {animation_target.id} ({animation_target.title}). "
                    "Propose an animation patch only: reveal or emphasize existing title, bullets, or visuals in a teaching order. "
                    "Do not change text, notes, visuals, objectives, or any other slide."
                ),
                target_id=animation_target.id,
            )],
        )
    covered = {oid for slide in slides for oid in slide.objective_ids}
    for objective in package.project.learning_objectives:
        if objective.id not in covered:
            findings.append(EditFinding(id=f"coverage-{objective.id}", title=f"{objective.id} has no slide coverage", detail=f"{objective.id} — {objective.text} has no connected slide yet.", tone="warning"))
            actions.append(PlannedAction(id=f"cover-{objective.id}", title=f"Add evidence for {objective.id}", detail="Choose an appropriate slide and connect a concrete explanation or activity to this objective.", prompt=f"First inspect the most appropriate slide for {objective.id}: {objective.text}. Then propose the smallest patch that adds a concrete explanation or activity and links that slide to the objective."))
    dense = _densest_slide(slides)
    if dense is not None:
        if len(dense.bullets) >= 4:
            findings.append(EditFinding(id=f"density-{dense.id}", title=f"Slide {dense.order} may be dense", detail=f"{dense.title} has {len(dense.bullets)} main points for {package.project.meta.audience}.", tone="info"))
        actions.append(PlannedAction(id=f"teach-{dense.id}", title=f"Strengthen the teaching on slide {dense.order}", detail="Read the slide first; improve it with a concrete scenario, prompt, or speaker-note cue instead of merely rewriting text.", prompt=f"Teacher request: {request}. First read slide {dense.id} ({dense.title}). Improve this slide for teaching with a concrete scenario, guiding question, or speaker-note cue. Propose only reviewable patches and explain how each helps learners." ,target_id=dense.id))
    if package.lesson_plan is not None:
        actions.append(PlannedAction(id="align-plan", title="Align the lesson-plan facilitation", detail="Check whether the lesson plan includes a clear teacher prompt or understanding check after this change.", prompt=f"Teacher request: {request}. Inspect the relevant lesson-plan entry and propose at most one minimal patch that keeps the teacher guidance aligned with the slide changes."))
    return EditPlan(request=request, summary=f"Checked {len(slides)} slides and {len(package.project.learning_objectives)} learning objectives. Select actions to run; every resulting change still waits for your approval.", findings=findings, actions=actions)
