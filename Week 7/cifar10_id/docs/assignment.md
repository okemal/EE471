# Assignment Mapping & Rubric Evidence (Week 7 · Task 2)

This document maps the EE471 Week 7 CIFAR-10 classifier requirements onto concrete artifacts in `Week 7/cifar10_id/`.

| Requirement | Implementation | Evidence |
|---|---|---|
| Train CIFAR-10 PyTorch Tutorial baseline | `TutorialCifarNet` (`Conv2d(3,6,5) -> Pool -> Conv2d(6,16,5) -> Pool -> Linear(400->120->84->10)`), SGD `lr=0.001`, `momentum=0.9`, batch `4`, `2` epochs | [backend/app/architecture.py](../backend/app/architecture.py), [backend/app/training.py](../backend/app/training.py) |
| Perform Hyperparameter Optimization (HPO) | 5-trial progression sweeping optimizers (SGD+Momentum vs. AdamW), learning rate, batch size (`4` -> `64` -> `128`), `CosineAnnealingLR`, ResNet-9 residual architecture, dropout, label smoothing, and `Flip+Crop+Cutout` | [backend/app/training.py](../backend/app/training.py), [backend/app/data/benchmark.json](../backend/app/data/benchmark.json), [docs/evaluation.json](evaluation.json) |
| Modify website with baseline vs. optimized side-by-side comparison | Browser UI compares `TutorialCifarNet` and `CifarResNet9` side by side with agreement badge, per-model top-3 bars, HPO table, and 10-class catalogue | [frontend/index.html](../frontend/index.html), [frontend/ui.js](../frontend/ui.js), [frontend/app.js](../frontend/app.js) |
| Containerize with Cog & Docker Compose | Standalone `cog.yaml` (`vision10-cifar-id:cog`) + `Dockerfile` (`vision10-cifar-id:cpu`) + `compose.cog.yaml` with SHA-256 weight verification and live container logs | [cog.yaml](../cog.yaml), [run.py](../run.py), [Dockerfile](../Dockerfile), [compose.cog.yaml](../compose.cog.yaml) |
| Inspect live container logs during predictions | Cog logs structured JSON events (`ready`, `prediction`, `failed`) to `stdout` and `/tmp/cifar10-predictions.jsonl` without storing raw image bytes | [run.py](../run.py) |
| Verify Cog container via Postman & automated script | Reproducible Postman collection + environment generator and automated HTTP contract script | [docs/postman/Vision10.postman_collection.json](postman/Vision10.postman_collection.json), [scripts/prepare_postman.py](../scripts/prepare_postman.py), [scripts/verify_cog.py](../scripts/verify_cog.py) |
| Automated testing suite (>= 80% coverage target; configured 85%) | Unit, security boundary, Cog transport, runner, and E2E Playwright tests | [tests/](../tests/), [docs/testing.md](testing.md) |
