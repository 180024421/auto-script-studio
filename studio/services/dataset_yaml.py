"""从工程 dataset/ 生成 adb-ide / Ultralytics 可用的 data.yaml。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence


def collect_class_names(project_dir: Path, subdir: str = "dataset") -> list[str]:
    """从 dataset 下 meta.json 与 labels 汇总类别名。"""
    root = project_dir / subdir
    names: list[str] = []
    seen: set[str] = set()
    if not root.is_dir():
        return names
    for meta_path in sorted(root.glob("*.meta.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            for n in data.get("class_names") or []:
                s = str(n).strip()
                if s and s not in seen:
                    seen.add(s)
                    names.append(s)
        except Exception:
            continue
    labels_dir = root / "labels"
    if labels_dir.is_dir():
        for txt in labels_dir.glob("*.txt"):
            for line in txt.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    cid = int(parts[0])
                except ValueError:
                    continue
                while len(names) <= cid:
                    names.append(f"class_{len(names)}")
    return names


def write_data_yaml(
    project_dir: Path,
    *,
    subdir: str = "dataset",
    class_names: Sequence[str] | None = None,
) -> Path:
    """写入 dataset/data.yaml，供 adb-ide yolo train 使用。"""
    project_dir = Path(project_dir)
    ds = project_dir / subdir
    names = list(class_names) if class_names else collect_class_names(project_dir, subdir)
    if not names:
        names = ["object"]
    images_train = (ds / "images").as_posix()
    labels_train = (ds / "labels").as_posix()
    lines = [
        f"path: {ds.resolve().as_posix()}",
        "train: images",
        "val: images",
        f"nc: {len(names)}",
        "names:",
    ]
    for i, n in enumerate(names):
        lines.append(f"  {i}: {n}")
    out = ds / "data.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
