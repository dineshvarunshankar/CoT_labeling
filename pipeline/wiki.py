"""LLM wiki memory and Gemini maintainer support."""

from __future__ import annotations

import logging
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from . import paths

FRONTMATTER_DELIM = "---"
LOG = logging.getLogger(__name__)
FINDING_HEADING_RE = re.compile(r"^###\s+(\d{3})\s+-\s+.+$", re.MULTILINE)


@dataclass
class WikiPage:
    path: Path
    frontmatter: Dict
    body: str

    @property
    def page_id(self) -> str:
        return str(self.frontmatter.get("id") or self.path.stem)

    def to_text(self) -> str:
        return _serialize(self.frontmatter, self.body)

    def finding_ids(self) -> List[str]:
        """Stable numbered findings declared inside this markdown page."""
        ids = FINDING_HEADING_RE.findall(self.body)
        duplicates = sorted({finding_id for finding_id in ids if ids.count(finding_id) > 1})
        if duplicates:
            joined = ", ".join(duplicates)
            raise ValueError(f"duplicate finding id(s) in {self.path}: {joined}")
        return sorted(ids)

    def human_finding_ids(self) -> List[str]:
        """Numbered findings under ## Human Findings."""
        parts = self.body.split("## Agent Findings")
        human_body = parts[0]
        return sorted(FINDING_HEADING_RE.findall(human_body))

    def agent_finding_ids(self) -> List[str]:
        """Numbered findings under ## Agent Findings."""
        parts = self.body.split("## Agent Findings")
        if len(parts) < 2:
            return []
        agent_body = parts[1]
        return sorted(FINDING_HEADING_RE.findall(agent_body))


@dataclass
class WikiMemory:
    category_defs: Dict[str, WikiPage] = field(default_factory=dict)
    general_pages: Dict[str, WikiPage] = field(default_factory=dict)
    glossary: Optional[WikiPage] = None

    def applicable_finding_columns(self, label: str) -> List[str]:
        cols = general_finding_columns(self.general_pages)
        category = self.category_defs.get(label)
        if category is not None:
            cols.extend(category_finding_columns(label, category))
        return cols

    def all_finding_columns(self) -> List[str]:
        cols = general_finding_columns(self.general_pages)
        for label, page in sorted(self.category_defs.items()):
            cols.extend(category_finding_columns(label, page))
        return cols


def _split_frontmatter(text: str) -> tuple[Dict, str]:
    if not text.startswith(FRONTMATTER_DELIM):
        return {}, text
    rest = text[len(FRONTMATTER_DELIM):]
    end = rest.find(f"\n{FRONTMATTER_DELIM}")
    if end < 0:
        return {}, text
    yaml_block = rest[:end]
    body = rest[end + len(f"\n{FRONTMATTER_DELIM}"):]
    if body.startswith("\n"):
        body = body[1:]
    return yaml.safe_load(yaml_block) or {}, body


def _serialize(frontmatter: Dict, body: str) -> str:
    if not frontmatter:
        return body
    fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"{FRONTMATTER_DELIM}\n{fm_yaml}\n{FRONTMATTER_DELIM}\n\n{body.lstrip()}"


def read_page(path: Path) -> WikiPage:
    fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return WikiPage(path=path, frontmatter=fm, body=body)


def list_pages(root: Path, *, recursive: bool = False) -> List[WikiPage]:
    out: List[WikiPage] = []
    pattern = "**/*.md" if recursive else "*.md"
    for path in sorted(root.glob(pattern)):
        if path.name.startswith("_"):
            continue
        out.append(read_page(path))
    return out


def general_finding_columns(pages: Dict[str, WikiPage]) -> List[str]:
    cols: List[str] = []
    for page_id, page in sorted(pages.items()):
        for finding_id in page.finding_ids():
            cols.append(f"general/{page_id}/{finding_id}")
    return cols


def category_finding_columns(label: str, page: WikiPage) -> List[str]:
    return [f"categories/{label}/{finding_id}" for finding_id in page.finding_ids()]


