"""Read task manifests under exports/."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from . import paths


@dataclass
class ImageItem:
    image_path: Path
    image_id: str
    task_id: str
    label: str
    title: str
    question: str
    gt_answer: str
    bbox: tuple[float, float, float, float] | None

    def to_dict(self) -> dict:
        return {
            "image_path": str(self.image_path.relative_to(paths.ROOT)),
            "image_id": self.image_id,
            "task_id": self.task_id,
            "label": self.label,
            "question": self.question,
            "gt_answer": self.gt_answer,
            "bbox": self.bbox,
        }

_BBOX_MAP = None

def _load_bbox_map() -> dict:
    global _BBOX_MAP
    if _BBOX_MAP is None:
        bbox_path = paths.ROOT / "bbox_map.json"
        if bbox_path.exists():
            _BBOX_MAP = json.loads(bbox_path.read_text())
        else:
            _BBOX_MAP = {}
    return _BBOX_MAP

def _get_absolute_bbox(rel_path: str) -> tuple[float, float, float, float] | None:
    bbox_map = _load_bbox_map()
    data = bbox_map.get(rel_path)
    if not data:
        return None
    x1, y1, x2, y2 = data["bbox"]
    return (float(x1), float(y1), float(x2), float(y2))


def task_id(label: str, image_id: str) -> str:
    return f"{label}__{image_id}"


def _image_id(rel_path: str) -> str:
    return Path(rel_path).stem


def iter_all() -> Iterator[ImageItem]:
    from . import wiki
    try:
        memory = wiki.load_wiki_memory()
    except Exception:
        memory = None

    for base_dir in sorted(paths.EXPORTS.iterdir()):
        if not base_dir.is_dir():
            continue

        label = base_dir.name
        if "-data" in label:
            label = label.split("-data")[0]

        title = label
        question = ""
        
        if memory and memory.category_defs:
            cat_page = memory.category_defs.get(label)
            if cat_page:
                title = cat_page.frontmatter.get("title", title)
                question = cat_page.frontmatter.get("question", question)

        for gt_answer in ("yes", "no"):
            ans_dir = base_dir / gt_answer
            if ans_dir.is_dir():
                for img_path in sorted(ans_dir.iterdir()):
                    if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                        continue
                    
                    image_id = _image_id(img_path.name)
                    # Use a dummy rel_path for bbox mapping if available
                    rel_path = f"images/{img_path.name}" 
                    yield ImageItem(
                        image_path=img_path.resolve(),
                        image_id=image_id,
                        task_id=task_id(label, image_id),
                        label=label,
                        title=title,
                        question=question,
                        gt_answer=gt_answer,
                        bbox=_get_absolute_bbox(rel_path)
                    )


def collect_items(labels: Iterable[str] | None = None) -> List[ImageItem]:
    items = list(iter_all())
    if labels:
        wanted = set(labels)
        items = [item for item in items if item.label in wanted]
    return items
