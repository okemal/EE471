from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import torch
from PIL import Image

from week_9 import tasks
from week_9.tasks import (
    ASSETS_DIR,
    DEFAULT_AUDIO_PATH,
    DEFAULT_IMAGE_PATH,
    DEFAULT_NER_QA_CONTEXT,
    Week9Tasks,
)


def test_bundled_media_assets_and_credits_exist() -> None:
    assert DEFAULT_IMAGE_PATH.is_file()
    credits_path = ASSETS_DIR / "credits.json"
    assert credits_path.is_file()
    entries = json.loads(credits_path.read_text(encoding="utf-8"))
    ids = {item["id"] for item in entries}
    assert {"dog", "librispeech-sample"} <= ids


def test_week9_tasks_single_active_model_eviction(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Week9Tasks(device="cpu")
    moved_to_cpu: list[str] = []

    class FakeModel:
        def __init__(self, name: str) -> None:
            self.name = name

        def to(self, device: Any) -> FakeModel:
            if str(device) == "cpu":
                moved_to_cpu.append(self.name)
            return self

    monkeypatch.setattr(tasks, "resolve_device", lambda _: torch.device("cpu"))
    bundle_a, _ = runner._get_bundle("sentiment", "m1", lambda *_: {"model": FakeModel("m1")})
    assert runner.active_model_key == ("sentiment", "m1", "cpu")
    bundle_a_again, _ = runner._get_bundle(
        "sentiment", "m1", lambda *_: {"model": FakeModel("m1b")}
    )
    assert bundle_a_again is bundle_a

    runner._get_bundle("zero-shot", "m2", lambda *_: {"model": FakeModel("m2")})
    assert runner.active_model_key == ("zero-shot", "m2", "cpu")
    assert "m1" in moved_to_cpu


def test_load_pretrained_with_context_raises_descriptive_offline_error() -> None:
    def failing_loader(model_id: str, **_: Any) -> None:
        raise OSError(f"Cannot find {model_id} in cache")

    with pytest.raises(RuntimeError, match="google-t5/t5-small"):
        tasks.load_pretrained_with_context(failing_loader, "google-t5/t5-small")


def test_analyze_sentiment_preserves_order_and_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Week9Tasks(device="cpu")

    class FakeTokenizer:
        def __call__(self, texts: list[str], **_: Any) -> Any:
            assert len(texts) == 2

            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(input_ids=torch.zeros((2, 4), dtype=torch.long))

    class FakeModel:
        config = SimpleNamespace(id2label={0: "NEGATIVE", 1: "POSITIVE"})

        def to(self, _: torch.device) -> FakeModel:
            return self

        def eval(self) -> FakeModel:
            return self

        def __call__(self, **_: Any) -> SimpleNamespace:
            return SimpleNamespace(logits=torch.tensor([[0.1, 3.0], [3.0, 0.2]]))

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")),
    )
    res = runner.analyze_sentiment()
    assert [item.label for item in res.items] == ["POSITIVE", "NEGATIVE"]
    assert res.items[0].score > 0.9

    with pytest.raises(ValueError, match="at least one"):
        runner.analyze_sentiment("   ")


def test_classify_zero_shot_validates_labels_and_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Week9Tasks(device="cpu")

    class FakeTokenizer:
        def __call__(self, texts: list[str], hyps: list[str], **_: Any) -> Any:
            assert len(texts) == len(hyps) == 3

            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(input_ids=torch.zeros((3, 5), dtype=torch.long))

    class FakeModel:
        config = SimpleNamespace(label2id={"contradiction": 0, "neutral": 1, "entailment": 2})

        def __call__(self, **_: Any) -> SimpleNamespace:
            return SimpleNamespace(
                logits=torch.tensor(
                    [
                        [1.0, 0.5, 4.0],
                        [2.0, 1.0, 0.1],
                        [1.5, 1.0, 1.2],
                    ]
                )
            )

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")),
    )
    res = runner.classify_zero_shot("Berkshire holds cash.", "finance, sports, politics")
    assert res.labels[0].label == "finance"
    assert res.labels[0].score > res.labels[1].score

    with pytest.raises(ValueError, match="candidate_labels"):
        runner.classify_zero_shot("Some text", " , ")
    with pytest.raises(ValueError, match="non-empty"):
        runner.classify_zero_shot("  ", "finance")


