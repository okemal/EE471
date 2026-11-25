from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import torch

from week_9 import task4


class _FakeBatch(dict[str, torch.Tensor]):
    def to(self, _: torch.device) -> _FakeBatch:
        return self


def test_demonstrate_load_and_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_dir = tmp_path / "saved_bert"

    class FakeTokenizer:
        mask_token_id = 103

        def __call__(self, prompt: str, *_: Any, **__: Any) -> _FakeBatch:
            ids = [101, 200, 103, 102] if "[MASK]" in prompt else [101, 200, 102]
            return _FakeBatch(input_ids=torch.tensor([ids]))

        def decode(self, ids: list[int], **_: Any) -> str:
            return "mathematics" if ids[0] == 5 else "other"

        def save_pretrained(self, target: Path) -> None:
            (Path(target) / "tokenizer.json").write_text("{}", encoding="utf-8")

    class FakeModel:
        def to(self, _: torch.device) -> FakeModel:
            return self

        def eval(self) -> FakeModel:
            return self

        def __call__(self, **_: Any) -> Any:
            logits = torch.zeros((1, 4, 10))
            logits[0, 2, 5] = 8.0
            return type("Out", (), {"logits": logits})()

        def save_pretrained(self, target: Path) -> None:
            (Path(target) / "model.safetensors").write_bytes(b"weights")

    monkeypatch.setattr(task4, "resolve_device", lambda *_: torch.device("cpu"))
    monkeypatch.setattr(
        task4.AutoTokenizer,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: FakeTokenizer()),
    )
    monkeypatch.setattr(
        task4.AutoModelForMaskedLM,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    res = task4.demonstrate_load_and_save(save_dir=save_dir)
    assert res.predictions_match is True
    assert res.before_token == "mathematics"
    assert res.after_token == "mathematics"
    assert "model.safetensors" in res.saved_files
    assert "tokenizer.json" in res.saved_files

    with pytest.raises(ValueError, match="mask token"):
        task4.demonstrate_load_and_save(save_dir=save_dir, prompt="No mask here.")


def test_demonstrate_encode_decode_pad_truncate_and_special_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTokenizer:
        def __init__(self) -> None:
            self.pad_token = "[PAD]"
            self.pad_token_id = 0
            self.vocab = ["[PAD]", "[CLS]", "[SEP]", "Hello", "world", "long"]

        def __len__(self) -> int:
            return len(self.vocab)

        def tokenize(self, text: str) -> list[str]:
            return text.split()

        def encode(
            self, text: str, truncation: bool = False, max_length: int | None = None
        ) -> list[int]:
            tokens = ["[CLS]", *text.split(), "[SEP]"]
            if truncation and max_length is not None:
                tokens = tokens[:max_length]
            return list(range(100, 100 + len(tokens)))

        def decode(self, ids: list[int], skip_special_tokens: bool = False) -> str:
            return "decoded" if skip_special_tokens else "[CLS] decoded [SEP]"

        def __call__(self, sentences: list[str], **_: Any) -> dict[str, torch.Tensor]:
            assert len(sentences) == 2
            return {
                "input_ids": torch.tensor([[101, 10, 20, 30, 102], [101, 40, 102, 0, 0]]),
                "attention_mask": torch.tensor([[1, 1, 1, 1, 1], [1, 1, 1, 0, 0]]),
            }

        def convert_ids_to_tokens(self, ids: list[int]) -> list[str]:
            if "<EE471>" in self.vocab and len(ids) == 4:
                return ["[CLS]", "Welcome", "<EE471>", "[SEP]"]
            return [f"tok_{i}" for i in ids]

        def add_special_tokens(self, spec: dict[str, list[str]]) -> int:
            for tok in spec["additional_special_tokens"]:
                if tok not in self.vocab:
                    self.vocab.append(tok)
            return 1

        def convert_tokens_to_ids(self, tok: str | list[str]) -> int | list[int]:
            if isinstance(tok, list):
                return [self.vocab.index(t) if t in self.vocab else 99 for t in tok]
            return self.vocab.index(tok)

    class FakeModel:
        def __init__(self) -> None:
            self.weight = torch.zeros((6, 4))

        def eval(self) -> FakeModel:
            return self

        def get_input_embeddings(self) -> Any:
            return type("Emb", (), {"weight": self.weight})()

        def resize_token_embeddings(self, new_size: int) -> None:
            self.weight = torch.zeros((new_size, 4))

    monkeypatch.setattr(
        task4.AutoTokenizer,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: FakeTokenizer()),
    )
    monkeypatch.setattr(
        task4.AutoModelForMaskedLM,
        "from_pretrained",
        classmethod(lambda cls, *args, **kwargs: FakeModel()),
    )

    enc = task4.demonstrate_encode_and_decode("Hello world")
    assert enc.tokens == ("Hello", "world")
    assert enc.decoded_without_special == "decoded"

    pad = task4.demonstrate_padding(["Longer first sentence.", "Short."])
    assert pad.shorter_row_index == 1
    assert pad.pad_positions == (3, 4)

    trunc = task4.demonstrate_truncation("a " * 30, max_length=16)
    assert trunc.full_length == 32
    assert trunc.truncated_length == 16
    assert trunc.dropped_tokens == 16

    spec = task4.demonstrate_special_tokens("<EE471>", "Welcome <EE471>")
    assert spec.vocab_size_before == 6
    assert spec.vocab_size_after == 7
    assert spec.embedding_rows_after == 7
    assert "<EE471>" in spec.tokens_after
    assert len(spec.ids_with_boundary) == len(spec.ids_without_boundary) + 2
    assert "[CLS]" in spec.decoded_with_boundary and "[SEP]" in spec.decoded_with_boundary
