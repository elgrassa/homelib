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


def test_ci_does_not_double_trigger_on_branch_push_and_a_pull_request() -> None:
    """A branch push plus an open PR must not fire two runs of the same commit.

    With `push` unscoped and `pull_request` both present, every push to a
    branch with an open PR starts two runs of the identical tree on the same
    host. They are not independent: run 12259 (pull_request) went red on six
    tests with `database "homelib_test_index" does not exist` while run 12258
    (push, same commit) passed, because the two raced over a shared throwaway
    database. The per-process database name fixes the race; scoping `push` to
    main and the v2 integration branch leaves feature-branch work on the PR
    trigger only.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    # PyYAML parses a bare `on:` key as the boolean True.
    triggers = workflow.get("on") or workflow[True]

    if "push" in triggers and "pull_request" in triggers:
        branches = (triggers.get("push") or {}).get("branches")
        assert branches == ["main", "v2"], (
            "`push` must be scoped to main and the v2 integration branch when "
            "`pull_request` is also a trigger, otherwise every feature-branch "
            f"push runs CI twice; got branches={branches!r}"
        )


def test_ci_declares_no_permissions_block() -> None:
    """Forgejo ignores `permissions:` and warns about it.

    It is GitHub Actions syntax. On this instance capabilities come from
    Authorized Integrations, so a `permissions: contents: read` block grants
    and restricts nothing while reading like a security control — the
    dangerous kind of no-op, because it invites the reader to believe the job
    is sandboxed.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())

    assert "permissions" not in workflow, "top-level `permissions:` is ignored by Forgejo"
    for name, job in workflow["jobs"].items():
        assert "permissions" not in job, (
            f"job {name!r} declares `permissions:`, which Forgejo ignores"
        )


def test_pre_push_hook_stays_fast_by_excluding_the_slow_markers() -> None:
    """The pre-push gate must not grow into the full suite.

    Quality gates live on the PR; this hook exists only to catch what is cheap
    to check and embarrassing to push. The moment it starts running the
    integration tests, the embedding-model loads or the coverage floor, it
    stops being a fast gate and people start reaching for --no-verify — at
    which point it protects nothing at all.
    """
    hook = REPO_ROOT / ".githooks/pre-push"
    assert hook.exists(), "pre-push hook is missing"
    assert hook.stat().st_mode & 0o111, "pre-push hook is not executable"

    body = hook.read_text()
    for marker in ("integration", "slow", "llm"):
        assert f"not {marker}" in body, f"pre-push hook no longer excludes `{marker}` tests"
    assert "--no-cov" in body, "pre-push hook runs the coverage floor; that belongs on the PR"


def _all_job_commands() -> dict[str, str]:
    """Every `run:` command in the workflow, keyed by job name."""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    return {
        name: " ".join(str(step.get("run", "")) for step in job["steps"])
        for name, job in workflow["jobs"].items()
    }


def test_some_ci_job_runs_the_full_suite_the_hook_skips() -> None:
    """Whatever the hook defers must actually be enforced somewhere.

    The fast local gate and the fast CI job are only safe because ONE job runs
    everything with the coverage floor. If every job picked up the marker
    exclusions, the integration tests would run nowhere at all and three
    separate gates would be green on a suite nobody executed.
    """
    jobs = _all_job_commands()
    full = {
        name: cmd
        for name, cmd in jobs.items()
        if "pytest" in cmd and "--cov" in cmd and "not integration" not in cmd
    }

    assert full, f"no CI job runs the full suite with the coverage floor; jobs are {sorted(jobs)}"


