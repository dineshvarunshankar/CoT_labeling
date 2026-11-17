"""Export completed annotations to SFT/RLVR JSONL."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable

from . import coverage, paths, wiki
from .validation import is_complete_annotation

LOG = logging.getLogger(__name__)


def _row(ann: dict) -> dict:
    return {
        "image": ann["image_path"],
        "task_id": coverage.task_id(ann["label"], ann["image_id"]),
        "image_id": ann["image_id"],
        "label": ann["label"],
        "question": ann["question"],
        "answer": ann["gt_answer"],
        "cot": ann["cot"],
        "subject_bbox": ann["subject_bbox"],
        "modality": ann["modality"],
        "difficulty": ann["difficulty"],
    }


def export(task_ids: Iterable[str] | None = None) -> dict:
    """Export selected tasks, or all recorded tasks, after coverage validation."""
    recorded = coverage._read_existing()
    if not recorded:
        raise ValueError("No coverage records found. Run the annotation pipeline before exporting.")
    selected = sorted(set(recorded if task_ids is None else task_ids))
    pending_path = paths.OUTPUTS / "maintainer" / "pending.json"
    if pending_path.exists():
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        if not isinstance(pending, list) or any(not isinstance(value, str) for value in pending):
            raise ValueError(f"Invalid pending maintenance state: {pending_path}")
        if set(selected).intersection(pending):
            raise ValueError("Selected tasks have unfinished wiki maintenance. Resume the pipeline before exporting.")
    memory = wiki.load_wiki_memory()
    sft: list[dict] = []
    rlvr: list[dict] = []

    for task_id in selected:
        state = recorded.get(task_id)
        if state is None:
            raise ValueError(f"Task has no coverage record: {task_id}")
        columns = memory.applicable_finding_columns(state["label"])
        if state.get("has_annotation") != "yes" or any(state.get(col) != "done" for col in columns):
            raise ValueError(f"Task needs annotation with the current wiki: {task_id}")
        source = paths.COT_ANNOTATIONS / state["label"] / f"{state['image_id']}.json"
        try:
            ann = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read annotation for {task_id}: {source}") from exc
        if not is_complete_annotation(ann):
            raise ValueError(f"Invalid annotation for {task_id}")
        for field in ("image_id", "image_path", "label", "gt_answer"):
            if ann.get(field) != state.get(field):
                raise ValueError(f"Annotation {field} does not match coverage for {task_id}")
        if not isinstance(ann.get("question"), str):
            raise ValueError(f"Annotation question is missing for {task_id}")
        row = _row(ann)
        (sft if row["difficulty"] == "easy" else rlvr).append(row)

    # Validate the entire selection before replacing either dataset.
    _write_jsonl(paths.DATASET_SFT, sft)
    _write_jsonl(paths.DATASET_RLVR, rlvr)
    summary = {"sft": len(sft), "rlvr": len(rlvr)}
    LOG.info("exported %s", summary)
    return summary


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export tasks with complete coverage.")
    parser.add_argument("--split", help="Export a specific data split")
    args = parser.parse_args()
    paths.set_split(args.split)
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(export(), indent=2))


if __name__ == "__main__":
    main()
