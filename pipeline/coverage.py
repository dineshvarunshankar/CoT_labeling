"""Maintain coverage.csv, the live requeue sheet."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List

from . import manifest, paths, wiki

LOG = logging.getLogger(__name__)

META_FIELDS = [
    "task_id",
    "image_id",
    "image_path",
    "label",
    "gt_answer",
    "has_annotation",
    "difficulty",
]


def task_id(label: str, image_id: str) -> str:
    return manifest.task_id(label, image_id)


def _read_existing() -> Dict[str, dict]:
    if not paths.COVERAGE_CSV.exists():
        return {}
    with paths.COVERAGE_CSV.open(newline="", encoding="utf-8") as handle:
        return {row["task_id"]: row for row in csv.DictReader(handle)}


def reset() -> None:
    """Start a fresh coverage sheet for a new independent run."""
    paths.COVERAGE.mkdir(parents=True, exist_ok=True)
    if paths.COVERAGE_CSV.exists():
        paths.COVERAGE_CSV.unlink()


def _annotation_path(item: manifest.ImageItem) -> Path | None:
    path = paths.ANNOTATIONS / item.label / f"{item.image_id}.json"
    return path if path.exists() else None


def _repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(paths.ROOT))
    except ValueError:
        return str(path)


def _read_annotation(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        LOG.warning("malformed annotation: %s", path)
        return {}


def _annotation_difficulty(payload: dict) -> str:
    return str(payload.get("difficulty", ""))


def _has_normalized_bbox(payload: dict) -> bool:
    bbox = payload.get("subject_bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    try:
        left, top, right, bottom = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return False
    return (
        0.0 <= left < right <= 1.0
        and 0.0 <= top < bottom <= 1.0
    )


def _has_complete_annotation(payload: dict) -> str:
    if not payload:
        return "no"
    if not _has_normalized_bbox(payload):
        return "no"
    if not payload.get("cot"):
        return "no"
    return "yes"


def _finding_columns_for_label(memory: wiki.WikiMemory, label: str) -> List[str]:
    return memory.applicable_finding_columns(label)


def refresh(items: Iterable[manifest.ImageItem]) -> List[dict]:
    """Refresh coverage.csv while preserving existing done cells."""
    paths.COVERAGE.mkdir(parents=True, exist_ok=True)
    memory = wiki.load_wiki_memory()
    existing = _read_existing()
    all_finding_cols = memory.all_finding_columns()

    rows: List[dict] = []
    for item in items:
        old = existing.get(item.task_id, {})
        ann_path = _annotation_path(item)
        ann_payload = _read_annotation(ann_path)
        applicable = set(_finding_columns_for_label(memory, item.label))
        row = {
            "task_id": item.task_id,
            "image_id": item.image_id,
            "image_path": _repo_relative(item.image_path),
            "label": item.label,
            "gt_answer": item.gt_answer,
            "has_annotation": _has_complete_annotation(ann_payload),
            "difficulty": _annotation_difficulty(ann_payload),
        }
        for col in all_finding_cols:
            if col not in applicable:
                row[col] = "n/a"
            elif old.get(col) == "done":
                row[col] = "done"
            else:
                row[col] = "not_done"
        rows.append(row)

    rows.sort(key=lambda row: row["task_id"])
    _write_rows(rows, all_finding_cols)
    return rows


def mark_done(items: Iterable[manifest.ImageItem]) -> List[dict]:
    item_list = list(items)
    rows = refresh(manifest.iter_all())
    memory = wiki.load_wiki_memory()
    all_finding_cols = memory.all_finding_columns()
    done_by_task = {
        item.task_id: set(_finding_columns_for_label(memory, item.label))
        for item in item_list
    }

    for row in rows:
        for col in done_by_task.get(row["task_id"], set()):
            row[col] = "done"
    _write_rows(rows, all_finding_cols)
    return rows


def mark_not_done(task_ids: Iterable[str]) -> List[dict]:
    rows = refresh(manifest.iter_all())
    wanted = set(task_ids)
    memory = wiki.load_wiki_memory()
    all_finding_cols = memory.all_finding_columns()

    for row in rows:
        if row["task_id"] not in wanted:
            continue
        for col in _finding_columns_for_label(memory, row["label"]):
            row[col] = "not_done"
    _write_rows(rows, all_finding_cols)
    return rows


def find_not_done(rows: List[dict]) -> Dict[str, List[str]]:
    not_done: Dict[str, List[str]] = {}
    for row in rows:
        cols = [
            key
            for key, value in row.items()
            if key not in META_FIELDS and value == "not_done"
        ]
        if cols:
            not_done[row["task_id"]] = cols
    return not_done


def _write_rows(rows: List[dict], finding_cols: List[str]) -> None:
    with paths.COVERAGE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=META_FIELDS + finding_cols)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the live coverage sheet.")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="delete the existing coverage.csv before rebuilding it",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.fresh:
        reset()
    rows = refresh(manifest.iter_all())
    pending = find_not_done(rows)
    print(f"coverage rows: {len(rows)}")
    print(f"tasks with not_done cells: {len(pending)}")
    print(f"wrote: {paths.COVERAGE_CSV}")


if __name__ == "__main__":
    main()
