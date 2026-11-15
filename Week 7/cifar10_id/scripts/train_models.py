"""Train the CIFAR-10 baseline and HPO-optimized models and export benchmark metrics."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.training import run_cifar10_study  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=None, help="Force 'cuda' or 'cpu' (default: auto)")
    args = parser.parse_args()

    benchmark = run_cifar10_study(
        data_dir=settings.data_dir,
        cache_dir=settings.cache_dir,
        benchmark_output=ROOT / "backend" / "app" / "data" / "benchmark.json",
        evaluation_output=ROOT / "docs" / "evaluation.json",
        device=args.device,
    )
    print(
        f"Baseline ({benchmark['baseline']['trial_id']}): "
        f"{benchmark['baseline']['test_accuracy']:.4f} | "
        f"Optimized ({benchmark['optimized']['trial_id']}): "
        f"{benchmark['optimized']['test_accuracy']:.4f}"
    )


if __name__ == "__main__":
    main()