def load_wiki_memory() -> WikiMemory:
    category_defs = {
        page.path.stem: page for page in list_pages(paths.WIKI_CATEGORIES)
    }

    return WikiMemory(
        category_defs=category_defs,
        general_pages={
            page.path.stem: page
            for page in list_pages(paths.WIKI_GENERAL, recursive=True)
        },
        glossary=read_page(paths.WIKI_GLOSSARY) if paths.WIKI_GLOSSARY.exists() else None,
    )


def coverage_columns() -> List[str]:
    """All stable coverage columns created by numbered wiki findings."""
    return load_wiki_memory().all_finding_columns()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_annotation_prompt(item, memory: WikiMemory) -> str:
    """Build the prompt for one annotation task."""
    parts: List[str] = [
        "# Triage CoT Annotation",
        (
            "You are in Annotation Mode. Read the contract, the current wiki memory, "
            "and the per-task context. Then emit one clean JSON annotation."
        ),
        "The image is provided separately. Use the target subject bbox as the main region of interest.",
        "\n---\n# CONTRACT\n",
        _read_text(paths.AGENTS_MD),
        "\n---\n# PROMPT\n",
        _read_text(paths.PROMPT),
        "\n---\n# OUTPUT JSON SCHEMA\n",
        _read_text(paths.ANNOTATION_SCHEMA),
        "\n---\n# GLOSSARY\n",
    ]

    if memory.glossary:
        parts.append(memory.glossary.to_text())

    parts.append("\n---\n# ACTIVE CATEGORY DEFINITION\n")
    category = memory.category_defs.get(item.label)
    if category is None:
        parts.append(f"(no wiki/categories/{item.label}.md page found)")
    else:
        parts.append(category.to_text())

    parts.append("\n---\n# GENERAL WIKI PAGES\n")
    if memory.general_pages:
        for page_id in sorted(memory.general_pages):
            parts.append(f"## general/{page_id}\n")
            parts.append(memory.general_pages[page_id].to_text())
            parts.append("")
    else:
        parts.append("(no wiki/general pages yet)")

    parts.extend(
        [
            "\n---\n# PER-IMAGE CONTEXT\n",
            f"image_id: {item.image_id}",
            f"image_path: {item.image_path}",
            f"label: {item.label}",
            f"question: {item.question}",
            f"ground_truth_answer: {item.gt_answer}",
            f"target_subject_bbox: {item.bbox}",
            "modality_instruction: decide rgb vs thermal from the image itself",
            "\n---\n# YOUR TASK\n",
            (
                "Emit exactly one valid annotation JSON object. Do not include prose "
                "or markdown fences. Explain the ground_truth_answer above; do not predict a new label."
            ),
        ]
    )
    return "\n".join(parts)


def build_maintainer_prompt(annotation_payloads: List[dict], *, round_idx: int) -> str:
    memory = load_wiki_memory()
    labels = sorted({str(ann.get("label", "")) for ann in annotation_payloads if ann.get("label")})
    parts: List[str] = [
        "# Triage Wiki Maintenance",
        f"round: {round_idx}",
        "\n---\n# CONTRACT\n",
        _read_text(paths.AGENTS_MD),
        "\n---\n# MAINTAINER PROMPT\n",
        _read_text(paths.PROMPT_WIKI_MAINTAINER),
        "\n---\n# OUTPUT JSON SCHEMA\n",
        _read_text(paths.WIKI_MAINTAINER_SCHEMA),
        "\n---\n# GLOSSARY\n",
    ]

    if memory.glossary:
        parts.append(memory.glossary.to_text())

    parts.append("\n---\n# GENERAL WIKI PAGES\n")
    for page_id in sorted(memory.general_pages):
        parts.append(f"## wiki/general/{page_id}.md\n")
        parts.append(memory.general_pages[page_id].to_text())
        parts.append("")

    parts.append("\n---\n# RELEVANT CATEGORY PAGES\n")
    for label in labels:
        page = memory.category_defs.get(label)
        if page is not None:
            parts.append(f"## wiki/categories/{label}.md\n")
            parts.append(page.to_text())
            parts.append("")

    parts.extend(
        [
            "\n---\n# ROUND ANNOTATIONS\n",
            json.dumps(annotation_payloads, indent=2, ensure_ascii=False),
            "\n---\n# YOUR TASK\n",
            "Return exactly one JSON object. Use an empty findings array when no new reusable finding is needed.",
        ]
    )
    return "\n".join(parts)


