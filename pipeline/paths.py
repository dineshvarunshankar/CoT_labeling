"""Centralized filesystem layout.

Every other pipeline module imports from here, so directory structure changes
only need to be made in this file.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPORTS = ROOT / "exports"
WIKI = ROOT / "wiki"
WIKI_CATEGORIES = WIKI / "categories"
WIKI_GENERAL = WIKI / "general"
WIKI_INDEX = WIKI / "index.md"
WIKI_LOG = WIKI / "log.md"
WIKI_GLOSSARY = WIKI / "glossary.md"

REFERENCE = ROOT / "reference"

PROMPTS = ROOT / "prompts"
PROMPT = PROMPTS / "prompt.md"
ANNOTATION_SCHEMA = PROMPTS / "annotation_schema.json"
PROMPT_WIKI_MAINTAINER = PROMPTS / "wiki_maintainer.md"
WIKI_MAINTAINER_SCHEMA = PROMPTS / "wiki_maintainer_schema.json"

# Generated coverage state. It lives next to the wiki because it tracks which
# tasks were annotated with the current numbered findings.
WIKI_COVERAGE = WIKI / "coverage"

# Generated model outputs.
OUTPUTS = ROOT / "outputs"
ANNOTATIONS = OUTPUTS / "annotations"

COVERAGE = WIKI_COVERAGE
COVERAGE_CSV = COVERAGE / "coverage.csv"

DATASET = OUTPUTS / "dataset"
DATASET_SFT = DATASET / "sft.jsonl"
DATASET_RLVR = DATASET / "rlvr.jsonl"

AGENTS_MD = ROOT / "AGENTS.md"


def ensure_dirs() -> None:
    """Idempotently create the run-time output directories."""
    for p in (
        PROMPTS,
        WIKI_GENERAL,
        WIKI_CATEGORIES,
        ANNOTATIONS,
        COVERAGE,
        DATASET,
    ):
        p.mkdir(parents=True, exist_ok=True)