def test_complete_text_enforces_two_distinct_sentences_and_word_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Week9Tasks(device="cpu")

    class FakeTokenizer:
        pad_token_id = None
        eos_token_id = 0

        def __call__(self, prompt: str, **_: Any) -> Any:
            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(input_ids=torch.tensor([[1, 2, 3]]))

        def decode(self, ids: torch.Tensor, **_: Any) -> str:
            idx = int(ids[0].item())
            choices = {
                10: " I will master Hugging Face Transformers quickly. Extra words here.",
                11: " I will build reliable AI software in Python!",
                12: " I will master Hugging Face Transformers quickly.",
            }
            return choices[idx]

    class FakeModel:
        def generate(self, **_: Any) -> torch.Tensor:
            return torch.tensor(
                [
                    [1, 2, 3, 10, 99],
                    [1, 2, 3, 12, 99],
                    [1, 2, 3, 11, 99],
                ]
            )

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")),
    )
    res = runner.complete_text(max_words=35)
    assert len(res.completions) == 2
    assert res.completions[0].text != res.completions[1].text
    for comp in res.completions:
        assert comp.text.startswith(res.prompt)
        assert comp.word_count <= 35
        assert comp.text[-1] in ".!?"

    with pytest.raises(ValueError, match="entire budget"):
        runner.complete_text("one two three four five", max_words=5)


def test_fill_mask_requires_exactly_one_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Week9Tasks(device="cpu")

    with pytest.raises(ValueError, match="found 0"):
        runner.fill_mask("No mask gap here.")
    with pytest.raises(ValueError, match="found 2"):
        runner.fill_mask("Two […] gaps […] here.")

    class FakeTokenizer:
        mask_token = "[MASK]"
        mask_token_id = 103

        def __call__(self, text: str, **_: Any) -> Any:
            assert "[MASK]" in text

            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(input_ids=torch.tensor([[101, 200, 103, 201, 102]]))

        def decode(self, ids: list[int], **_: Any) -> str:
            return {10: "transformers", 20: "attention"}.get(ids[0], "models")

    class FakeModel:
        def __call__(self, **_: Any) -> SimpleNamespace:
            logits = torch.zeros((1, 5, 30))
            logits[0, 2, 10] = 5.0
            logits[0, 2, 20] = 3.0
            return SimpleNamespace(logits=logits)

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")),
    )
    res = runner.fill_mask(top_k=2)
    assert res.candidates[0].token_str == "transformers"
    assert "transformers" in res.candidates[0].sequence


