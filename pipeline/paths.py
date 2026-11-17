"""Shared input, wiki, and output paths."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPORTS = ROOT / "exports"
DATA = ROOT / "data"

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

# Coverage tracks tasks against the current numbered findings.
WIKI_COVERAGE = WIKI / "coverage"

# Generated model outputs.
OUTPUTS = ROOT / "outputs"
COT_ANNOTATIONS = OUTPUTS / "cot_annotations"

COVERAGE = WIKI_COVERAGE
COVERAGE_CSV = COVERAGE / "coverage.csv"

DATASET_SFT = COT_ANNOTATIONS / "sft.jsonl"
DATASET_RLVR = COT_ANNOTATIONS / "rlvr.jsonl"


def set_split(split_name: str | None) -> None:
    """Select split paths, or restore the default layout with None."""
    global DATA, EXPORTS, OUTPUTS, COT_ANNOTATIONS, DATASET_SFT, DATASET_RLVR
    global COVERAGE, COVERAGE_CSV

    DATA = ROOT / "data"
    OUTPUTS = ROOT / "outputs"
    if split_name:
        DATA = DATA / split_name
        OUTPUTS = OUTPUTS / split_name
    EXPORTS = DATA / "exports" if split_name else ROOT / "exports"
    COT_ANNOTATIONS = OUTPUTS / "cot_annotations"
    DATASET_SFT = COT_ANNOTATIONS / "sft.jsonl"
    DATASET_RLVR = COT_ANNOTATIONS / "rlvr.jsonl"
    COVERAGE = OUTPUTS / "coverage" if split_name else WIKI_COVERAGE
    COVERAGE_CSV = COVERAGE / "coverage.csv"


AGENTS_MD = ROOT / "AGENTS.md"


def ensure_dirs() -> None:
    """Idempotently create the run-time output directories."""
    for p in (
        PROMPTS,
        WIKI_GENERAL,
        WIKI_CATEGORIES,
        COT_ANNOTATIONS,
        COVERAGE,
    ):
        p.mkdir(parents=True, exist_ok=True)
