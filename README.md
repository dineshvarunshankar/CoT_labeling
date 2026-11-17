# Triage CoT Labeling

Generate JSON annotations for triage images with Gemini through the CMU AI Gateway.
The model explains existing ground-truth answers. A markdown wiki supplies memory across annotation rounds.
A separate maintainer pass adds reusable findings and requeues affected tasks.

## Setup

Use Python 3.10 or later and `uv`.

```bash
git clone https://github.com/dineshvarunshankar/CoT_labeling.git
cd CoT_labeling
uv sync
export CMU_GATEWAY_API_KEY='<your-key>'
export LLM_MODEL='gemini/gemini-3.1-pro-preview'
```

`LLM_MODEL` selects the model for annotation and wiki maintenance. The value above is the default in the client.
The client uses `https://ai-gateway.andrew.cmu.edu/v1`.

## Usage

Run the pipeline:

```bash
uv run python -m pipeline.run
```

The default round budget is three. Each round uses one wiki snapshot.
New numbered findings trigger another round. After convergence, the pipeline exports completed tasks to `sft.jsonl` and `rlvr.jsonl`.

For a split under `data/<split>/`, use:

```bash
uv run python -m pipeline.run --split 01_05_26
```

This writes annotations, datasets, and coverage under `outputs/01_05_26/`.
To run a small annotation pass without wiki maintenance, use:

```bash
uv run python -m pipeline.run --split 01_05_26 --label amputation_arm --limit 4 --max-rounds 1 --skip-wiki-maintainer
```

Keep the coverage file to resume a project. `--fresh-coverage` rebuilds coverage and keeps existing annotation files.
Use `--help` for all arguments.

To generate an annotation review and a wiki graph for Obsidian, run:

```bash
uv run python -m pipeline.visualize --split 01_05_26
uv run python -m pipeline.wiki_graph_vault
```

Open `outputs/01_05_26/review.md` for the review. Open `outputs/wiki_graph_vault/` as an Obsidian vault for Graph View.

## Project Structure

```text
CoT_labeling/
├── AGENTS.md        # agent operating schema
├── INSTRUCTIONS.md  # runtime, coverage, and export details
├── data/            # input images, grouped by split
├── pipeline/        # annotation, wiki maintenance, coverage, and export code
├── prompts/         # prompts and JSON schemas
├── reference/       # source material for wiki authors
├── wiki/            # general and category findings
└── outputs/         # annotations, datasets, and review files
```

A split has this input layout:

```text
data/<split>/exports/
├── <label>-data-vf/
│   ├── yes/<image_id>.jpg
│   └── no/<image_id>.jpg
└── bbox_map.json
```

Annotations go to `outputs/<split>/cot_annotations/<label>/<image_id>.json`.
The same `cot_annotations/` directory contains the dataset exports: `easy` tasks in `sft.jsonl` and `hard` tasks in `rlvr.jsonl`.
Without `--split`, these files go to `outputs/cot_annotations/`.

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for input discovery, bounding boxes, annotation fields, and coverage rules.
See [AGENTS.md](AGENTS.md) for the agent operating schema.
