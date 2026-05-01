# AGENTS.md - Triage Wiki Operating Schema

This file is the operating schema for agents working in this repository. It
defines the repository layers, the two agent modes, and the bookkeeping rules
that keep annotation, wiki memory, coverage, and dataset export consistent.

## Mission

Build dense, grounded chain-of-thought annotations for triage images using a
markdown wiki as persistent model memory.

The annotation model explains existing ground-truth answers. It does not create
new labels. The wiki-maintainer agent turns reusable observations from completed
annotations into numbered wiki findings that future rounds can use.

## Repository Layers

- `exports/`: input manifests and images. Treat as read-only source material.
- `wiki/`: persistent memory. Human findings and agent findings live here.
- `wiki/index.md`: compact navigation surface for the maintainer agent.
- `wiki/log.md`: append-only timeline of wiki changes.
- `wiki/glossary.md`: shared vocabulary for tasks, findings, coverage, and
  annotation outputs.
- `wiki/coverage/coverage.csv`: generated requeue sheet. Do not hand-edit.
- `outputs/annotations/`: generated per-task annotation JSON.
- `outputs/dataset/`: generated SFT/RLVR JSONL exports.
- `prompts/prompt.md`: Gemini image annotation prompt.
- `prompts/wiki_maintainer.md`: wiki-maintainer prompt.

## Runtime Model

The pipeline runs in rounds.

1. Load the current wiki once.
2. Annotate all pending tasks using that same wiki state.
3. Run the Gemini wiki-maintainer pass.
4. If new numbered findings were added, refresh coverage and run another round.
5. If no new finding was added, the loop converges and exports the dataset.

## Annotation Mode

Annotation Mode is executed by the Gemini API through `pipeline.run` and
`pipeline.annotate`.

The prompt is assembled from:

- this file;
- `prompts/prompt.md`;
- `prompts/annotation_schema.json`;
- `wiki/glossary.md`;
- the active category page;
- all general wiki pages;
- per-task image/question/GT context.

The model must emit exactly one JSON object matching
`prompts/annotation_schema.json`.

The pipeline injects image/task provenance into the saved annotation. Gemini
does not output `image_id`, `image_path`, `label`, `question`, `gt_answer`, or
other task metadata.

Annotation Mode must not edit the wiki or emit wiki-update proposals.

## Wiki-Maintainer Mode

Wiki-Maintainer Mode is executed by a Gemini text-only call inside
`pipeline.run`.

Gemini receives `prompts/wiki_maintainer.md`, the current wiki pages, the round
annotations, and `prompts/wiki_maintainer_schema.json`. It returns proposed
findings as JSON. The pipeline applies accepted findings to markdown, logs the
change, regenerates `wiki/index.md`, and refreshes coverage.

The maintainer should follow `prompts/wiki_maintainer.md` exactly.
Before adding any finding, it must compare the candidate idea against existing
`## Human Findings` and `## Agent Findings` on the relevant page. Do not add a
duplicate finding if the idea is already represented, even with different
wording.

Allowed proposed targets:

- `wiki/general/*.md`
- `wiki/categories/<label>.md`

Forbidden proposals:

- do not edit `outputs/annotations/`;
- do not change ground-truth answers;
- do not edit generated datasets;
- do not propose changes to `## Human Findings`;
- do not propose changes to `wiki/index.md`;
- do not propose changes to `wiki/coverage/coverage.csv`.

## Wiki Page Format

Runtime wiki pages contain memory only, not operating instructions.

General pages:

```markdown
---
id: thermal
scope: general
---

# thermal

## Human Findings

### 001 - Human-authored reusable guidance

...

## Agent Findings

### 002 - Agent-authored reusable guidance

...
```

Category pages:

```markdown
---
id: amputation_arm
title: Arm Amputation
question: "Does the subject shown in the green box appear to have an arm amputation from what you see in the frame?"
---

# amputation_arm

## Human Findings

### 001 - Human-authored category guidance

...

## Agent Findings
```

Finding rules:

- headings must use exactly `### NNN - Short title`;
- IDs are unique within a page;
- IDs are never renumbered;
- `wiki/general/common.md` findings apply across labels and modalities;
- `wiki/general/rgb.md`, `wiki/general/thermal.md`, and
  `wiki/general/subject_types.md` findings apply across labels within that
  broad context;
- category findings apply only to that category/question;
- place each finding at the broadest correct scope and do not duplicate common
  ideas across RGB, thermal, and category pages;
- one finding should express one reusable idea;
- do not write sources inside findings. Sources belong in `wiki/log.md`.

## Coverage

Coverage columns are built from numbered finding headings.

Examples:

- `general/thermal/001`
- `general/rgb/002`
- `categories/amputation_arm/001`

Rows are tasks. Cells are:

- `done`: task was annotated with that finding in the prompt;
- `not_done`: task must be re-annotated with that finding in the prompt;
- `n/a`: finding does not apply to that task.

Adding a new finding creates a new column. Editing text under an existing
finding does not create a new column.

## Index and Log

`wiki/index.md` is the maintainer's navigation surface. It is regenerated by
the pipeline after wiki maintenance, not manually edited by the maintainer.

`wiki/log.md` is append-only. Each maintainer pass that changes the wiki should
append an entry with the operation, target, summary, sources, and pages touched.
