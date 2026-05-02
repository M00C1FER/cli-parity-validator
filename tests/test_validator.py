"""Smoke tests for cli-parity-validator."""
import json
import sys
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


# ── ParityResult extended fields ──────────────────────────────────────────────

def test_parity_result_total_and_pass_count():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        schema = {"tools": ["a"]}
        (base / "alpha.json").write_text(json.dumps(schema))
        (target / "alpha.json").write_text(json.dumps(schema))
        (base / "beta.json").write_text(json.dumps({"tools": ["x"]}))
        (target / "beta.json").write_text(json.dumps({"tools": ["x", "y"]}))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert result.total == 2
        assert result.pass_count == 1
        assert result.violations == 1


def test_violation_details_not_empty_on_failure():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        (base / "x.json").write_text(json.dumps({"tools": ["a"]}))
        (target / "x.json").write_text(json.dumps({"tools": ["a", "b"]}))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert len(result.violation_details) > 0


def test_violation_details_empty_on_pass():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        schema = {"tools": ["a", "b"]}
        (base / "x.json").write_text(json.dumps(schema))
        (target / "x.json").write_text(json.dumps(schema))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert result.violation_details == []


def test_missing_file_in_target_is_violation():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        (base / "x.json").write_text(json.dumps({"tools": ["a"]}))
        # target has no x.json
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert not result.all_pass
        assert any("missing in target" in line for line in result.lines)


# ── validate() function (YAML-schema path) ───────────────────────────────────

def test_validate_no_paths_no_schema():
    """validate() with empty config should succeed with zero tools."""
    from cli_parity_validator.validator import validate, ParityValidatorConfig
    result = validate(ParityValidatorConfig())
    assert result.ok
    assert result.source_tool_count == 0


def test_validate_warns_on_missing_source_file():
    """Unreachable source file must produce a warning, not a silent miss."""
    from cli_parity_validator.validator import validate, ParityValidatorConfig
    from pathlib import Path
    result = validate(ParityValidatorConfig(
        server_paths=[Path("/nonexistent/server.py")]
    ))
    # Should still be ok (no errors), but warnings must mention the missing file
    warning_lines = [l for l in result.lines if "not found" in l or "warnings" in l]
    assert len(warning_lines) > 0


def test_validate_schema_missing_tool_detected():
    """Tool in source but absent from schema manifest → error."""
    import textwrap
    import yaml
    from cli_parity_validator.validator import validate, ParityValidatorConfig

    src = textwrap.dedent("""\
        import mcp
        @mcp.tool()
        def my_tool(): pass
    """)
    schema = {"servers": {"default": {"tools": ["other_tool"]}}}

    with tempfile.TemporaryDirectory() as d:
        src_path = Path(d) / "server.py"
        src_path.write_text(src)
        schema_path = Path(d) / "schema.yaml"
        schema_path.write_text(yaml.dump(schema))

        result = validate(ParityValidatorConfig(
            server_paths=[src_path],
            schema_path=schema_path,
            server_names=["default"],
        ))
    assert not result.ok
    assert result.violations > 0
    assert any("my_tool" in l for l in result.lines)


def test_validate_schema_stale_tool_detected():
    """Tool in schema but absent from source → stale error."""
    import textwrap
    import yaml
    from cli_parity_validator.validator import validate, ParityValidatorConfig

    src = textwrap.dedent("""\
        import mcp
        @mcp.tool()
        def real_tool(): pass
    """)
    schema = {"servers": {"default": {"tools": ["real_tool", "ghost_tool"]}}}

    with tempfile.TemporaryDirectory() as d:
        src_path = Path(d) / "server.py"
        src_path.write_text(src)
        schema_path = Path(d) / "schema.yaml"
        schema_path.write_text(yaml.dump(schema))

        result = validate(ParityValidatorConfig(
            server_paths=[src_path],
            schema_path=schema_path,
            server_names=["default"],
        ))
    assert not result.ok
    assert any("ghost_tool" in l for l in result.lines)


def test_validate_exact_match_passes():
    """Source and schema agree exactly → ok."""
    import textwrap
    import yaml
    from cli_parity_validator.validator import validate, ParityValidatorConfig

    src = textwrap.dedent("""\
        import mcp
        @mcp.tool()
        def tool_a(): pass
        @mcp.tool(name="tool_b")
        def _b(): pass
    """)
    schema = {"servers": {"default": {"tools": ["tool_a", "tool_b"]}}}

    with tempfile.TemporaryDirectory() as d:
        src_path = Path(d) / "server.py"
        src_path.write_text(src)
        schema_path = Path(d) / "schema.yaml"
        schema_path.write_text(yaml.dump(schema))

        result = validate(ParityValidatorConfig(
            server_paths=[src_path],
            schema_path=schema_path,
            server_names=["default"],
        ))
    assert result.ok
    assert result.violations == 0


# ── CLI main() ────────────────────────────────────────────────────────────────

def test_main_version(capsys):
    from cli_parity_validator.validator import main
    with pytest.raises(SystemExit) as exc:
        sys.argv = ["cli-parity", "--version"]
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "1.0.0" in captured.out


def test_main_json_format(capsys):
    from cli_parity_validator.validator import main
    sys.argv = ["cli-parity", "--format", "json"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "ok" in data
    assert "violations" in data


def test_main_exit_nonzero_on_drift(tmp_path, capsys):
    """main() must exit 1 when drift is detected."""
    import textwrap
    import yaml
    from cli_parity_validator.validator import main

    src = textwrap.dedent("""\
        import mcp
        @mcp.tool()
        def undeclared_tool(): pass
    """)
    schema = {"servers": {"default": {"tools": ["other_tool"]}}}
    src_path = tmp_path / "server.py"
    src_path.write_text(src)
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(yaml.dump(schema))

    sys.argv = ["cli-parity", "--schema", str(schema_path), str(src_path)]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


# ── Tool-set ordering (set-based, not order-dependent) ───────────────────────

def test_tool_set_comparison_is_order_independent():
    """Tools ["a","b"] and ["b","a"] must be treated as equal."""
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        (base / "x.json").write_text(json.dumps({"tools": ["a", "b"]}))
        (target / "x.json").write_text(json.dumps({"tools": ["b", "a"]}))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert result.all_pass


def test_invalid_json_is_error():
    from cli_parity_validator import ParityValidator, ValidationConfig
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"; target = Path(d) / "target"
        base.mkdir(); target.mkdir()
        (base / "x.json").write_text("not json {{{")
        (target / "x.json").write_text(json.dumps({"tools": ["a"]}))
        result = ParityValidator(ValidationConfig(str(base), str(target))).validate()
        assert not result.all_pass
        assert any("parse error" in line for line in result.lines)