def test_the_full_suite_does_not_run_on_the_quick_lane() -> None:
    """The quick runner's daemon caps jobs at 25m and considers >12m wrong.

    A `timeout-minutes:` above the daemon's own cap is not honoured: the
    daemon kills the job and reports it CANCELLED rather than failed, which
    reads as a hang rather than a limit. Run 12292 died exactly that way. The
    corpus-scale suite therefore belongs on the heavy lane.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())

    for name, job in workflow["jobs"].items():
        commands = " ".join(str(step.get("run", "")) for step in job["steps"])
        if "--cov" in commands and "not integration" not in commands:
            labels = job["runs-on"]
            assert "quick" not in labels, (
                f"job {name!r} runs the full corpus-scale suite on the quick lane "
                f"({labels}), whose daemon will cancel it at 25 minutes"
            )


def test_compose_pins_the_ollama_context_window() -> None:
    """An unpinned context window fails silently, which is the worst kind.

    Ollama TRUNCATES an over-long prompt rather than erroring, so the model
    answers a question it was only shown part of and nothing in the response
    says so. `_MAX_CONTEXT_HITS` allows 20 passages, which reaches ~7,600
    tokens; the image default is far smaller.

    This was invisible during development because the dev machine has
    OLLAMA_CONTEXT_LENGTH set globally to 32768 — a local setting no reviewer
    inherits. Exactly the class of defect this repo keeps finding: something
    that works only because of state on one machine.
    """
    compose = yaml.safe_load((REPO_ROOT / "docker/docker-compose.yml").read_text())
    env = compose["services"]["ollama"].get("environment") or {}

    assert "OLLAMA_CONTEXT_LENGTH" in env, (
        "the ollama service does not pin OLLAMA_CONTEXT_LENGTH, so a reviewer "
        "gets the image default and silent prompt truncation"
    )


def test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve() -> None:
    """Streamlit runs `apps/ui/app.py` as a script, not as `python -m`.

    Without PYTHONPATH=/app, `from apps.ui.api_client import …` raises
    ModuleNotFoundError while `_stcore/health` still returns 200 — a
    false-healthy container that looks up but cannot render Crossroads.
    Pytest hides this via pyproject.toml `pythonpath = ["."]`; the image
    must pin the same root explicitly.
    """
    dockerfile = (REPO_ROOT / "docker/ui.Dockerfile").read_text()

    assert "PYTHONPATH=/app" in dockerfile, (
        "ui.Dockerfile must set PYTHONPATH=/app so `import apps` works when "
        "Streamlit executes apps/ui/app.py as a script"
    )


def test_streamlit_theme_pins_parchment_gold_from_mockups() -> None:
    """Peer-facing shell: parchment/ink/gold tokens from magic-library mockup.

    Without a committed `.streamlit/config.toml`, Compose and Community Cloud
    fall back to default white Streamlit chrome. Theme only — not the HTML
    rotunda (cut order: static door grid before rotating-room).
    """
    config = (REPO_ROOT / ".streamlit/config.toml").read_text()

    assert 'primaryColor = "#8a5b13"' in config
    assert 'backgroundColor = "#f7f0e3"' in config
    assert 'secondaryBackgroundColor = "#fffaf0"' in config
    assert 'textColor = "#241c16"' in config
    assert 'font = "serif"' in config


def test_ui_dockerfile_copies_streamlit_theme_into_image() -> None:
    """UI image only COPY'd apps/ + packages/; theme must be copied explicitly.

    Streamlit loads `$CWD/.streamlit/config.toml` from WORKDIR /app. Omitting
    this COPY leaves Compose on default white chrome while Cloud (full checkout)
    looks themed — a peer/local skew.
    """
    dockerfile = (REPO_ROOT / "docker/ui.Dockerfile").read_text()

    assert "COPY .streamlit/ .streamlit/" in dockerfile, (
        "ui.Dockerfile must COPY .streamlit/ so parchment theme reaches Compose"
    )


def test_compose_api_wires_homelib_sqlite_path_for_v2_doors() -> None:
    """Coffee Table / playlists 503 when the API container lacks the SQLite path.

    v2 routes call `_require_sqlite()`; health can still look green on Postgres
    while Crossroads doors return 503 HOMELIB_SQLITE_PATH. Compose must set the
    env and mount host `data/` so the seeded `homelib.sqlite` is reachable
    inside the container (and writable for progress / demo sessions).
    """
    compose = yaml.safe_load((REPO_ROOT / "docker/docker-compose.yml").read_text())
    api = compose["services"]["api"]
    env = api.get("environment") or {}
    volumes = api.get("volumes") or []

    assert "HOMELIB_SQLITE_PATH" in env, (
        "api service omits HOMELIB_SQLITE_PATH — Coffee Table and other v2 "
        "doors return 503 even when Postgres health is green"
    )
    assert any("data" in str(v) for v in volumes), (
        "api service must mount host data/ so HOMELIB_SQLITE_PATH resolves "
        f"inside the container; volumes={volumes!r}"
    )


def test_ci_pytest_forces_workspace_basetemp() -> None:
    """Hostexecutor lane TMPDIR is shared and can vanish mid-job.

    PR #18 run 87 failed hundreds of tests with FileNotFoundError under
    /Volumes/.../CI/tmp/quick/pytest-of-* even though job-level TMPDIR pointed
    at the workspace. The test steps must re-export TMPDIR from
    GITHUB_WORKSPACE and pass --basetemp so pytest never uses the shared dir.
    """
    workflow = CI_WORKFLOW.read_text()

    assert 'TMPDIR="${GITHUB_WORKSPACE:-$PWD}/.pytest-tmp"' in workflow, (
        "CI test steps must force TMPDIR under GITHUB_WORKSPACE; job-level env "
        "alone does not override the hostexecutor lane TMPDIR"
    )
    assert "--basetemp=" in workflow, (
        "CI pytest invocations must pin --basetemp under the workspace TMPDIR"
    )
