"""Demo: validate parity between two schema directories."""
import json
import tempfile
from pathlib import Path
from cli_parity_validator import ParityValidator, ValidationConfig

# Create two schema dirs in temp space
with tempfile.TemporaryDirectory() as d:
    base = Path(d) / "base"
    target = Path(d) / "target"
    base.mkdir(); target.mkdir()

    # Write identical schemas
    schema = {"tools": ["exec_command", "batch_execute", "sysmon_health"]}
    (base / "alpha.json").write_text(json.dumps(schema))
    (target / "alpha.json").write_text(json.dumps(schema))

    # Add an extra tool in target
    schema_extra = {**schema, "tools": schema["tools"] + ["extra_tool"]}
    (target / "beta.json").write_text(json.dumps(schema_extra))
    (base / "beta.json").write_text(json.dumps(schema))

    config = ValidationConfig(base_dir=str(base), target_dir=str(target))
    validator = ParityValidator(config)
    result = validator.validate()

    print(f"Parity pass: {result.pass_count}/{result.total}")
    print(f"Violations:  {result.violations}")
    for v in result.violation_details:
        print(f"  ✗ {v}")
    if result.all_pass:
        print("All schemas match.")
