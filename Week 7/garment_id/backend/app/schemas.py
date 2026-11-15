"""Pydantic response schemas shared by the FastAPI server and Cog runner."""

from typing import Literal

from pydantic import BaseModel, Field


class GarmentClass(BaseModel):
    """Metadata and visual clues for one FashionMNIST garment category."""

    id: str
    class_index: int = Field(ge=0, le=9)
    label: str
    display_name: str
    category_group: str
    summary: str
    silhouette_clues: list[str]
    common_confusions: list[str]
    care_and_construction: str
    aliases: list[str] = Field(default_factory=list)
    baseline_accuracy: float | None = Field(default=None, ge=0, le=1)
    optimized_accuracy: float | None = Field(default=None, ge=0, le=1)


class ClassProbability(BaseModel):
    """Single predicted class entry and its softmax probability."""

    label: str
    display_name: str
    class_id: str
    probability: float = Field(ge=0, le=1)


class ModelPrediction(BaseModel):
    """Inference output and provenance for one classifier (baseline or optimized)."""

    model_id: Literal["baseline", "optimized"]
    model_name: str
    architecture: str
    hyperparameters: dict[str, str | int | float]
    test_accuracy: float = Field(ge=0, le=1)
    predicted_class: str
    predicted_display_name: str
    predicted_id: str
    confidence: float = Field(ge=0, le=1)
    top_classes: list[ClassProbability] = Field(min_length=3, max_length=3)
    elapsed_ms: float = Field(ge=0)


class ModelComparison(BaseModel):
    """Side-by-side comparison metrics between baseline and optimized classifiers."""

    agreement: bool
    confidence_delta: float
    test_accuracy_delta: float
    winner: Literal["optimized"]
    summary: str


class Candidate(BaseModel):
    """Ranked garment candidate pairing optimized and baseline probabilities."""

    garment: GarmentClass
    probability: float = Field(ge=0, le=1)
    baseline_probability: float = Field(ge=0, le=1)


class Identification(BaseModel):
    """Complete side-by-side garment classification response."""

    status: Literal["matched", "uncertain", "no_match"]
    message: str
    candidates: list[Candidate]
    baseline: ModelPrediction
    optimized: ModelPrediction
    comparison: ModelComparison
    diagnostics: dict[str, float | bool | str]
    elapsed_ms: int = Field(ge=0)
    model: str
    score_note: str


class GarmentDetail(BaseModel):
    """Single garment category detail response."""

    garment: GarmentClass
    baseline_accuracy: float | None = Field(default=None, ge=0, le=1)
    optimized_accuracy: float | None = Field(default=None, ge=0, le=1)


class Catalogue(BaseModel):
    """All 10 garment categories and dataset attribution."""

    garments: list[GarmentClass]
    dataset: str


class TrialRecord(BaseModel):
    """Recorded metrics and hyperparameters for one training/HPO experiment."""

    trial_id: str
    name: str
    role: Literal["baseline", "hpo_candidate", "optimized"]
    architecture: str
    optimizer: str
    learning_rate: float
    batch_size: int
    epochs: int
    scheduler: str
    weight_decay: float
    augmentation: str
    dropout: float
    best_val_accuracy: float = Field(ge=0, le=1)
    test_accuracy: float = Field(ge=0, le=1)
    train_seconds: float = Field(ge=0)
    parameter_count: int = Field(gt=0)


class BenchmarkReport(BaseModel):
    """Training, HPO progression, and held-out FashionMNIST test evaluation."""

    dataset: str
    generated_at: str
    device: str
    baseline: TrialRecord
    optimized: TrialRecord
    trials: list[TrialRecord]
    per_class_accuracy: list[dict[str, str | int | float]]
    epoch_history: dict[str, list[dict[str, int | float]]]


class Health(BaseModel):
    """Readiness and configuration snapshot for the frontend status badge."""

    status: Literal["loading", "ready", "error", "disabled"]
    device: str
    model: str
    class_count: int
    error: str | None
    offline: bool
    max_upload_bytes: int
    dataset: str
    baseline_accuracy: float | None = None
    optimized_accuracy: float | None = None
