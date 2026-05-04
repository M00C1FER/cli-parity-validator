"""
CLI Parity Validator — MCP Tool Exposure Consistency Checker

Validates that tools declared in a JSON/YAML schema file are consistently
exposed across multiple MCP server implementations, using static AST analysis.

No runtime execution — pure static analysis.
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set

import yaml

__version__ = "1.0.0"


# ── AST-based tool extraction ──────────────────────────────────────────────

def _is_mcp_tool_decorator(decorator: ast.expr) -> bool:
    """Return True if this decorator is @mcp.tool or @mcp.tool(...)."""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "tool"
        and isinstance(target.value, ast.Name)
        and target.value.id == "mcp"
    )


def _collect_tools_from_tree(tree: ast.AST) -> Set[str]:
    """Extract tool names from @mcp.tool() decorator and mcp.tool()(fn) call patterns."""
    tools: Set[str] = set()
    for node in ast.walk(tree):
        # Pattern 1: @mcp.tool() / @mcp.tool decorator on function definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                if _is_mcp_tool_decorator(d):
                    # Honour explicit name= kwarg: @mcp.tool(name="foo")
                    if isinstance(d, ast.Call):
                        name_kwarg = next(
                            (kw.value for kw in d.keywords if kw.arg == "name"),
                            None,
                        )
                        if isinstance(name_kwarg, ast.Constant) and isinstance(name_kwarg.value, str):
                            tools.add(name_kwarg.value)
                        else:
                            tools.add(node.name)
                    else:
                        tools.add(node.name)
                    break
        # Pattern 2: mcp.tool()(some_function) at module level
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            outer = node.value  # mcp.tool()(fn)
            if (
                isinstance(outer.func, ast.Call)
                and isinstance(outer.func.func, ast.Attribute)
                and outer.func.func.attr == "tool"
                and isinstance(outer.func.func.value, ast.Name)
                and outer.func.func.value.id == "mcp"
                and len(outer.args) == 1
                and isinstance(outer.args[0], ast.Name)
            ):
                tools.add(outer.args[0].id)
    return tools


def load_python_mcp_tools(paths: List[Path]) -> Set[str]:
    """Extract @mcp.tool-decorated tool names from a list of Python source files.

    Missing paths are silently skipped; callers that need to surface
    unreachable-file warnings should check path existence before calling
    (e.g. the :func:`validate` function does this and emits a warning).
    """
    tools: Set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        tools |= _collect_tools_from_tree(tree)
    return tools


def load_schema(path: Path) -> dict:
    """Load a YAML or JSON schema file into a dict."""
    with path.open("r", encoding="utf-8") as fh:
        try:
            if path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(fh) or {}
            else:
                data = json.load(fh) or {}
        except (yaml.YAMLError, json.JSONDecodeError) as exc:
            raise ValueError(f"Malformed schema file '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {path}")
    return data


def _extract_tool_names(entries: list) -> Set[str]:
    """Extract tool names from a YAML tool list, skipping malformed entries."""
    result: Set[str] = set()
    for entry in (entries or []):
        if isinstance(entry, str):
            result.add(entry)
    return result


def sorted_lines(items: Iterable[str], prefix: str) -> List[str]:
    return [f"{prefix}{name}" for name in sorted(items)]


# ── Validation result ──────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of a validation run."""
    ok: bool
    lines: List[str]
    source_tool_count: int = 0
    manifest_tool_count: int = 0
    error_count: int = 0

    @property
    def all_pass(self) -> bool:
        """Alias for ``ok`` — True when no violations were found."""
        return self.ok

    @property
    def violations(self) -> int:
        """Alias for ``error_count`` — number of parity violations detected."""
        return self.error_count


# ── Core validator ─────────────────────────────────────────────────────────

@dataclass
class ParityValidatorConfig:
    """Configuration for a parity validation run."""
    server_paths: List[Path] = field(default_factory=list)
    schema_path: Optional[Path] = None
    agent_tools_dir: Optional[Path] = None
    required_tools: Set[str] = field(default_factory=set)
    required_roles: List[str] = field(default_factory=list)
    server_names: List[str] = field(default_factory=lambda: ["default"])
    strict: bool = False