def test_recognize_entities_preserves_unicode_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Week9Tasks(device="cpu")
    text = DEFAULT_NER_QA_CONTEXT
    nate_s = text.index("Nate")
    izmir_inst_s = text.index("Izmir Institute of Technology")
    izmir_city_s = text.index("İzmir")
    turkiye_s = text.index("Türkiye")

    offsets = [
        (0, 0),
        (nate_s, nate_s + 4),
        (izmir_inst_s, izmir_inst_s + 5),
        (izmir_inst_s + 6, izmir_inst_s + 15),
        (izmir_inst_s + 16, izmir_inst_s + 18),
        (izmir_inst_s + 19, izmir_inst_s + 29),
        (izmir_city_s, izmir_city_s + 1),
        (izmir_city_s + 1, izmir_city_s + 5),
        (turkiye_s, turkiye_s + 7),
        (0, 0),
    ]
    word_ids = [None, 0, 1, 2, 3, 4, 5, 5, 6, None]

    class FakeEncoding(dict[str, Any]):
        def word_ids(self, _: int = 0) -> list[int | None]:
            return word_ids

    class FakeTokenizer:
        def __call__(self, *_: Any, **__: Any) -> FakeEncoding:
            return FakeEncoding(
                input_ids=torch.zeros((1, len(offsets)), dtype=torch.long),
                offset_mapping=torch.tensor([offsets]),
            )

    class FakeModel:
        config = SimpleNamespace(
            id2label={0: "O", 1: "B-PER", 2: "B-ORG", 3: "I-ORG", 4: "B-LOC", 5: "I-LOC"}
        )

        def __call__(self, **_: Any) -> SimpleNamespace:
            logits = torch.full((1, len(offsets), 6), -10.0)
            tags = [0, 1, 2, 3, 3, 3, 4, 5, 4, 0]
            for pos, tag_idx in enumerate(tags):
                logits[0, pos, tag_idx] = 10.0
            return SimpleNamespace(logits=logits)

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")),
    )
    res = runner.recognize_entities(text)
    extracted = [(e.entity_group, e.text) for e in res.entities]
    assert extracted == [
        ("PER", "Nate"),
        ("ORG", "Izmir Institute of Technology"),
        ("LOC", "İzmir"),
        ("LOC", "Türkiye"),
    ]


def test_answer_question_retains_disagreement_between_qa_and_ner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Week9Tasks(device="cpu")
    context = DEFAULT_NER_QA_CONTEXT
    nate_s = context.index("Nate")
    izmir_s = context.index("İzmir")

    monkeypatch.setattr(
        runner,
        "recognize_entities",
        lambda *_, **__: tasks.NerResult(
            model_id="ner",
            device="cpu",
            text=context,
            entities=(
                tasks.NamedEntity("Nate", "PER", 0.99, nate_s, nate_s + 4),
                tasks.NamedEntity(
                    "Türkiye", "LOC", 0.95, context.index("Türkiye"), len(context) - 1
                ),
            ),
        ),
    )

    class FakeEncoding(dict[str, Any]):
        def sequence_ids(self, _: int = 0) -> list[int | None]:
            return [None, 0, None, 1, 1, 1, None]

    class FakeTokenizer:
        def __call__(self, question: str, *_: Any, **__: Any) -> FakeEncoding:
            self.last_q = question
            return FakeEncoding(
                input_ids=torch.zeros((1, 7), dtype=torch.long),
                offset_mapping=torch.tensor(
                    [
                        [
                            (0, 0),
                            (0, 3),
                            (0, 0),
                            (nate_s, nate_s + 4),
                            (izmir_s, izmir_s + 5),
                            (0, 0),
                            (0, 0),
                        ]
                    ]
                ),
            )

    fake_tok = FakeTokenizer()

    class FakeModel:
        def __call__(self, **_: Any) -> SimpleNamespace:
            s = torch.full((1, 7), -5.0)
            e = torch.full((1, 7), -5.0)
            target_idx = 3 if "name" in fake_tok.last_q else 4
            s[0, target_idx] = 5.0
            e[0, target_idx] = 5.0
            return SimpleNamespace(start_logits=s, end_logits=e)

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"tokenizer": fake_tok, "model": FakeModel()}, torch.device("cpu")),
    )
    res = runner.answer_question(
        [
            "What is the research assistant's name?",
            "In which city does the research assistant live?",
        ],
        context,
    )
    assert res.items[0].agreed is True
    assert res.items[0].answer == "Nate"
    assert res.items[1].agreed is False
    assert res.items[1].answer == "İzmir"
    assert res.items[1].ner_entity == "Türkiye"


