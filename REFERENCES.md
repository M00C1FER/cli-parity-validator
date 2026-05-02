# Reference Projects

Projects studied during the 2026-05-02 audit cycle.

| Project | Stars | License | Pattern adopted |
|---------|-------|---------|----------------|
| [pre-commit/pre-commit](https://github.com/pre-commit/pre-commit) | ★12k | MIT | Exit-code contract: non-zero on any violation, regardless of number of errors — matches our strict-mode behaviour. |
| [adrienverge/yamllint](https://github.com/adrienverge/yamllint) | ★3k | GPL-3.0 | Structured `Problem` dataclass (file, line, col, message, level) — inspired `ValidationResult.lines` carrying both info and error lines distinguishable by prefix. |
| [zricethezav/gitleaks](https://github.com/zricethezav/gitleaks) | ★18k | MIT | `--no-banner --redact` flags make CI-safe output; adopted the same convention of a `--format json` flag for machine-readable output. |
| [aquasecurity/trivy](https://github.com/aquasecurity/trivy) | ★24k | Apache-2.0 | Cross-platform install via a single shell script that detects package manager (apt/dnf/apk/brew) and falls back gracefully — adopted in `install.sh`. |
| [koalaman/shellcheck](https://github.com/koalaman/shellcheck) | ★36k | GPL-3.0 | Static analysis without execution; pure-AST approach maps directly to our `load_python_mcp_tools` function that parses Python source without importing it. |
