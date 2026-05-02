# CLI Parity Validator

> Validate that multiple AI CLI tools expose consistent, expected toolsets — catch drift before it breaks pipelines.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20WSL%20%7C%20Termux-lightgrey)](install.sh)

## What It Does

In multi-agent AI systems, different CLIs (Claude, Gemini, Copilot) each expose tool APIs via MCP servers. When tools go missing or change signatures, downstream agents fail silently. CLI Parity Validator compares your actual live tool registries against a declared schema and emits structured drift reports.

**Key capabilities:**
- Compare tool lists across multiple MCP server registries
- Validate against a YAML-declared expected schema
- Check per-agent tool access policies (allow/deny lists)
- Flag missing required tools, unexpected extras, signature mismatches
- Exit code semantics for CI/CD pipeline integration

## Quick Start

```bash
bash install.sh
cli-parity --help
cli-parity --schema schema.yaml --strict
```

## Installation (all platforms)

| Platform | Method |
|----------|--------|
| Linux / WSL | `bash install.sh` (uses `apt-get`/`dnf`/`pacman`) |
| Termux (Android) | `bash install.sh` (uses `pkg`) |
| pip (manual) | `pip install .` inside a venv |

```bash
git clone https://github.com/M00C1FER/cli-parity-validator
cd cli-parity-validator
bash install.sh
```

## Usage

```bash
# Validate against a schema file
cli-parity --schema schema.yaml

# Check only specific agent tool directories
cli-parity --agent-tools ./agent-tools/ --required-tools core_tools.txt

# Strict mode: any drift = non-zero exit
cli-parity --schema schema.yaml --strict

# JSON output for CI parsing
cli-parity --schema schema.yaml --format json
```

## Schema Format

```yaml
# schema.yaml
servers:
  nexus-ipc:
    required_tools:
      - context_store
      - context_read
      - call_agent
  nexus-research:
    required_tools:
      - research_decompose
      - research_search
agents:
  hotel:
    deny_tools:
      - deep_research
      - execute_rust_code
```

## Architecture (MOSA)

```
cli-parity-validator/
├── src/cli_parity_validator/
│   ├── validator.py       # Core validation logic
│   └── __init__.py
├── install.sh             # Cross-platform wizard
├── examples/demo.py       # Runnable demo
└── TOOLS.md               # Tool reference
```

**Go refactor candidate:** The validator's hot path (YAML diff, JSON comparison) is well-suited for a single-binary Go implementation for easier distribution. See TOOLS.md for planned Go port.

## Cross-Platform Notes

- **Linux/WSL:** Full feature set, `fcntl`-based locking
- **Termux:** Full feature set, no `sudo` required
- **Windows (native):** Not supported — use WSL

## Tools Reference

See [TOOLS.md](TOOLS.md) for recommended tools and installation walkthrough.

## License

[MIT](LICENSE)
