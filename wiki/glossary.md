# Glossary

Terms used across the wiki.

- **Task** — one label/question applied to one image.
- **Task ID** — stable internal ID in the form `<label>__<image_id>`.
- **Category** — one of the triage labels, such as `amputation_arm` or `tripod`.
  The category definition lives at `wiki/categories/<label>.md`.
- **Finding** — a reusable numbered note inside a wiki page, such as
  `general/thermal/001` or `categories/amputation_arm/001`.
- **Human Findings** — user-authored findings under `## Human Findings`.
- **Agent Findings** — maintainer-authored findings under `## Agent Findings`.
- **Coverage** — the generated sheet at `wiki/coverage/coverage.csv` that marks
  whether each task was annotated with each applicable numbered finding.
- **done** — coverage state meaning the task has been annotated with that
  finding present in the prompt.
- **not_done** — coverage state meaning the task must be re-annotated with that
  finding present in the prompt.
- **n/a** — coverage state meaning the finding does not apply to that task.
- **Annotation** — one clean per-task JSON output containing the dense natural
  CoT and minimal task provenance.
- **CoT** — the dense natural visual rationale explaining why the provided GT
  answer is supported.
- **Subject bbox** — normalized `[x_min, y_min, x_max, y_max]` coordinates in
  `[0, 1]` for the target casualty/person shown by the green box. Gemini
  produces it during annotation; `pipeline.bbox` may later overwrite it with
  normalized GT coordinates.
- **Modality** — `rgb` or `thermal`.
- **Difficulty** — `easy` or `hard`, based on how much visual ambiguity and
  rule-out reasoning the annotation requires. Drives the SFT vs RLVR split at
  export time (`easy` → `sft.jsonl`, `hard` → `rlvr.jsonl`).
- **Round** — one annotate-then-maintain cycle inside `pipeline.run`. The wiki
  is loaded once at the start of a round and used for every task in that round.
- **Annotation Mode** — the Gemini call that produces one annotation JSON per
  task. Driven by `prompts/prompt.md` and `prompts/annotation_schema.json`.
- **Wiki-Maintainer Mode** — the round-boundary Gemini text-only call that
  proposes new wiki findings as JSON. Driven by `prompts/wiki_maintainer.md`
  and `prompts/wiki_maintainer_schema.json`.
- **Maintainer** — the Wiki-Maintainer Mode agent. The pipeline applies its
  accepted findings to markdown deterministically.
- **Coverage column** — one stable numbered finding such as
  `general/thermal/006` or `categories/amputation_arm/004`. Adding a new
  finding adds a new column to `wiki/coverage/coverage.csv` and requeues the
  applicable rows as `not_done`.
