"""Export clean annotations to SFT/RLVR JSONL."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable, List

from . import coverage, paths

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
        "subject_bbox": ann.get("subject_bbox"),
        "modality": ann["modality"],
        "difficulty": ann["difficulty"],
    }


def _iter_annotations() -> Iterable[dict]:
    if not paths.ANNOTATIONS.exists():
        return
    for path in sorted(paths.ANNOTATIONS.rglob("*.json")):
        try:
            yield json.loads(path.read_text())
        except json.JSONDecodeError as e:
            LOG.warning("skipping %s: %s", path, e)


def export() -> dict:
    paths.DATASET.mkdir(parents=True, exist_ok=True)
    sft: List[dict] = []
    rlvr: List[dict] = []

    for ann in _iter_annotations():
        row = _row(ann)
        if row["difficulty"] == "easy":
            sft.append(row)
        else:
            rlvr.append(row)

    _write_jsonl(paths.DATASET_SFT, sft)
    _write_jsonl(paths.DATASET_RLVR, rlvr)

    summary = {"sft": len(sft), "rlvr": len(rlvr)}
    LOG.info("exported %s", summary)
    return summary


def _write_jsonl(path: Path, rows: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    argparse.ArgumentParser().parse_args()
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(export(), indent=2))


if __name__ == "__main__":
    main()