def run_maintainer(client, annotation_payloads: List[dict], *, round_idx: int) -> int:
    if not annotation_payloads:
        LOG.info("wiki maintainer: no new annotations to review")
        regenerate_index()
        return 0

    prompt = build_maintainer_prompt(annotation_payloads, round_idx=round_idx)
    result = client.generate_text(
        prompt,
        response_json_schema=_read_json(paths.WIKI_MAINTAINER_SCHEMA),
    )
    raw_text = result.text or ""
    _save_maintainer_raw(round_idx, raw_text)
    findings = _parse_maintainer_response(raw_text)
    LOG.info("wiki maintainer: proposed %d finding(s)", len(findings))
    added = apply_findings(findings, round_idx=round_idx)
    regenerate_index()
    return added


def _save_maintainer_raw(round_idx: int, raw_text: str) -> None:
    out_dir = paths.OUTPUTS / "maintainer"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"round_{round_idx:02d}.json"
    out_path.write_text(raw_text, encoding="utf-8")
    LOG.info("wiki maintainer: raw response saved to %s", out_path.relative_to(paths.ROOT))


def _parse_maintainer_response(raw_text: str) -> List[dict]:
    cleaned = raw_text.strip()
    if not cleaned:
        LOG.warning("wiki maintainer: empty response; treating as no findings")
        return []
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as e:
        LOG.warning(
            "wiki maintainer: invalid JSON (%s); treating as no findings. "
            "Inspect outputs/maintainer/round_*.json for the raw response.",
            e,
        )
        return []

    findings = payload.get("findings") if isinstance(payload, dict) else None
    if not isinstance(findings, list):
        LOG.warning(
            "wiki maintainer: response missing findings array; treating as no findings"
        )
        return []
    return [finding for finding in findings if isinstance(finding, dict)]


def _target_page(value: str) -> Path | None:
    path = (paths.ROOT / value).resolve()
    try:
        path.relative_to(paths.WIKI.resolve())
    except ValueError:
        return None
    if path.suffix != ".md" or not path.exists():
        return None
    if path.parent not in {paths.WIKI_GENERAL.resolve(), paths.WIKI_CATEGORIES.resolve()}:
        return None
    return path


def _next_finding_id(path: Path) -> str:
    page = read_page(path)
    ids = [int(finding_id) for finding_id in page.finding_ids()]
    return f"{(max(ids) if ids else 0) + 1:03d}"


def _covered_by_existing(path: Path, title: str, body: str) -> bool:
    existing = path.read_text(encoding="utf-8").lower()
    title_norm = " ".join(title.lower().split())
    body_norm = " ".join(body.lower().split())
    return bool(title_norm and title_norm in existing) or bool(body_norm and body_norm in existing)


def _append_finding(path: Path, title: str, body: str) -> str:
    finding_id = _next_finding_id(path)
    text = path.read_text(encoding="utf-8").rstrip()
    if "## Agent Findings" not in text:
        text += "\n\n## Agent Findings"

    block = (
        f"\n\n### {finding_id} - {title.strip()}\n\n"
        f"{body.strip()}\n"
    )
    path.write_text(text + block, encoding="utf-8")
    return finding_id


