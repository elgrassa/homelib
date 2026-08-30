"""Guards on the gates themselves.

A config file that looks like a guarantee but is wired into nothing is worse
than no config at all, because it gets believed. `.gitleaks.toml` sat in this
repository for a day enforced by nothing — no CI step, no hook, no just
recipe — while CHECKLIST.md listed secret scanning as done. When it was finally
run it reported four findings.

These tests assert the wiring, not the scan: the scan itself runs in `just
secrets` and in CI, where it belongs. Each one corresponds to a specific way
the guarantee was, or could quietly become, hollow.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GITLEAKS_CONFIG = REPO_ROOT / ".gitleaks.toml"
CI_WORKFLOW = REPO_ROOT / ".forgejo/workflows/ci.yml"
JUSTFILE = REPO_ROOT / "justfile"


def _gate_steps() -> list[dict[str, object]]:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    steps = workflow["jobs"]["gate"]["steps"]
    assert isinstance(steps, list)
    return steps


def test_gitleaks_allowlists_never_exempt_whole_files() -> None:
    """No allowlist may use `paths`.

    A `paths` entry exempts every finding in that file. The entries here exist
    to cover specific known-safe strings — a placeholder in .env.example, a
    metric name in the eval baseline — and scoping them by file instead would
    also allow a real credential pasted into the same file later. This was
    verified rather than assumed: a path-scoped version of this config
    suppressed a planted GitHub PAT and AWS key id that gitleaks otherwise
    reports, even with matchCondition = "AND".
    """
    config = tomllib.loads(GITLEAKS_CONFIG.read_text())

    allowlists: list[dict[str, object]] = []
    if isinstance(config.get("allowlist"), dict):
        allowlists.append(config["allowlist"])
    allowlists.extend(config.get("allowlists", []))

    assert allowlists, "gitleaks config defines no allowlists at all"
    offenders = [a.get("description", "<unnamed>") for a in allowlists if a.get("paths")]
    assert not offenders, f"allowlists exempt whole files via `paths`: {offenders}"


def test_gitleaks_runs_in_ci() -> None:
    """The scan is a CI step, not just a file sitting in the repo."""
    commands = " ".join(str(step.get("run", "")) for step in _gate_steps())

    assert "gitleaks" in commands, "no gitleaks step in the CI gate job"


def test_ci_checks_out_full_history_for_the_secret_scan() -> None:
    """A shallow clone would make the history scan vacuous.

    `gitleaks git` reads the git log. With actions/checkout's default depth of
    1 it sees a single commit and reports clean on every run — passing not
    because the history is clean but because it was never looked at.
    """
    checkout = next(
        step for step in _gate_steps() if "actions/checkout" in str(step.get("uses", ""))
    )
    options = checkout.get("with")
    assert isinstance(options, dict), "checkout step has no `with:` block, so no fetch-depth"

    assert options.get("fetch-depth") == 0, (
        "CI checkout is shallow, so the gitleaks history scan would see one commit"
    )


def test_just_ci_includes_the_secret_scan() -> None:
    """`just ci` is documented as "what CI runs"; it must actually match."""
    ci_line = next(line for line in JUSTFILE.read_text().splitlines() if line.startswith("ci:"))

    assert "secrets" in ci_line, f"`just ci` omits the secret scan: {ci_line!r}"