def test_translate_text_uses_opus_mt_fr_en_and_default_french_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Week9Tasks(device="cpu")
    seen_inputs: list[str] = []

    class FakeTokenizer:
        def __call__(self, text: str, **_: Any) -> Any:
            seen_inputs.append(text)

            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(input_ids=torch.tensor([[1, 2, 3]]))

        def decode(self, *_: Any, **__: Any) -> str:
            return "This course is produced by Hugging Face."

    class FakeModel:
        def generate(self, **_: Any) -> torch.Tensor:
            return torch.tensor([[1, 2]])

    calls: list[tuple[str, str]] = []

    def fake_get_bundle(kind: str, model_id: str, *_: Any) -> tuple[dict[str, Any], torch.device]:
        calls.append((kind, model_id))
        return {"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")

    monkeypatch.setattr(runner, "_get_bundle", fake_get_bundle)
    res = runner.translate_text()
    assert res.source_text == "Ce cours est produit par Hugging Face."
    assert res.translated_text == "This course is produced by Hugging Face."
    assert calls == [("seq2seq", tasks.TRANSLATION_MODEL_ID)]
    assert seen_inputs == ["Ce cours est produit par Hugging Face."]


def test_summarize_and_translate_share_t5_bundle_key(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Week9Tasks(device="cpu")
    seen_prefixes: list[str] = []

    class FakeTokenizer:
        def __call__(self, text: str, **_: Any) -> Any:
            seen_prefixes.append(text.split(":", 1)[0])

            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(input_ids=torch.tensor([[1, 2, 3]]))

        def decode(self, *_: Any, **__: Any) -> str:
            return "Output text."

    class FakeModel:
        def generate(self, **_: Any) -> torch.Tensor:
            return torch.tensor([[1, 2]])

    calls: list[tuple[str, str]] = []

    def fake_get_bundle(kind: str, model_id: str, *_: Any) -> tuple[dict[str, Any], torch.device]:
        calls.append((kind, model_id))
        return {"tokenizer": FakeTokenizer(), "model": FakeModel()}, torch.device("cpu")

    monkeypatch.setattr(runner, "_get_bundle", fake_get_bundle)
    s_res = runner.summarize("Long text about the crisis.")
    t_res = runner.translate_to_french("Short English sentence.")
    assert s_res.summary_text == "Output text."
    assert t_res.translated_text == "Output text."
    assert calls == [
        ("seq2seq", tasks.T5_MODEL_ID),
        ("seq2seq", tasks.T5_MODEL_ID),
    ]
    assert seen_prefixes == ["summarize", "translate English to French"]


def test_classify_image_and_transcribe_audio_with_pil_and_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = Week9Tasks(device="cpu")
    with pytest.raises(FileNotFoundError):
        runner.transcribe_audio(tmp_path / "missing.wav")

    class FakeProcessor:
        def __call__(self, *, images: Image.Image, return_tensors: str) -> Any:
            assert images.mode == "RGB"
            assert return_tensors == "pt"

            class Batch(dict[str, torch.Tensor]):
                def to(self, _: torch.device) -> Batch:
                    return self

            return Batch(pixel_values=torch.zeros((1, 3, 224, 224)))

    class FakeVitModel:
        config = SimpleNamespace(id2label={0: "golden retriever", 1: "Labrador retriever"})

        def __call__(self, **_: Any) -> SimpleNamespace:
            return SimpleNamespace(logits=torch.tensor([[5.0, 1.0]]))

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"processor": FakeProcessor(), "model": FakeVitModel()}, torch.device("cpu")),
    )
    img_res = runner.classify_image(Image.new("RGBA", (32, 32), (10, 20, 30, 255)), top_k=2)
    assert img_res.top_prediction.label == "golden retriever"
    assert img_res.source == "<uploaded image>"

    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"RIFF")

    def fake_pipe(path: str, **_: Any) -> dict[str, Any]:
        assert path == str(audio_file)
        return {
            "text": "Hello world.",
            "chunks": [{"timestamp": (0.0, 1.0), "text": "Hello world."}],
        }

    monkeypatch.setattr(
        runner,
        "_get_bundle",
        lambda *_: ({"pipeline": fake_pipe, "dtype": torch.float16}, torch.device("cpu")),
    )
    asr_res = runner.transcribe_audio(audio_file)
    assert asr_res.text == "Hello world."
    assert len(asr_res.chunks) == 1
    assert DEFAULT_AUDIO_PATH.name == "librispeech_sample.wav"
