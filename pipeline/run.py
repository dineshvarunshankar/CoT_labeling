"""Autonomous round-based labeling pipeline.

The loop is driven by two signals:
    1. annotate any task that is missing or has any `not_done` cell;
    2. after the maintainer phase, only continue if new finding columns appear.

Editing the wording of an existing finding does not create a new coverage
column. A new numbered finding does, and coverage requeues applicable tasks.
"""

from __future__ import annotations

import argparse
from collections import Counter
import logging
import json
import os
from typing import Iterable, List

from . import annotate, coverage, export, manifest, paths, wiki
from .gemini import GeminiClient

LOG = logging.getLogger(__name__)


def _apply_limit(
    items: List[manifest.ImageItem], limit: int | None
) -> List[manifest.ImageItem]:
    if limit is None:
        return items
    return items[:limit]


def _tasks_from_ids(
    items: Iterable[manifest.ImageItem], task_ids: Iterable[str]
) -> List[manifest.ImageItem]:
    wanted = set(task_ids)
    return [item for item in items if item.task_id in wanted]


def _pending_task_ids(rows: List[dict]) -> List[str]:
    not_done = set(coverage.find_not_done(rows))
    missing_annotation = {row["task_id"] for row in rows if row["has_annotation"] != "yes"}
    return sorted(not_done | missing_annotation)


def _label_counts(items: List[manifest.ImageItem]) -> str:
    counts = Counter(item.label for item in items)
    return ", ".join(f"{label}={count}" for label, count in sorted(counts.items()))


def _read_pending_maintenance() -> set[str]:
    path = paths.OUTPUTS / "maintainer" / "pending.json"
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(value, str) for value in payload):
        raise ValueError(f"Invalid pending maintenance state: {path}")
    return set(payload)


def _write_pending_maintenance(task_ids: set[str]) -> None:
    path = paths.OUTPUTS / "maintainer" / "pending.json"
    if not task_ids:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(task_ids)), encoding="utf-8")
    temporary.replace(path)


