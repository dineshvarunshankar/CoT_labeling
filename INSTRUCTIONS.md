# Instructions

Operational behavior and semantics for the triage CoT labeling repository.
**Environment setup, `uv`, API keys, and all shell commands live in
`README.md`.**

## Runtime Model

The pipeline runs in rounds.

At the start of a round, the current wiki state is loaded once and inserted into
every annotation prompt for that round. The wiki is not reloaded after each
image.

After the annotation pass, the wiki-maintainer agent reviews the new
annotations. It edits the wiki only when it finds reusable guidance for future
images. New guidance is appended as a numbered finding inside an existing wiki
page. If no new finding is added, the loop stops. If a finding is added,
`coverage.csv` marks affected tasks as `not_done`, and the next round uses the
new wiki state.

```text
round N:
  load wiki state
  annotate pending tasks
  run wiki-maintainer
  if new finding added -> refresh coverage and run round N+1
  if no new finding -> export dataset
```

## Wiki Layout

The wiki is persistent model memory. It is read during annotation and maintained
between rounds.

```text
wiki/
├── index.md
├── log.md
├── glossary.md
├── general/
│   ├── common.md
│   ├── rgb.md
│   ├── thermal.md
│   └── subject_types.md
├── categories/
│   └── <label>.md
└── coverage/coverage.csv
```

Use `wiki/general/common.md` for modality-independent findings that apply across
labels. Use `wiki/general/rgb.md`, `wiki/general/thermal.md`, and
`wiki/general/subject_types.md` for broad findings that are specific to those
contexts.
Use `wiki/categories/<label>.md` for category definitions and numbered findings
that apply only to that specific label/question.

Runtime wiki pages contain only memory:

```markdown
## Human Findings
### 001 - Human-authored finding

## Agent Findings
### 002 - Maintainer-authored finding
```

Editing instructions live in `AGENTS.md` and `prompts/wiki_maintainer.md`, not
inside wiki pages.

## Annotation

The annotation pass produces one JSON file per image/category task.

```text
outputs/annotations/<label>/<image_id>.json
```

The annotation file stores the dense natural CoT and minimal task provenance. It
does not store wiki edits, rule coverage, or runtime audit metadata.

Required model output fields:

- `modality`
- `difficulty`
- `subject_bbox`
- `cot`

`modality` is part of the saved annotation and downstream export. The model
chooses `rgb` or `thermal` from the image itself.

The required model output shape is defined in
`prompts/annotation_schema.json` and passed directly to Gemini as the structured
output schema.

The saved annotation also includes task provenance from the manifest:
`image_id`, `image_path`, `label`, `question`, and `gt_answer`.
`subject_bbox` is produced by Gemini for the target subject using absolute pixel
`[x_min, y_min, x_max, y_max]` coordinates. The coordinates are provided in the
prompt input and the model must start its CoT reasoning by stating them.

## Wiki Maintenance

Wiki maintenance is a Gemini text-only call inside `pipeline.run`.

The pipeline sends Gemini the maintainer prompt, output schema, relevant wiki
pages, and annotations from the completed round. Gemini returns JSON findings
using `prompts/wiki_maintainer_schema.json`. The pipeline applies accepted
findings directly:

- appends general findings under `wiki/general/*.md`
- appends category findings under `wiki/categories/<label>.md`
- appends to `wiki/log.md`

Before adding anything, it compares the candidate idea against existing
`## Human Findings` and `## Agent Findings` on the relevant page. If the idea is
already covered, it returns no finding. Per-image facts stay in annotation
files. Reusable guidance belongs in the wiki. `wiki/index.md` and
`wiki/coverage/coverage.csv` are updated by the pipeline.

Findings use stable three-digit IDs inside each page:

```markdown
### 001 - Short finding title

Reusable guidance text.
```

The heading format must be exactly `### NNN - Short title`. Do not renumber
existing findings. The maintainer is allowed to make no edits; that is the
normal stop condition for the autonomous loop. Sources are written only in
`wiki/log.md`, not inside findings.

## Coverage

`wiki/coverage/coverage.csv` is the live requeue sheet.

Rows are tasks. Columns are numbered wiki findings. Cells are:

- `done`: the task was annotated with that finding in the prompt.
- `not_done`: the task needs re-annotation with that finding in the prompt.
- `n/a`: the finding does not apply to that task.

Coverage columns are stable IDs such as `general/thermal/001` or
`categories/amputation_arm/001`. General findings apply to all tasks. Category
findings apply only to that category label; other labels are marked `n/a`.

When a new finding is added, the sheet gains a new column and applicable
existing rows start as `not_done`. Editing the text of an existing finding does
not create a new column.

Keep the file when resuming the same labeling project. The `--fresh-coverage`
flag starts an independent fresh run: it deletes only the existing coverage
sheet and rebuilds it from the current manifests and wiki. Annotation files
under `outputs/annotations/` are not deleted; valid existing annotations are
reused on the next run. See `README.md` for how to invoke it.

## Pipeline stages (`pipeline.run`)

What the main entrypoint does in order:

1. Load selected tasks from `exports/`.
2. Optionally reset `coverage.csv` (when using fresh coverage; see README).
3. Refresh coverage against the current wiki.
4. Annotate tasks that are missing or `not_done`.
5. Run the wiki-maintainer agent.
6. Continue only if new numbered findings were added.
7. Export dataset JSONL only when the loop converged and coverage is clean.

## Human review in Obsidian

Two helpers exist: **annotation review** produces a scrollable markdown file with
CoT and images; **wiki graph vault** materializes the wiki as an Obsidian vault
with native Graph View. Outputs are under `outputs/` as described in README.
Invoke them from the repository root using the commands in README (Visualizing
section).

## Inputs and exports

Manifest layout under `exports/`, `bbox_map.json`, and bounding-box semantics are
documented in README (Inputs and Bounding Boxes).

`outputs/dataset/` is written by `pipeline.export` only when the loop converged
and coverage has no `not_done` cells. The exporter splits annotations by
`difficulty`: `easy` rows go to `sft.jsonl` and `hard` rows go to `rlvr.jsonl`.

Each row contains `image`, `task_id`, `image_id`, `label`, `question`, `answer`
(from `gt_answer`), `cot`, `subject_bbox`, `modality`, and `difficulty`.
