from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from week_9 import cli, opus_mt_fr_en, smollm2, task4, vit, whisper
from week_9.tasks import SentimentAnalysisResult, SentimentItem


def test_cli_list_prints_all_four_models(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "smollm2" in captured.out
    assert "opus-mt-fr-en" in captured.out
    assert "vit" in captured.out
    assert "whisper" in captured.out
    assert "task1" in captured.out
    assert "task4" in captured.out
    assert "app" in captured.out


def test_cli_dispatches_task1_task4_and_app(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli.Week9Tasks,
        "analyze_sentiment",
        lambda self: SentimentAnalysisResult(
            model_id="distilbert-sst2",
            device="cpu",
            items=(SentimentItem("Great", "POSITIVE", 0.99),),
        ),
    )
    assert cli.main(["task1", "sentiment"]) == 0
    assert "POSITIVE" in capsys.readouterr().out

    monkeypatch.setattr(
        cli,
        "demonstrate_encode_and_decode",
        lambda: task4.EncodeDecodeResult(
            model_id="bert-base-cased",
            original_text="Hi",
            tokens=("Hi",),
            input_ids=(101, 8790, 102),
            decoded_with_special="[CLS] Hi [SEP]",
            decoded_without_special="Hi",
            explanation="Boundary tokens added.",
        ),
    )
    assert cli.main(["task4", "encode-decode"]) == 0
    assert "[CLS] Hi [SEP]" in capsys.readouterr().out

    app_args: list[str] = []
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(main=lambda a: app_args.extend(a) or 0)
            if name == "week_9.app"
            else None
        ),
    )
    assert cli.main(["app", "--port", "7860"]) == 0
    assert app_args == ["--port", "7860"]


def test_cli_dispatches_to_model_module(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[str] = []

    def fake_main(args: list[str]) -> int:
        received.extend(args)
        return 0

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: SimpleNamespace(main=fake_main) if name == "week_9.vit" else None,
    )

    exit_code = cli.main(["vit", "--top-k", "3"])
    assert exit_code == 0
    assert received == ["--top-k", "3"]


def test_module_clis_print_expected_outputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        smollm2,
        "generate_text",
        lambda **_: smollm2.GenerationResult(
            model_id=smollm2.MODEL_ID,
            device="cpu",
            dtype="torch.float32",
            prompt="Hi",
            generated_text="Hi there!",
            input_token_count=1,
            generated_token_count=2,
        ),
    )
    assert smollm2.main(["--prompt", "Hi"]) == 0
    assert "Hi there!" in capsys.readouterr().out

    monkeypatch.setattr(
        opus_mt_fr_en,
        "translate_text",
        lambda **_: opus_mt_fr_en.TranslationResult(
            model_id=opus_mt_fr_en.MODEL_ID,
            device="cpu",
            source_text="Bonjour",
            translated_text="Hello",
        ),
    )
    assert opus_mt_fr_en.main(["--text", "Bonjour"]) == 0
    assert "Hello" in capsys.readouterr().out

    top_pred = vit.Prediction(label="Egyptian cat", class_id=285, probability=0.92)
    monkeypatch.setattr(
        vit,
        "classify_image",
        lambda **_: vit.ClassificationResult(
            model_id=vit.MODEL_ID,
            device="cpu",
            source="cat.jpg",
            top_prediction=top_pred,
            predictions=(top_pred,),
        ),
    )
    assert vit.main(["--top-k", "1"]) == 0
    assert "Predicted class: Egyptian cat (92.00%)" in capsys.readouterr().out

    monkeypatch.setattr(
        whisper,
        "transcribe_audio",
        lambda **_: whisper.TranscriptionResult(
            model_id=whisper.MODEL_ID,
            device="cpu",
            dtype="torch.float32",
            source="sample.wav",
            text="Testing one two.",
            chunks=(whisper.TranscriptChunk(start_s=0.0, end_s=2.0, text="Testing one two."),),
        ),
    )
    assert whisper.main(["--language", "auto", "--show-timestamps"]) == 0
    assert "[  0.00s ->   2.00s] Testing one two." in capsys.readouterr().out
