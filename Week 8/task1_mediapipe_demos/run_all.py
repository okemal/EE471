"""Batch runner & model downloader for all 22 MediaPipe 1.2.3 solution demonstrations."""

from __future__ import annotations

import argparse
import importlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from mediapipe_demos.common import PROJECT_ROOT
from mediapipe_demos.models import MODEL_SPECS, download_all_models

TASK_ORDER: tuple[str, ...] = tuple(MODEL_SPECS.keys())


def run_selected_tasks(tasks: list[str], *, output_dir: Path | None = None) -> dict[str, object]:
    """Execute each requested demo module in sequence and collect structured timing/results."""
    started = time.perf_counter()
    results: dict[str, object] = {}
    failures: dict[str, str] = {}

    for task in tasks:
        t0 = time.perf_counter()
        try:
            mod = importlib.import_module(f"demos.{task}")
            payload = mod.run_demo(output_path=output_dir)
            results[task] = {
                "status": "ok",
                "elapsed_s": round(time.perf_counter() - t0, 2),
                "result": payload,
            }
        except Exception as exc:  # noqa: BLE001
            failures[task] = f"{type(exc).__name__}: {exc}"
            results[task] = {
                "status": "failed",
                "elapsed_s": round(time.perf_counter() - t0, 2),
                "error": failures[task],
            }
            print(f"[FAILED] {task}: {failures[task]}")

    report = {
        "executed_at": datetime.now(UTC).isoformat(),
        "total_tasks": len(tasks),
        "passed": len(tasks) - len(failures),
        "failed": len(failures),
        "total_elapsed_s": round(time.perf_counter() - started, 2),
        "tasks": results,
    }
    report_path = PROJECT_ROOT / "artifacts" / "demo_results.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 72)
    print(
        f"Summary: {report['passed']}/{report['total_tasks']} passed "
        f"in {report['total_elapsed_s']:.2f}s -> {report_path}"
    )
    print("=" * 72)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download and cache all 21 unique model files without running inference.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all 22 MediaPipe solution demos in sequence.",
    )
    parser.add_argument(
        "--domain",
        choices=["audio", "decision", "retrieval", "text", "vision"],
        help="Run all demos belonging to a single MediaPipe domain.",
    )
    parser.add_argument(
        "--task",
        action="append",
        choices=list(TASK_ORDER),
        help="Run one or more specific tasks (repeatable).",
    )
    parser.add_argument("--list", action="store_true", help="List all 22 tasks and exit.")
    args = parser.parse_args()

    if args.list:
        for idx, task in enumerate(TASK_ORDER, start=1):
            spec = MODEL_SPECS[task]
            print(
                f"{idx:2d}. [{spec.domain:<9}] {task:<22} ({spec.filename}, ~{spec.approx_mb} MB)"
            )
        return

    if args.download_only:
        download_all_models()
        return

    if args.task:
        selected = args.task
    elif args.domain:
        selected = [t for t in TASK_ORDER if MODEL_SPECS[t].domain == args.domain]
    else:
        selected = list(TASK_ORDER)

    report = run_selected_tasks(selected)
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