def validate(config: ParityValidatorConfig) -> ValidationResult:
    """
    Validate tool exposure consistency.

    Checks:
    1. Tools in Python source match tools in the YAML/JSON schema manifest
    2. Role YAML files only reference tools that exist in the source
    3. Required tools are present in specified roles
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []

    # Warn about unreachable source files before extraction so callers
    # get explicit feedback rather than silent false-negatives.
    for p in config.server_paths:
        if not p.exists():
            warnings.append(f"source file not found (skipped): {p}")

    # Extract tools from Python source files
    source_tools = load_python_mcp_tools(config.server_paths)
    info.append(f"source tools (@mcp.tool): {len(source_tools)}")

    manifest_tools: Set[str] = set()

    # Validate against schema manifest if provided
    if config.schema_path and config.schema_path.exists():
        unified = load_schema(config.schema_path)
        servers_section = unified.get("servers", {})
        for sname in config.server_names:
            manifest_tools |= _extract_tool_names(
                servers_section.get(sname, {}).get("tools", [])
            )
        info.append(f"manifest tools ({config.schema_path.name}): {len(manifest_tools)}")

        missing_from_manifest = source_tools - manifest_tools
        extra_in_manifest = manifest_tools - source_tools
        if missing_from_manifest:
            errors.append(f"tools missing from {config.schema_path.name}:")
            errors.extend(sorted_lines(missing_from_manifest, "  - "))
        if extra_in_manifest:
            errors.append(f"stale tools present in {config.schema_path.name}:")
            errors.extend(sorted_lines(extra_in_manifest, "  - "))

    # Validate agent/role YAML files if directory provided
    if config.agent_tools_dir and config.agent_tools_dir.is_dir():
        for role_file in sorted(config.agent_tools_dir.glob("*.yaml")):
            role_data = load_schema(role_file)
            tool_entries = role_data.get("tools") or []
            if not isinstance(tool_entries, list):
                errors.append(f"{role_file.name}: tools is not a list")
                continue

            role_tool_names: Set[str] = set()
            for entry in tool_entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if not isinstance(name, str):
                    continue
                role_tool_names.add(name)

                mcp_server = entry.get("mcp_server", "")
                if mcp_server in config.server_names and source_tools and name not in source_tools:
                    errors.append(
                        f"{role_file.name}: references unknown tool '{name}' on server '{mcp_server}'"
                    )

            if role_file.name in config.required_roles and config.required_tools:
                missing_required = config.required_tools - role_tool_names
                if missing_required:
                    errors.append(
                        f"{role_file.name}: missing required tools for parity"
                    )
                    errors.extend(sorted_lines(missing_required, "  - "))

    # Build output lines
    lines: List[str] = []
    lines.extend(info)
    if warnings:
        lines.append("warnings:")
        lines.extend(warnings)
    if errors:
        lines.append("errors:")
        lines.extend(errors)
    else:
        lines.append("OK: tool exposure and role mappings are consistent.")

    ok = len(errors) == 0 and (len(warnings) == 0 or not config.strict)
    return ValidationResult(
        ok=ok,
        lines=lines,
        source_tool_count=len(source_tools),
        manifest_tool_count=len(manifest_tools),
        error_count=len(errors),
    )


def main() -> None:  # noqa: C901 — intentionally compact CLI glue
    """CLI entry point: ``cli-parity``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="cli-parity",
        description="Validate MCP tool exposure consistency across CLI agents.",
    )
    parser.add_argument(
        "--version", action="version", version=f"cli-parity-validator {__version__}"
    )
    parser.add_argument(
        "--schema",
        type=Path,
        metavar="FILE",
        help="YAML/JSON schema file declaring expected tools per server.",
    )
    parser.add_argument(
        "--agent-tools",
        dest="agent_tools",
        type=Path,
        metavar="DIR",
        help="Directory of per-agent YAML role files to validate.",
    )
    parser.add_argument(
        "--required-tools",
        dest="required_tools",
        type=Path,
        metavar="FILE",
        help="Text file (one tool per line) of required tools.",
    )
    parser.add_argument(
        "--server",
        nargs="+",
        default=["default"],
        metavar="NAME",
        help="Server name(s) to check in the schema (default: 'default').",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (non-zero exit on any warning).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        metavar="FILE",
        help="Python source files to scan for @mcp.tool decorators.",
    )

    args = parser.parse_args()

    required_tools: Set[str] = set()
    if args.required_tools and Path(args.required_tools).exists():
        required_tools = {
            line.strip()
            for line in Path(args.required_tools).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

    config = ParityValidatorConfig(
        server_paths=list(args.paths or []),
        schema_path=args.schema,
        agent_tools_dir=args.agent_tools,
        required_tools=required_tools,
        server_names=args.server,
        strict=args.strict,
    )

    result = validate(config)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "violations": result.violations,
                    "source_tool_count": result.source_tool_count,
                    "manifest_tool_count": result.manifest_tool_count,
                    "lines": result.lines,
                },
                indent=2,
            )
        )
    else:
        for line in result.lines:
            print(line)

    sys.exit(0 if result.ok else 1)
