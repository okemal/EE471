"""The exact pretrained ResNet50 weight variant used in Cog's getting-started guide.

ImageNet labels are returned verbatim, separately from species suggestions:
"tiger cat" is a domestic-cat class, and "lynx" does not establish a species.
"""

import hashlib
from pathlib import Path

from .config import Settings

CHECKPOINT_SHA256 = "0676ba61b6795bbe1773cffd859882e5e297624d384b6993f7c9e683e722fb8a"


def checkpoint_path(config: Settings) -> Path:
    import torch
    from torchvision.models import ResNet50_Weights

    weights = ResNet50_Weights.IMAGENET1K_V1
    destination = config.cache_dir / "resnet50" / weights.url.rsplit("/", 1)[-1]
    if not destination.exists():
        if config.offline:
            raise FileNotFoundError("Download the ResNet50 weights before starting offline.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        torch.hub.download_url_to_file(weights.url, str(destination), hash_prefix=CHECKPOINT_SHA256)
    # Verify cached files too, before loading even a restricted state dictionary.
    with destination.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != CHECKPOINT_SHA256:
        raise ValueError("ResNet50 checkpoint checksum mismatch.")
    return destination


class ResNetBaseline:
    def __init__(self, config: Settings, device: str):
        import torch
        from torchvision.models import ResNet50_Weights, resnet50

        self.device = device
        weights = ResNet50_Weights.IMAGENET1K_V1
        self.transform = weights.transforms()
        self.categories = weights.meta["categories"]
        self.model = resnet50(weights=None)
        state = torch.load(checkpoint_path(config), map_location="cpu", weights_only=True)
        self.model.load_state_dict(state)
        self.model.to(device).eval()

    def predict(self, image) -> dict:
        import torch

        with torch.inference_mode():
            pixels = self.transform(image).unsqueeze(0).to(self.device)
            values, indices = self.model(pixels)[0].softmax(0).topk(3)
        classes = [
            {"label": self.categories[int(index)], "score": round(float(score), 6)}
            for score, index in zip(values.cpu(), indices.cpu(), strict=True)
        ]
        return {
            "model": "ResNet50",
            "weights": "IMAGENET1K_V1",
            "predicted_class": classes[0]["label"],
            "top_classes": classes,
        }