def _append_finding_log(path: Path, finding_id: str, title: str, sources: List[str]) -> None:
    paths.WIKI_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not paths.WIKI_LOG.exists():
        paths.WIKI_LOG.write_text("# Wiki Log\n\n## Entries\n", encoding="utf-8")

    rel_path = path.relative_to(paths.ROOT)
    target = rel_path.with_suffix("").as_posix().replace("wiki/", "")
    source_line = ", ".join(sources) if sources else "none"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n## [{timestamp}] finding_added | {target}/{finding_id}\n\n"
        f"- Summary: {title.strip()}\n"
        f"- Sources: {source_line}\n"
        f"- Pages touched: {rel_path.as_posix()}\n"
    )
    with paths.WIKI_LOG.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def apply_findings(findings: List[dict], *, round_idx: int) -> int:
    added = 0
    skipped = 0
    for finding in findings:
        target = _target_page(str(finding.get("target_page", "")))
        title = str(finding.get("title", "")).strip()
        body = str(finding.get("body", "")).strip()
        raw_sources = finding.get("sources", [])
        sources = [str(source).strip() for source in raw_sources if str(source).strip()] if isinstance(raw_sources, list) else []

        if target is None or not title or not body:
            LOG.warning("wiki maintainer: skipped malformed finding in round %d", round_idx)
            skipped += 1
            continue
        if _covered_by_existing(target, title, body):
            LOG.info("wiki maintainer: skipped duplicate finding for %s", target.relative_to(paths.ROOT))
            skipped += 1
            continue

        finding_id = _append_finding(target, title, body)
        _append_finding_log(target, finding_id, title, sources)
        LOG.info(
            "wiki maintainer: added %s/%s to %s",
            target.relative_to(paths.ROOT).with_suffix("").as_posix().replace("wiki/", ""),
            finding_id,
            target.relative_to(paths.ROOT),
        )
        added += 1

    LOG.info("wiki maintainer: added=%d skipped=%d", added, skipped)
    return added


def regenerate_index() -> None:
    memory = load_wiki_memory()
    general_descriptions = {
        "common": "modality-independent findings that apply across labels",
        "rgb": "visible-light evidence, color, surface detail, and RGB image degradation",
        "thermal": "thermal contrast, heat continuity, and thermal-specific limitations",
        "subject_types": "subject type cues that affect posture and triage interpretation",
    }
    lines = [
        "# Triage Wiki Index",
        "",
        "Navigation for the Triage Wiki maintainer.",
        "",
        "This wiki is persistent memory for dense-CoT triage annotation. It is",
        "regenerated by the pipeline after wiki maintenance. Read `AGENTS.md` for",
        "operating rules and `prompts/wiki_maintainer.md` before editing wiki memory.",
        "",
        "## General Pages",
        "",
        "General findings apply to every task.",
        "",
    ]
    if memory.general_pages:
        for page_id in sorted(memory.general_pages):
            page = memory.general_pages[page_id]
            description = general_descriptions.get(page_id, "general reusable findings")
            count = len(page.finding_ids())
            suffix = "finding" if count == 1 else "findings"
            lines.append(
                f"- [[general/{page_id}]]: {description} "
                f"({count} {suffix})."
            )
    else:
        lines.append("- None yet.")

    lines.extend(["", "## Categories", "", "Category findings apply only to that label/question.", ""])
    for label in sorted(memory.category_defs):
        page = memory.category_defs[label]
        title = page.frontmatter.get("title") or label
        question = page.frontmatter.get("question") or ""
        summary = f"{title}"
        if question:
            summary = f"{summary}: {question}"
        lines.append(f"- [[categories/{label}]]: {summary}")

    lines.extend(
        [
            "",
            "## Prompts and Schema",
            "",
            "- `AGENTS.md`: repository operating schema.",
            "- `prompts/prompt.md`: Gemini annotation behavior.",
            "- `prompts/annotation_schema.json`: annotation structured output schema.",
            "- `prompts/wiki_maintainer.md`: round-boundary maintainer behavior.",
            "- `prompts/wiki_maintainer_schema.json`: maintainer structured output schema.",
            "",
            "## Generated State",
            "",
            "- `wiki/coverage/coverage.csv`: live numbered-finding coverage matrix.",
            "- `wiki/log.md`: chronological wiki maintenance log.",
        ]
    )

    paths.WIKI_INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
