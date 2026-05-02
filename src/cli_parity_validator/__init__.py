"""cli-parity-validator — Cross-CLI tool inventory parity checker."""
__version__ = "1.0.0"

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from cli_parity_validator.validator import (
    ValidationResult,
    ParityValidatorConfig,
    validate,
)


@dataclass
class ValidationConfig:
    """Simple directory-pair configuration for comparing JSON tool manifests.

    Args:
        base_dir: Directory containing the reference JSON schema files.
        target_dir: Directory containing the implementation JSON files to compare.
    """
    base_dir: str
    target_dir: str


class ParityValidator:
    """Compare JSON tool manifests between a base and target directory.

    Loads every ``*.json`` file from *base_dir*, reads the ``tools`` list,
    and checks whether *target_dir* contains matching files with the same set
    of tools.  Extra tools in *target* or missing tools from *base* both count
    as violations.

    Example::

        config = ValidationConfig("schemas/", "servers/")
        result = ParityValidator(config).validate()
        if not result.all_pass:
            print(result.violations, "violations found")
    """

    def __init__(self, config: ValidationConfig) -> None:
        self.config = config

    def validate(self) -> "ParityResult":
        base = Path(self.config.base_dir)
        target = Path(self.config.target_dir)
        errors: List[str] = []
        lines: List[str] = []
        total_base = 0
        total_target = 0
        file_count = 0
        pass_count = 0

        for base_file in sorted(base.glob("*.json")):
            file_count += 1
            target_file = target / base_file.name
            if not target_file.exists():
                errors.append(f"missing in target: {base_file.name}")
                continue

            try:
                base_data = json.loads(base_file.read_text())
                target_data = json.loads(target_file.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"parse error ({base_file.name}): {exc}")
                continue

            base_tools = set(base_data.get("tools", []))
            target_tools = set(target_data.get("tools", []))
            total_base += len(base_tools)
            total_target += len(target_tools)

            file_errors: List[str] = []
            for t in sorted(target_tools - base_tools):
                file_errors.append(f"extra in target ({base_file.name}): {t}")
            for t in sorted(base_tools - target_tools):
                file_errors.append(f"missing from target ({base_file.name}): {t}")

            if file_errors:
                errors.extend(file_errors)
            else:
                pass_count += 1

        ok = len(errors) == 0
        if ok:
            lines.append("OK: all schemas match")
        else:
            lines.extend(errors)

        return ParityResult(
            ok=ok,
            lines=lines,
            source_tool_count=total_base,
            manifest_tool_count=total_target,
            error_count=len(errors),
            total=file_count,
            pass_count=pass_count,
        )


@dataclass
class ParityResult(ValidationResult):
    """Extended result returned by :class:`ParityValidator`.

    Adds ``total`` (files checked) and ``pass_count`` (files without violations)
    to the base :class:`ValidationResult`.
    """
    total: int = 0
    pass_count: int = 0

    @property
    def violation_details(self) -> List[str]:
        """List of individual violation strings (same as ``lines`` when there are errors)."""
        return [line for line in self.lines if not line.startswith("OK:")]


__all__ = [
    "ValidationConfig",
    "ValidationResult",
    "ParityValidator",
    "ParityResult",
    "ParityValidatorConfig",
    "validate",
]
