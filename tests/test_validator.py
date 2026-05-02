"""Smoke tests for cli-parity-validator."""
import json
import tempfile
from pathlib import Path
import pytest


def test_import():
    from cli_parity_validator import ParityValidator, ValidationConfig
    assert ParityValidator
    assert ValidationConfig


def test_identical_schemas_pass():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        schema = {"tools": ["a", "b"]}
        (base / "x.json").write_text(json.dumps(schema))
        (target / "x.json").write_text(json.dumps(schema))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert result.all_pass


def test_extra_tool_is_violation():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        (base / "x.json").write_text(json.dumps({"tools": ["a"]}))
        (target / "x.json").write_text(json.dumps({"tools": ["a", "b"]}))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert not result.all_pass
        assert result.violations > 0
