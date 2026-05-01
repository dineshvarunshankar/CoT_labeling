"""Dense-CoT annotation worker plus the annotation JSON contract.

This file owns:
    - the JSON schema handoff to Gemini
    - the JSON parser used on Gemini responses
    - the worker functions that drive Gemini and write annotation files
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from . import coverage, manifest, paths, wiki
from .gemini import GeminiClient

LOG = logging.getLogger(__name__)


BBox = Tuple[float, float, float, float]
MODEL_FIELDS = {"modality", "difficulty", "subject_bbox", "cot"}


class AnnotationParseError(ValueError):
    """Raised when Gemini does not return the required annotation JSON."""


def _bbox(value: object) -> BBox:
    if value is None:
        raise AnnotationParseError("subject_bbox is required")
    if not isinstance(value, list) or len(value) != 4:
        raise AnnotationParseError("subject_bbox must be an array of 4 numbers")
    try:
        left, top, right, bottom = (float(v) for v in value)
    except (TypeError, ValueError) as e:
        raise AnnotationParseError("subject_bbox must contain only numbers") from e
    if any(coord < 0.0 for coord in (left, top, right, bottom)):
        raise AnnotationParseError(
            f"subject_bbox must use positive coordinates: {value}"
        )
    if left >= right or top >= bottom:
        raise AnnotationParseError(f"subject_bbox coordinates are not ordered: {value}")
    return (left, top, right, bottom)


@dataclass
class Annotation:
    """The saved output for one image/category task."""

    image_id: str
    image_path: str
    label: str
    question: str
    gt_answer: str
    subject_bbox: BBox
    modality: str
    difficulty: str
    cot: str

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "image_path": self.image_path,
            "label": self.label,
            "question": self.question,
            "gt_answer": self.gt_answer,
            "subject_bbox": list(self.subject_bbox),
            "modality": self.modality,
            "difficulty": self.difficulty,
            "cot": self.cot,
        }


def parse_annotation_json(
    raw_text: str,
    *,
    image_id: str,
    image_path: str,
    label: str,
    question: str,
    gt_answer: str,
) -> Annotation:
    try:
        payload = json.loads(raw_text.strip())
    except json.JSONDecodeError as e:
        raise AnnotationParseError(f"invalid JSON: {e}") from e

    if not isinstance(payload, dict):
        raise AnnotationParseError("top-level model output must be a JSON object")

    extra = set(payload) - MODEL_FIELDS
    if extra:
        raise AnnotationParseError(f"unexpected model field(s): {sorted(extra)}")

    modality = str(payload.get("modality", "")).strip().lower()
    difficulty = str(payload.get("difficulty", "")).strip().lower()
    cot = str(payload.get("cot", "")).strip()

    if modality not in {"rgb", "thermal"}:
        raise AnnotationParseError("modality must be rgb or thermal")
    if difficulty not in {"easy", "hard"}:
        raise AnnotationParseError("difficulty must be easy or hard")
    if not cot:
        raise AnnotationParseError("cot is required")

    return Annotation(
        image_id=image_id,
        image_path=image_path,
        label=label,
        question=question,
        gt_answer=gt_answer,
        subject_bbox=_bbox(payload.get("subject_bbox")),
        modality=modality,
        difficulty=difficulty,
        cot=cot,
    )


def _annotation_path(item: manifest.ImageItem) -> Path:
    out_dir = paths.ANNOTATIONS / item.label
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{item.image_id}.json"


def _repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(paths.ROOT))
    except ValueError:
        return str(path)


def _response_schema() -> dict:
    return json.loads(paths.ANNOTATION_SCHEMA.read_text(encoding="utf-8"))


def _existing_annotation(item: manifest.ImageItem) -> Optional[Path]:
    path = _annotation_path(item)
    return path if path.exists() else None


def _serialize(ann: Annotation) -> str:
    return json.dumps(ann.to_dict(), indent=2)


def annotate_one(
    item: manifest.ImageItem,
    *,
    client: GeminiClient,
    memory: wiki.WikiMemory,
    force: bool = False,
) -> Optional[Annotation]:
    existing = _existing_annotation(item)
    if existing and not force:
        LOG.info("skip (exists): %s -> %s", item.task_id, existing.relative_to(paths.ROOT))
        return None

    text_prompt = wiki.build_annotation_prompt(item, memory)
    result = client.generate(
        text_prompt,
        image_path=item.image_path,
        response_json_schema=_response_schema(),
    )

    try:
        ann = parse_annotation_json(
            result.text,
            image_id=item.image_id,
            image_path=_repo_relative(item.image_path),
            label=item.label,
            question=item.question,
            gt_answer=item.gt_answer,
        )
    except AnnotationParseError as e:
        LOG.error("[%s] invalid JSON annotation: %s", item.task_id, e)
        return None

    return _finalize(item, ann)


def _finalize(item: manifest.ImageItem, ann: Annotation) -> Annotation:
    out_path = _annotation_path(item)
    out_path.write_text(_serialize(ann), encoding="utf-8")
    LOG.info("[%s] wrote %s", item.task_id, out_path.relative_to(paths.ROOT))
    return ann


def annotate_many(
    items: Iterable[manifest.ImageItem],
    *,
    client: Optional[GeminiClient] = None,
    force: bool = False,
    reload_wiki_each_call: bool = False,
) -> List[Annotation]:
    paths.ensure_dirs()
    client = client or GeminiClient()
    memory = wiki.load_wiki_memory()
    item_list = list(items)

    annotations: List[Annotation] = []
    total = len(item_list)
    for idx, item in enumerate(item_list, 1):
        if reload_wiki_each_call:
            memory = wiki.load_wiki_memory()
        LOG.info("[%d/%d] %s | gt=%s", idx, total, item.task_id, item.gt_answer)
        try:
            ann = annotate_one(item, client=client, memory=memory, force=force)
        except Exception as e:  # noqa: BLE001
            LOG.exception("[%s] hard failure: %s", item.task_id, e)
            continue
        if ann is not None:
            annotations.append(ann)
            coverage.mark_done([item])
    return annotations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Annotate triage images via Gemini + the Triage Wiki.")
    ap.add_argument("--label", action="append", help="restrict to one or more labels (repeatable)")
    ap.add_argument("--limit", type=int, default=None, help="annotate at most N images")
    ap.add_argument("--task", action="append", help="annotate specific task_id(s), e.g. label__image_id")
    ap.add_argument("--force", action="store_true", help="re-annotate even if a JSON already exists")
    ap.add_argument(
        "--reload-wiki-each-call",
        action="store_true",
        help="reload wiki memory before every image (slower; debug only)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    items = manifest.collect_items(args.label)
    if args.task:
        wanted = set(args.task)
        items = [i for i in items if i.task_id in wanted]
    if args.limit:
        items = items[: args.limit]

    if not items:
        LOG.error("no tasks to annotate (check --label / --task / exports/*)")
        return 1

    LOG.info("annotating %d tasks", len(items))
    annotate_many(items, force=args.force, reload_wiki_each_call=args.reload_wiki_each_call)
    return 0


if __name__ == "__main__":
    sys.exit(main())
