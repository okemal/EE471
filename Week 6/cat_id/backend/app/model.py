"""Two-stage local inference with pinned, safetensors-only model checkpoints.

A general CLIP gate compares felids with explicit non-cat and non-photographic
alternatives. BioCLIP ranks the pinned Felidae catalogue only after that gate.
Neither the similarities nor the rejection heuristics are calibrated confidence.
"""

import gc
import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .catalogue import species_catalogue
from .config import Settings
from .decision import decide

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Checkpoint:
    name: str
    repo: str
    revision: str
    architecture: str


BIOCLIP = Checkpoint(
    "BioCLIP 2.5 Huge",
    "imageomics/bioclip-2.5-vith14",
    "6e3d04e3d6522012c88181085c5ae666e14c45cd",
    "ViT-H-14",
)
GATE = Checkpoint(
    "OpenCLIP ViT-B/32",
    "laion/CLIP-ViT-B-32-laion2B-s34B-b79K",
    "1a25a446712ba5ee05982a381eed697ef9b435cf",
    "ViT-B-32",
)

NON_CAT_LABELS = [
    "dog",
    "wolf",
    "fox",
    "hyena",
    "civet",
    "genet",
    "mongoose",
    "meerkat",
    "raccoon",
    "red panda",
    "bear",
    "panda",
    "otter",
    "weasel",
    "ferret",
    "badger",
    "wolverine",
    "rabbit",
    "hare",
    "squirrel",
    "mouse",
    "rat",
    "hamster",
    "hedgehog",
    "porcupine",
    "deer",
    "antelope",
    "horse",
    "zebra",
    "cow",
    "goat",
    "sheep",
    "pig",
    "elephant",
    "rhinoceros",
    "giraffe",
    "monkey",
    "gorilla",
    "bird",
    "owl",
    "eagle",
    "parrot",
    "snake",
    "lizard",
    "crocodile",
    "turtle",
    "frog",
    "fish",
    "shark",
    "insect",
    "butterfly",
    "spider",
    "flower",
    "tree",
    "mushroom",
    "person",
    "human face",
    "car",
    "bicycle",
    "building",
    "mountain",
    "forest",
    "ocean",
    "food",
    "furniture",
    "computer",
    "text document",
    "empty room",
    "blank image",
    "random noise",
]
NON_PHOTO_PROMPTS = [
    "a drawing of a cat",
    "a cartoon cat",
    "a painting of a cat",
    "a stuffed toy cat",
    "a cat sculpture",
    "a toy animal",
    "a cat costume",
    "a screenshot of text",
    "an abstract pattern",
    "a blurry unrecognizable photograph",
]


def checkpoint_path(checkpoint: Checkpoint, settings: Settings) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=checkpoint.repo,
        revision=checkpoint.revision,
        cache_dir=str(settings.cache_dir),
        local_files_only=settings.offline,
        allow_patterns=["open_clip_model.safetensors", "open_clip_config.json"],
    )


def download_models(settings: Settings) -> None:
    for checkpoint in (GATE, BIOCLIP):
        logger.info("Preparing %s (%s)", checkpoint.name, checkpoint.revision)
        checkpoint_path(checkpoint, settings)


