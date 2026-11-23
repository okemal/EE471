from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from week_9 import config

TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{20,}")


def test_no_hardcoded_hf_tokens_in_source_or_templates() -> None:
    project_root = Path(__file__).resolve().parents[1]
    targets = [
        *sorted((project_root / "src").rglob("*.py")),
        project_root / ".env.example",
        project_root / "README.md",
    ]
    for path in targets:
        content = path.read_text(encoding="utf-8")
        assert TOKEN_PATTERN.search(content) is None, f"Hardcoded token found in {path}"


def test_load_environment_and_get_hf_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("HF_TOKEN=test_token_from_file\n", encoding="utf-8")

    loaded = config.load_environment(env_path=env_file)
    assert loaded == env_file
    assert config.get_hf_token(env_path=env_file) == "test_token_from_file"


def test_shell_env_takes_precedence_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HF_TOKEN", "shell_token")
    env_file = tmp_path / ".env"
    env_file.write_text("HF_TOKEN=file_token\n", encoding="utf-8")

    assert config.get_hf_token(env_path=env_file) == "shell_token"


def test_get_hf_token_missing_optional_and_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    missing_env = tmp_path / "does_not_exist.env"

    assert config.get_hf_token(env_path=missing_env, required=False) is None
    with pytest.raises(RuntimeError, match="HF_TOKEN is not set"):
        config.get_hf_token(env_path=missing_env, required=True)


def test_resolve_device_auto_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert config.resolve_device() == torch.device("cuda")
    assert config.resolve_device("auto") == torch.device("cuda")

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        torch.backends,
        "mps",
        SimpleNamespace(is_available=lambda: True),
        raising=False,
    )
    assert config.resolve_device() == torch.device("mps")

    monkeypatch.setattr(
        torch.backends,
        "mps",
        SimpleNamespace(is_available=lambda: False),
        raising=False,
    )
    assert config.resolve_device() == torch.device("cpu")


def test_resolve_device_explicit_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        torch.backends,
        "mps",
        SimpleNamespace(is_available=lambda: False),
        raising=False,
    )
    assert config.resolve_device("cpu") == torch.device("cpu")
    with pytest.raises(RuntimeError, match="CUDA is not available"):
        config.resolve_device("cuda")
    with pytest.raises(RuntimeError, match="MPS is not available"):
        config.resolve_device("mps")


def test_resolve_dtype(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.resolve_dtype(torch.device("cpu"), prefer_bfloat16=True) is torch.float32
    assert config.resolve_dtype(torch.device("mps"), prefer_bfloat16=True) is torch.float32

    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    assert config.resolve_dtype(torch.device("cuda"), prefer_bfloat16=True) is torch.bfloat16
    assert config.resolve_dtype(torch.device("cuda"), prefer_bfloat16=False) is torch.float16

    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: False)
    assert config.resolve_dtype(torch.device("cuda"), prefer_bfloat16=True) is torch.float16
