from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import requests
import torch
from PIL import Image

from week_9 import opus_mt_fr_en, smollm2, vit, whisper


class _BatchStub(dict[str, torch.Tensor]):
    def to(self, device: torch.device) -> _BatchStub:
        self.moved_to = device
        return self


def test_smollm2_generate_text_passes_attention_mask_and_pad_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTokenizer:
        pad_token_id = None
        eos_token_id = 0

        def __call__(self, prompt: str, *, return_tensors: str) -> _BatchStub:
            assert return_tensors == "pt"
            captured["prompt"] = prompt
            return _BatchStub(
                input_ids=torch.tensor([[10, 20, 30]]),
                attention_mask=torch.tensor([[1, 1, 1]]),
            )

        def decode(self, ids: torch.Tensor, *, skip_special_tokens: bool) -> str:
            captured["decoded_ids"] = ids.tolist()
            captured["skip_special_tokens"] = skip_special_tokens
            return "Let's learn about C and pointers."

    class FakeModel:
        def generate(self, **kwargs: Any) -> torch.Tensor:
            captured["generate_kwargs"] = kwargs
            return torch.tensor([[10, 20, 30, 40, 50]])

    monkeypatch.setattr(
        smollm2,
        "load_model",
        lambda **_: (FakeTokenizer(), FakeModel(), torch.device("cpu"), torch.float32),
    )

    result = smollm2.generate_text("Let's learn about C", max_new_tokens=16)

    assert result.generated_text == "Let's learn about C and pointers."
    assert result.input_token_count == 3
    assert result.generated_token_count == 2
    assert "attention_mask" in captured["generate_kwargs"]
    assert captured["generate_kwargs"]["pad_token_id"] == 0
    assert captured["generate_kwargs"]["max_new_tokens"] == 16
    assert captured["skip_special_tokens"] is True


def test_smollm2_validation_errors() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        smollm2.generate_text("   ")
    with pytest.raises(ValueError, match="max_new_tokens"):
        smollm2.generate_text("Hello", max_new_tokens=0)
    with pytest.raises(ValueError, match="positive"):
        smollm2.generate_text("Hello", do_sample=True, temperature=0.0)
    with pytest.raises(ValueError, match="do_sample=True"):
        smollm2.generate_text("Hello", do_sample=False, temperature=0.7)


def test_opus_mt_translate_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeTokenizer:
        def __call__(
            self,
            text: str,
            *,
            return_tensors: str,
            truncation: bool,
        ) -> _BatchStub:
            assert return_tensors == "pt"
            assert truncation is True
            captured["source"] = text
            return _BatchStub(input_ids=torch.tensor([[1, 2, 3]]))

        def decode(self, ids: torch.Tensor, *, skip_special_tokens: bool) -> str:
            assert skip_special_tokens is True
            return "I'd like some coffee, please."

    class FakeModel:
        def generate(self, **kwargs: Any) -> torch.Tensor:
            captured["generate_kwargs"] = kwargs
            return torch.tensor([[4, 5, 6]])

    monkeypatch.setattr(
        opus_mt_fr_en,
        "load_model",
        lambda **_: (FakeTokenizer(), FakeModel(), torch.device("cpu")),
    )

    result = opus_mt_fr_en.translate_text(max_new_tokens=64)

    assert result.translated_text == "I'd like some coffee, please."
    assert result.device == "cpu"
    assert captured["generate_kwargs"]["max_new_tokens"] == 64


def test_opus_mt_load_model_clears_max_length(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModel:
        def __init__(self) -> None:
            self.generation_config = SimpleNamespace(max_length=512)
            self.eval_called = False
            self.moved_to: torch.device | None = None

        def to(self, device: torch.device) -> FakeModel:
            self.moved_to = device
            return self

        def eval(self) -> FakeModel:
            self.eval_called = True
            return self

    fake_model = FakeModel()
    monkeypatch.setattr(
        opus_mt_fr_en.AutoTokenizer,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: "fake-tok"),
    )
    monkeypatch.setattr(
        opus_mt_fr_en.AutoModelForSeq2SeqLM,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: fake_model),
    )
    monkeypatch.setattr(opus_mt_fr_en, "resolve_device", lambda _: torch.device("cpu"))

    _, model, device = opus_mt_fr_en.load_model(token="tok")

    assert model is fake_model
    assert device == torch.device("cpu")
    assert fake_model.eval_called is True
    assert fake_model.generation_config.max_length is None


def test_opus_mt_validation_errors() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        opus_mt_fr_en.translate_text("")
    with pytest.raises(ValueError, match="max_new_tokens"):
        opus_mt_fr_en.translate_text("Bonjour", max_new_tokens=0)


def test_vit_load_image_local_converts_rgba_to_rgb(tmp_path: Path) -> None:
    img_path = tmp_path / "rgba.png"
    Image.new("RGBA", (32, 24), (10, 20, 30, 128)).save(img_path)

    loaded = vit.load_image(img_path)
    assert loaded.mode == "RGB"
    assert loaded.size == (32, 24)