class Classifier:
    """One model owner per process; one image at a time avoids GPU memory spikes."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.status = "loading" if settings.load_model else "disabled"
        self.device = "pending"
        self.error: str | None = None
        self.lock = threading.Lock()
        self.catalogue = species_catalogue()

    def _load(self, checkpoint):
        import open_clip

        path = Path(checkpoint_path(checkpoint, self.settings))
        config = json.loads((path / "open_clip_config.json").read_text())
        if open_clip.get_model_config(checkpoint.architecture) != config["model_cfg"]:
            raise ValueError(
                "Checkpoint architecture does not match the pinned model configuration"
            )
        prep = config["preprocess_cfg"]
        model, _, transform = open_clip.create_model_and_transforms(
            checkpoint.architecture,
            pretrained=str(path / "open_clip_model.safetensors"),
            device=self.device,
            precision="fp16" if self.device == "cuda" else "fp32",
            image_mean=prep["mean"],
            image_std=prep["std"],
            image_interpolation=prep.get("interpolation", "bicubic"),
            image_resize_mode=prep.get("resize_mode", "shortest"),
        )
        model.eval()
        return model, transform, open_clip.get_tokenizer(checkpoint.architecture)

    def _encode_text(self, model, tokenizer, groups: list[list[str]]):
        import torch

        vectors = []
        with torch.inference_mode():
            for group in groups:
                encoded = model.encode_text(tokenizer(group).to(self.device), normalize=True)
                mean = encoded.float().mean(dim=0)
                vectors.append(mean / mean.norm())
        return torch.stack(vectors)

    def load(self) -> None:
        torch = None
        try:
            import torch

            if self.settings.device not in {"auto", "cpu", "cuda"}:
                raise ValueError("CAT_ID_DEVICE must be auto, cpu, or cuda")
            self.device = (
                ("cuda" if torch.cuda.is_available() else "cpu")
                if self.settings.device == "auto"
                else self.settings.device
            )
            if self.device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA was requested but is unavailable")
            torch.set_num_threads(min(4, torch.get_num_threads()))
            self.gate, self.gate_transform, tokenizer = self._load(GATE)
            cat_groups = [
                [
                    f"a photo of a {s['common_name'].lower()}.",
                    f"a photo of a {s['common_name'].lower()}, a cat animal.",
                ]
                for s in self.catalogue
            ]
            cat_groups += [["a photo of a domestic cat.", "a photo of a wild cat."]]
            self.cat_count = len(cat_groups)
            others = [[f"a photo of a {label}."] for label in NON_CAT_LABELS]
            others += [[prompt] for prompt in NON_PHOTO_PROMPTS]
            self.gate_text = self._encode_text(self.gate, tokenizer, cat_groups + others)
            self.bio, self.bio_transform, tokenizer = self._load(BIOCLIP)
            groups = [
                [
                    f"a photo of {s['common_name']}, {s['scientific_name']}.",
                    f"a photo of {s['scientific_name']}.",
                    "a photo of Animalia Chordata Mammalia Carnivora Felidae "
                    f"{s['genus']} {s['scientific_name'].split()[-1]}, {s['common_name']}.",
                ]
                for s in self.catalogue
            ]
            self.species_text = self._encode_text(self.bio, tokenizer, groups)
            self.status = "ready"
            logger.info("Models ready on %s; %d species", self.device, len(self.catalogue))
        except Exception:
            self.status = "error"
            self.error = "The local model could not start. Check the server log, cache, and device configuration."
            logger.exception("Model initialization failed")
            # An initialization failure must not leave a half-loaded model occupying VRAM.
            for name in ("gate", "bio", "gate_text", "species_text"):
                if hasattr(self, name):
                    delattr(self, name)
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _image_vector(self, model, transform, image: Image.Image):
        import torch

        # Center and full-frame views reduce the loss of a cat near an edge.
        padded = ImageOps.pad(image, (max(image.size), max(image.size)), color=(128, 128, 128))
        pixels = torch.stack([transform(image), transform(padded)]).to(self.device)
        if self.device == "cuda":
            pixels = pixels.half()
        encoded = model.encode_image(pixels, normalize=True).float()
        mean = encoded.mean(dim=0)
        return mean / mean.norm()

    def predict(self, image: Image.Image) -> dict:
        import torch

        with torch.inference_mode():
            gate = (
                (self._image_vector(self.gate, self.gate_transform, image) @ self.gate_text.T)
                .cpu()
                .numpy()
            )
            cat_similarity = float(gate[: self.cat_count].max())
            other_similarity = float(gate[self.cat_count :].max())
            gate_decision = decide(cat_similarity, other_similarity, [], self.settings)
            if gate_decision.status == "no_match":
                return {
                    "status": "no_match",
                    "message": gate_decision.message,
                    "candidates": [],
                    "diagnostics": {
                        "cat_similarity": round(cat_similarity, 4),
                        "gate_margin": round(cat_similarity - other_similarity, 4),
                    },
                }
            scores = (
                (self._image_vector(self.bio, self.bio_transform, image) @ self.species_text.T)
                .cpu()
                .numpy()
            )
            ranking = np.argsort(scores)[::-1][:3]
            ranked_scores = [float(scores[i]) for i in ranking]
            decision = decide(cat_similarity, other_similarity, ranked_scores, self.settings)
            return {
                "status": decision.status,
                "message": decision.message,
                "candidates": [
                    {"species": self.catalogue[int(i)], "similarity": round(float(scores[i]), 4)}
                    for i in ranking
                ],
                "diagnostics": {
                    "cat_similarity": round(cat_similarity, 4),
                    "gate_margin": round(cat_similarity - other_similarity, 4),
                    "species_margin": round(ranked_scores[0] - ranked_scores[1], 4),
                },
            }
