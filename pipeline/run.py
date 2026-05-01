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


def run(
    labels: list[str] | None = None,
    limit: int | None = None,
    max_rounds: int = 3,
    skip_wiki_maintainer: bool = False,
    fresh_coverage: bool = False,
) -> dict:
    paths.ensure_dirs()
    if fresh_coverage:
        coverage.reset()

    selected_items = _apply_limit(manifest.collect_items(labels), limit)
    LOG.info(
        "run start: labels=%s total_tasks=%d max_rounds=%d wiki_maintainer=%s",
        ",".join(labels) if labels else "all",
        len(selected_items),
        max_rounds,
        "off" if skip_wiki_maintainer else "gemini",
    )
    LOG.info("task mix: %s", _label_counts(selected_items) or "none")

    client = GeminiClient()

    total_processed = 0
    converged = False
    rounds_completed = 0

    for round_idx in range(1, max_rounds + 1):
        rows = coverage.refresh(selected_items)
        queue = _tasks_from_ids(selected_items, _pending_task_ids(rows))
        complete_count = len(selected_items) - len(queue)
        rounds_completed = round_idx

        if not queue:
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
        annotations = annotate.annotate_many(
            queue,
            client=client,
            force=True,
            reload_wiki_each_call=False,
        )
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

        columns_before = set(wiki.coverage_columns())
        LOG.info(
            "round %d/%d: wiki maintainer reviewing %d annotation(s)",
            round_idx,
            max_rounds,
            len(annotations),
        )
        wiki.run_maintainer(
            client,
            [ann.to_dict() for ann in annotations],
            round_idx=round_idx,
        )
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
        export_summary = export.export()
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
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    third_party_level = os.environ.get("THIRD_PARTY_LOG_LEVEL", "WARNING")
    for logger_name in ("google_genai.models", "httpx"):
        logging.getLogger(logger_name).setLevel(third_party_level)

    summary = run(
        labels=args.label,
        limit=args.limit,
        max_rounds=args.max_rounds,
        skip_wiki_maintainer=args.skip_wiki_maintainer,
        fresh_coverage=args.fresh_coverage,
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
