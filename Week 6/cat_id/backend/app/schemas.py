"""Public response contracts shared by the API documentation and validation."""

from typing import Literal

from pydantic import BaseModel, Field


class Species(BaseModel):
    id: str
    common_name: str
    scientific_name: str
    genus: str
    subfamily: Literal["Felinae", "Pantherinae"]
    wikipedia_title: str
    summary: str
    range: str
    habitat: str
    identification: list[str]
    source_url: str
    taxonomy_note: str = ""
    aliases: list[str] = Field(default_factory=list)


class Knowledge(BaseModel):
    text: str
    source: str
    source_url: str
    live: bool
    license: str | None = None
    retrieved_at: str | None = None


class Candidate(BaseModel):
    species: Species
    similarity: float = Field(ge=-1, le=1, description="Cosine similarity, not a probability")


class ImageNetClass(BaseModel):
    label: str
    score: float = Field(ge=0, le=1)


class Baseline(BaseModel):
    model: Literal["ResNet50"]
    weights: Literal["IMAGENET1K_V1"]
    predicted_class: str
    top_classes: list[ImageNetClass] = Field(min_length=3, max_length=3)


class Identification(BaseModel):
    status: Literal["matched", "uncertain", "no_match"]
    message: str
    candidates: list[Candidate]
    diagnostics: dict[str, float]
    elapsed_ms: int
    model: str
    score_note: str
    knowledge: Knowledge | None = None
    baseline: Baseline | None = None


class SpeciesDetail(BaseModel):
    species: Species
    knowledge: Knowledge


class Catalogue(BaseModel):
    species: list[Species]
    taxonomy: str


class Health(BaseModel):
    status: Literal["loading", "ready", "error", "disabled"]
    device: str
    model: str
    species_count: int
    error: str | None
    offline: bool
    max_upload_bytes: int
    taxonomy: str