def test_vit_load_image_url_uses_timeout_and_closes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buf = BytesIO()
    Image.new("L", (16, 16), 200).save(buf, format="PNG")
    raw_bytes = buf.getvalue()
    state = {"closed": False, "timeout": None}

    class FakeResponse:
        content = raw_bytes

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_: object) -> None:
            state["closed"] = True

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, *, timeout: float) -> FakeResponse:
        assert url == "http://example.com/cat.png"
        state["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    loaded = vit.load_image("http://example.com/cat.png", timeout_s=12.5)
    assert loaded.mode == "RGB"
    assert state["timeout"] == 12.5
    assert state["closed"] is True


def test_vit_load_image_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        vit.load_image(tmp_path / "x.png", timeout_s=0)
    with pytest.raises(FileNotFoundError):
        vit.load_image(tmp_path / "missing.png")


def test_vit_classify_image_returns_ranked_softmax_predictions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    img_path = tmp_path / "cat.jpg"
    Image.new("RGB", (64, 64), (200, 150, 100)).save(img_path)

    class FakeProcessor:
        def __call__(self, *, images: Image.Image, return_tensors: str) -> _BatchStub:
            assert images.mode == "RGB"
            assert return_tensors == "pt"
            return _BatchStub(pixel_values=torch.zeros((1, 3, 224, 224)))

    class FakeModel:
        config = SimpleNamespace(id2label={0: "tabby", 1: "Egyptian cat", 2: "tiger cat"})

        def __call__(self, **_: Any) -> SimpleNamespace:
            return SimpleNamespace(logits=torch.tensor([[1.0, 4.0, 2.0]]))

    monkeypatch.setattr(
        vit,
        "load_model",
        lambda **_: (FakeProcessor(), FakeModel(), torch.device("cpu")),
    )

    result = vit.classify_image(img_path, top_k=2)

    assert result.top_prediction.label == "Egyptian cat"
    assert result.top_prediction.class_id == 1
    assert len(result.predictions) == 2
    assert result.predictions[0].probability > result.predictions[1].probability
    assert result.predictions[1].label == "tiger cat"


def test_vit_classify_image_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        vit.classify_image(top_k=0)


def test_whisper_load_pipeline_clears_forced_decoder_ids_and_bpe_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeModel:
        def __init__(self) -> None:
            self.generation_config = SimpleNamespace(forced_decoder_ids=[[1, None], [2, 50360]])
            self.eval_called = False
            self.moved_to: torch.device | None = None

        def to(self, device: torch.device) -> FakeModel:
            self.moved_to = device
            return self

        def eval(self) -> FakeModel:
            self.eval_called = True
            return self

    fake_model = FakeModel()
    fake_tokenizer = SimpleNamespace(clean_up_tokenization_spaces=True)
    fake_processor = SimpleNamespace(tokenizer=fake_tokenizer, feature_extractor="fe")

    monkeypatch.setattr(
        whisper.AutoModelForSpeechSeq2Seq,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: fake_model),
    )
    monkeypatch.setattr(
        whisper.AutoProcessor,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: fake_processor),
    )

    def fake_pipeline(task: str, **kwargs: Any) -> str:
        captured["task"] = task
        captured["kwargs"] = kwargs
        return "fake-pipe"

    monkeypatch.setattr(whisper, "pipeline", fake_pipeline)
    monkeypatch.setattr(whisper, "resolve_device", lambda _: torch.device("cpu"))

    pipe, device, dtype = whisper.load_pipeline(token="tok")

    assert pipe == "fake-pipe"
    assert device == torch.device("cpu")
    assert dtype is torch.float32
    assert fake_model.eval_called is True
    assert fake_model.generation_config.forced_decoder_ids is None
    assert fake_tokenizer.clean_up_tokenization_spaces is False
    assert captured["task"] == "automatic-speech-recognition"


def test_whisper_transcribe_audio_local_file_and_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"RIFF")
    captured: dict[str, Any] = {}

    def fake_pipe(audio_input: Any, **kwargs: Any) -> dict[str, Any]:
        captured["audio_input"] = audio_input
        captured["kwargs"] = kwargs
        return {
            "text": "  Hello world.  ",
            "chunks": [
                {"timestamp": (0.0, 1.5), "text": " Hello"},
                {"timestamp": (1.5, 3.0), "text": " world."},
            ],
        }

    monkeypatch.setattr(
        whisper,
        "load_pipeline",
        lambda **_: (fake_pipe, torch.device("cpu"), torch.float32),
    )

    result = whisper.transcribe_audio(audio_file, language="en", task="transcribe")

    assert captured["audio_input"] == str(audio_file)
    assert captured["kwargs"]["return_timestamps"] is True
    assert captured["kwargs"]["generate_kwargs"] == {"task": "transcribe", "language": "en"}
    assert result.text == "Hello world."
    assert len(result.chunks) == 2
    assert result.chunks[0].start_s == 0.0
    assert result.chunks[0].end_s == 1.5
    assert result.chunks[0].text == "Hello"


def test_whisper_validation_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="task must be"):
        whisper.transcribe_audio(task="invalid")  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        whisper.transcribe_audio(tmp_path / "missing.wav")
    with pytest.raises(ValueError, match="sample_index"):
        whisper.load_sample_audio(sample_index=-1)