def _saved_annotations(items: List[manifest.ImageItem], task_ids: set[str]) -> List[dict]:
    payloads = []
    for item in items:
        if item.task_id in task_ids:
            path = paths.COT_ANNOTATIONS / item.label / f"{item.image_id}.json"
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def run(
    labels: list[str] | None = None,
    limit: int | None = None,
    max_rounds: int = 3,
    skip_wiki_maintainer: bool = False,
    fresh_coverage: bool = False,
    data_dir: str | None = None,
    split: str | None = None,
) -> dict:
    paths.set_split(split)

    paths.ensure_dirs()

    if fresh_coverage:
        coverage.reset()

    selected_items = _apply_limit(manifest.collect_items(labels, data_dir=data_dir), limit)

    LOG.info(
        "run start: labels=%s total_tasks=%d max_rounds=%d wiki_maintainer=%s",
        ",".join(labels) if labels else "all",
        len(selected_items),
        max_rounds,
        "off" if skip_wiki_maintainer else "on",
    )
    LOG.info("task mix: %s", _label_counts(selected_items) or "none")

    client = GeminiClient()
    selected_ids = {item.task_id for item in selected_items}
    pending_maintenance = _read_pending_maintenance()

    total_processed = 0
    converged = False
    rounds_completed = 0

    for round_idx in range(1, max_rounds + 1):
        rows = coverage.refresh(selected_items)
        queue = _tasks_from_ids(selected_items, _pending_task_ids(rows))
        complete_count = len(selected_items) - len(queue)
        rounds_completed = round_idx

        if not queue and not (pending_maintenance & selected_ids):
            LOG.info(
                "round %d/%d: queue empty; complete=%d/%d; converged",
                round_idx,
                max_rounds,
                complete_count,
                len(selected_items),
            )
            converged = True
            break

        LOG.info(
            "round %d/%d: pending=%d complete=%d/%d; annotating queued tasks",
            round_idx,
            max_rounds,
            len(queue),
            complete_count,
            len(selected_items),
        )
        if queue and not skip_wiki_maintainer:
            pending_maintenance.update(item.task_id for item in queue)
            _write_pending_maintenance(pending_maintenance)
        annotations = annotate.annotate_many(
            queue,
            client=client,
            force=True,
            reload_wiki_each_call=False,
        ) if queue else []
        total_processed += len(annotations)
        LOG.info(
            "round %d/%d: annotation pass wrote=%d/%d",
            round_idx,
            max_rounds,
            len(annotations),
            len(queue),
        )

        if skip_wiki_maintainer:
            LOG.info("round %d/%d: skipping wiki-maintainer phase", round_idx, max_rounds)
            converged = True
            break

        incomplete = set(_pending_task_ids(coverage.refresh(selected_items)))
        reviewed_ids = (pending_maintenance & selected_ids) - incomplete
        payloads = _saved_annotations(selected_items, reviewed_ids)
        columns_before = set(wiki.coverage_columns())
        LOG.info(
            "round %d/%d: wiki maintainer reviewing %d annotation(s)",
            round_idx,
            max_rounds,
            len(payloads),
        )
        wiki.run_maintainer(
            client,
            payloads,
            round_idx=round_idx,
        )
        pending_maintenance.difference_update(reviewed_ids)
        _write_pending_maintenance(pending_maintenance)
        columns_after = set(wiki.coverage_columns())

        if columns_after == columns_before:
            LOG.info(
                "round %d/%d: maintainer added 0 new finding(s); converged",
                round_idx,
                max_rounds,
            )
            converged = True
            break

        added = sorted(columns_after - columns_before)
        LOG.info(
            "round %d/%d: maintainer added %d new finding(s): %s",
            round_idx,
            max_rounds,
            len(added),
            ", ".join(added),
        )
        LOG.info(
            "round %d/%d: refreshed coverage will requeue affected tasks next round",
            round_idx,
            max_rounds,
        )

    coverage_rows = coverage.refresh(selected_items)
    remaining = _pending_task_ids(coverage_rows)
    export_summary: dict = {}
    if converged and not remaining:
        export_summary = export.export(task_ids=[item.task_id for item in selected_items])
        LOG.info(
            "run complete: rounds=%d processed_annotations=%d pending=0 exported=%s",
            rounds_completed,
            total_processed,
            export_summary,
        )
    else:
        LOG.warning(
            "run stopped incomplete: rounds=%d processed_annotations=%d pending=%d exported=no",
            rounds_completed,
            total_processed,
            len(remaining),
        )

    return {
        "processed_annotations": total_processed,
        "coverage_rows": len(coverage_rows),
        "pending_tasks": len(remaining),
        "converged": converged,
        "rounds_completed": rounds_completed,
        "dataset": export_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the autonomous triage labeling loop.")
    parser.add_argument("--label", action="append", help="restrict to one or more labels")
    parser.add_argument("--limit", type=int, default=None, help="limit first-round tasks")
    parser.add_argument("--max-rounds", type=int, default=3, help="maximum annotation/requeue rounds")
    parser.add_argument(
        "--fresh-coverage",
        action="store_true",
        help="start this run with a newly rebuilt coverage.csv",
    )
    parser.add_argument(
        "--skip-wiki-maintainer",
        action="store_true",
        help="debug only: annotate without the wiki-maintainer phase",
    )
    parser.add_argument("--data-dir", type=str, default=None, help="override the input data directory")
    parser.add_argument("--split", type=str, default=None, help="process a specific data split (e.g. 01_05_26)")
    args = parser.parse_args()



    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    third_party_level = os.environ.get("THIRD_PARTY_LOG_LEVEL", "WARNING")
    for logger_name in ("openai", "httpx"):
        logging.getLogger(logger_name).setLevel(third_party_level)

    summary = run(
        labels=args.label,
        limit=args.limit,
        max_rounds=args.max_rounds,
        skip_wiki_maintainer=args.skip_wiki_maintainer,
        fresh_coverage=args.fresh_coverage,
        data_dir=args.data_dir,
        split=args.split,
    )


    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
