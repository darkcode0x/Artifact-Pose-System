#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _decimal_places(step: float) -> int:
    text = f"{step:.10f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def _normalize_lens(value: float, step: float, digits: int) -> float:
    return round(round(value / step) * step, digits)


def _read_lens_position(yaml_path: Path) -> float | None:
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("lens_position:"):
            continue
        raw = stripped.split(":", 1)[1].strip()
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _write_lens_position(yaml_path: Path, lens_position: float, digits: int) -> None:
    try:
        lines = yaml_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    lens_line = f"lens_position: {lens_position:.{digits}f}"

    for idx, line in enumerate(lines):
        if line.strip().startswith("lens_position:"):
            lines[idx] = lens_line
            yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

    for idx, line in enumerate(lines):
        if line.strip().startswith("reprojection_error:"):
            lines.insert(idx, lens_line)
            yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

    lines.append(lens_line)
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def organize(source_dir: Path, target_dir: Path, step: float, move: bool, default_lens: float | None) -> int:
    digits = _decimal_places(step)
    target_dir.mkdir(parents=True, exist_ok=True)

    yaml_files = sorted(source_dir.glob("*.yaml"))
    processed = 0

    for yaml_file in yaml_files:
        lens_position = _read_lens_position(yaml_file)
        if lens_position is None:
            if default_lens is None:
                print(f"[SKIP] {yaml_file.name}: khong co lens_position")
                continue
            lens_position = default_lens

        lens_position = _normalize_lens(lens_position, step, digits)
        target_name = f"camera_params_lens_{lens_position:.{digits}f}.yaml"
        target_path = target_dir / target_name

        if target_path.resolve() == yaml_file.resolve():
            _write_lens_position(target_path, lens_position, digits)
            print(f"[OK]   {yaml_file.name}: da dung ten chuan")
            processed += 1
            continue

        if target_path.exists():
            print(f"[SKIP] {yaml_file.name}: trung ten dich {target_name}")
            continue

        if move:
            shutil.move(str(yaml_file), str(target_path))
            action = "MOVE"
        else:
            shutil.copy2(str(yaml_file), str(target_path))
            action = "COPY"

        _write_lens_position(target_path, lens_position, digits)
        print(f"[{action}] {yaml_file.name} -> {target_name}")
        processed += 1

    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description="Gom va dat ten camera params YAML theo lens position")
    parser.add_argument("--source-dir", default="server/data", help="Thu muc chua file YAML nguon")
    parser.add_argument("--target-dir", default="server/data/camera_params", help="Thu muc gom file YAML")
    parser.add_argument("--step", type=float, default=0.1, help="Buoc lens position")
    parser.add_argument("--move", action="store_true", help="Di chuyen thay vi copy")
    parser.add_argument("--default-lens", type=float, default=None, help="Lens mac dinh neu file chua co lens_position")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    target_dir = Path(args.target_dir).resolve()

    if not source_dir.exists():
        print(f"Khong tim thay source dir: {source_dir}")
        return 1

    total = organize(source_dir, target_dir, args.step, args.move, args.default_lens)
    print(f"Hoan thanh: {total} file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
