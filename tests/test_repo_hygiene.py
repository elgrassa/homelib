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
    main (the single long-lived branch since `v2` was collapsed into it on
    2026-09-06) leaves feature-branch work on the PR trigger only.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    # PyYAML parses a bare `on:` key as the boolean True.
    triggers = workflow.get("on") or workflow[True]

    if "push" in triggers and "pull_request" in triggers:
        branches = (triggers.get("push") or {}).get("branches")
        assert branches == ["main"], (
            "`push` must be scoped to main alone when `pull_request` is also a "
            "trigger, otherwise every feature-branch push runs CI twice; the "
            f"`v2` integration branch is retired; got branches={branches!r}"
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


def test_run_agent_is_not_on_the_demo_request_path() -> None:
    """`homelib_rag.agent.run_agent`'s tool table binds `get_block` to the
    Postgres implementation. That is only safe because no request path in
    `apps/` calls `run_agent` — the API wires `get_block`/`search_catalog`
    through `Deps`, which dispatch on HOMELIB_SQLITE_PATH. Pin the fact, so a
    future "just call run_agent" lands with the dispatch work, not without.
    """
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in (REPO_ROOT / "apps").rglob("*.py")
        if "tests" not in path.parts and "run_agent" in path.read_text()
    ]
    assert offenders == [], f"run_agent referenced on a request path: {offenders}"


def _compose() -> dict[str, object]:
    compose = yaml.safe_load((REPO_ROOT / "docker/docker-compose.yml").read_text())
    assert isinstance(compose, dict)
    return compose


def test_compose_api_pins_selfhosted_like_ui() -> None:
    """`.env.example` ships `APP_MODE=demo` for the Community Cloud path. The
    api service used to read `${APP_MODE:-selfhosted}`, so a reviewer who
    copied `.env.example` got a demo-mode API that minted a fresh anonymous
    principal for every header-less request — an always-empty Coffee Table
    on the reviewer stack. Both containers pin selfhosted; the env var is for
    the Streamlit-only demo process."""
    services = _compose()["services"]
    assert isinstance(services, dict)
    for name in ("api", "ui"):
        env = services[name]["environment"]
        assert env["APP_MODE"] == "selfhosted", f"{name}: {env.get('APP_MODE')!r}"


def test_compose_ingest_can_write_sqlite_seed() -> None:
    """Hygiene (string/structure match, not behavioural). The api service reads
    `/data/homelib.sqlite`; the ingest one-shot must be able to write it: the
    env var is set and the data mount is not read-only. The image CMD stays
    the Postgres pipeline — the SQLite seed is `just seed-sqlite`, a second
    one-shot, so a cold clone never embeds the corpus twice in one process."""
    services = _compose()["services"]
    assert isinstance(services, dict)
    ingest = services["ingest"]
    assert ingest["environment"]["HOMELIB_SQLITE_PATH"] == "/data/homelib.sqlite"
    data_mounts = [v for v in ingest["volumes"] if str(v).startswith("../data:")]
    assert data_mounts == ["../data:/data"], data_mounts
    dockerfile = (REPO_ROOT / "docker/ingest.Dockerfile").read_text()
    assert "apps.ingest.pipeline" in dockerfile
    assert "sqlite_pipeline" not in dockerfile, "SQLite seed is a separate one-shot, not the CMD"
    assert "python -m apps.ingest.sqlite_pipeline" in JUSTFILE.read_text()


def test_drill_asserts_seed_counts_via_health() -> None:
    """The drill used to seed Postgres, then ask the API — which reads SQLite —
    and never checked the counts. It must seed SQLite through the compose
    one-shot (not a host `uv run`) and assert 18 books / 9168 chunks."""
    drill = (REPO_ROOT / "scripts/cold_clone_drill.sh").read_text()
    assert "run --rm --build ingest python -m apps.ingest.sqlite_pipeline" in drill
    assert "/health" in drill
    assert "18" in drill and "9168" in drill
    assert "uv run" not in drill


def test_seed_one_shots_build_the_profile_image_before_running() -> None:
    """Hygiene pin. `compose up --build` builds only the services it starts; the
    ingest service is behind the `seed` profile, so `run --rm ingest` reuses any
    image already tagged for the project. The first drill after PR-A ran a
    five-day-old ingest image and failed with "No module named
    apps.ingest.sqlite_pipeline". Every seed one-shot must pass `--build`."""
    drill = (REPO_ROOT / "scripts/cold_clone_drill.sh").read_text()
    justfile = JUSTFILE.read_text()
    for text, name in ((drill, "drill"), (justfile, "justfile")):
        runs = [line for line in text.splitlines() if "--profile seed run" in line]
        assert runs, f"{name}: no seed one-shot found"
        for line in runs:
            assert "--build" in line, f"{name}: seed one-shot without --build: {line.strip()}"


def test_drill_verifies_monitoring_via_observatory_not_grafana_panel_count() -> None:
    """Hygiene pin (string-match, not behavioural): on the tip path the API
    logs asks to SQLite, so Grafana's Postgres panels chart an unwritten table.
    Counting provisioned panels proved nothing about the ask the drill just
    made. The drill must read `GET /v1/observatory` and assert the ask landed
    in `queries_over_time`.
    """
    drill = (REPO_ROOT / "scripts/cold_clone_drill.sh").read_text()
    assert "/v1/observatory" in drill
    assert "queries_over_time" in drill
    assert '["dashboard"]["panels"]' not in drill, (
        "drill still asserts on Grafana panel count — vacuous on the SQLite path"
    )


def test_specs_ui_door_list_matches_crossroads_doors() -> None:
    """`specs/ui.md` describes the doors; the code defines them. The spec's door
    table must list exactly `CROSSROADS_DOORS`, in order — a door added or
    renamed in one place and not the other fails here, not in a review."""
    from apps.ui.view_model import CROSSROADS_DOORS

    text = (REPO_ROOT / "specs/ui.md").read_text()
    section = text.split("## The doors", 1)[1].split("\n## ", 1)[0]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith(("| Door", "|---"))
    ]
    doors = tuple(line.split("|")[1].strip() for line in rows)
    assert doors == tuple(CROSSROADS_DOORS)


def test_personal_books_dir_is_untracked_and_ignored() -> None:
    """Purchased ebooks never leave this machine: `data/books/` and
    `data/private/` are ignored and nothing under them is tracked."""
    import subprocess

    ignore = (REPO_ROOT / ".gitignore").read_text()
    assert "data/books/" in ignore
    assert "data/private/" in ignore
    tracked = subprocess.run(
        ["git", "ls-files", "data/books", "data/private"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tracked.strip() == "", tracked


def test_no_dotenv_file_is_tracked() -> None:
    """Only `.env.example` may be tracked; a real `.env*` carries keys."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", ".env", ".env.*", "**/.env", "**/.env.*"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert all(path.endswith(".env.example") for path in tracked), tracked


def test_ci_graph_guard_job_exists() -> None:
    """PRs must not carry a private graphify-out/ snapshot (studio-kit #47)."""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    jobs = workflow["jobs"]
    assert "graph-guard" in jobs, "ci.yml is missing the graph-guard job"
    guard = jobs["graph-guard"]
    assert guard.get("runs-on") == ["macos-arm64", "quick"]
    body = CI_WORKFLOW.read_text()
    assert "graphify-out/" in body
    assert "github.event_name == 'pull_request'" in body or "pull_request" in str(
        guard.get("if", "")
    )


def test_ci_graph_refresh_pushes_to_current_protected_branch() -> None:
    """Homelib refreshes on the pushed protected ref — main, and only main.

    The refresh stays keyed on GITHUB_REF_NAME (a future integration branch
    is a one-line case addition), but since `v2` was collapsed into main on
    2026-09-06 the only accepted ref is main: a stray `v2)` case would resurrect
    the two-branch ping-pong the moment someone recreates that branch.
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    jobs = workflow["jobs"]
    assert "graph-refresh" in jobs, "ci.yml is missing the graph-refresh job"
    refresh = jobs["graph-refresh"]
    assert refresh.get("runs-on") == ["macos-arm64", "quick"]
    body = CI_WORKFLOW.read_text()
    assert "GITHUB_REF_NAME" in body, "graph-refresh must key off the pushed ref"
    assert "HEAD:${ref}" in body or 'HEAD:"${ref}"' in body or "HEAD:${ref}" in body
    # Must not be the unadapted template that only ever targets main.
    assert "git push origin HEAD:main" not in body or "HEAD:${ref}" in body
    script = _graph_refresh_script()
    assert "main)" in script, "refresh must accept the main ref"
    assert "v2)" not in script, "the retired v2 integration branch must not be a refresh target"


def _graph_refresh_script() -> str:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    steps = workflow["jobs"]["graph-refresh"]["steps"]
    return str(next(step["run"] for step in reversed(steps) if "run" in step))


def _run_graph_refresh(tmp_path: Path, ref: str) -> tuple[int, str, bool, str]:
    """Execute the graph-refresh step script in a scratch repo with a stub graphify.

    Returns (exit code, combined output, whether graphify was invoked, and the
    scratch remote's tip for `ref` or "" when nothing was pushed).
    """
    import os
    import subprocess

    # Git hooks export GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE; inherited, they
    # make `git init` re-init the *hook's* repo (seen in the pre-push gate).
    base_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    base_env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig-empty")
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"

    def run(args: list[str], cwd: Path) -> None:
        subprocess.run(args, cwd=cwd, env=base_env, check=True)

    run(["git", "init", "-q", "--bare", str(remote)], tmp_path)
    run(["git", "init", "-q", "-b", ref, str(work)], tmp_path)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    (work / "README.md").write_text("scratch\n")
    run([*git, "add", "README.md"], work)
    run([*git, "commit", "-q", "-m", "seed"], work)
    run(["git", "remote", "add", "origin", str(remote)], work)
    run(["git", "push", "-q", "origin", f"HEAD:{ref}"], work)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "graphify-called"
    stub = bindir / "graphify"
    stub.write_text(
        "#!/bin/sh\n"
        f"touch '{marker}'\n"
        "mkdir -p graphify-out\n"
        "sha=$(git rev-parse HEAD)\n"
        'printf \'{"built_at_commit": "%s", "nodes": []}\n\' "$sha" '
        "> graphify-out/graph.json\n"
    )
    stub.chmod(0o755)
    env = {**base_env, "PATH": f"{bindir}:{base_env['PATH']}", "GITHUB_REF_NAME": ref}
    proc = subprocess.run(
        ["bash", "-e", "-c", _graph_refresh_script()],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    tip = subprocess.run(
        ["git", "log", "-1", "--format=%s", ref],
        cwd=remote,
        env=base_env,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return proc.returncode, proc.stdout + proc.stderr, marker.exists(), tip


def test_ci_graph_refresh_commits_on_main(tmp_path: Path) -> None:
    """Behavioural: a push to main rebuilds, commits and pushes the graph.

    Until 2026-09-06 main was a pure fast-forward of the `v2` integration
    branch and deliberately never refreshed (rebuilds are not byte-stable, so
    refreshing on both forked them — runs 13318/13319). With `v2` collapsed
    into main, main is the one branch that owns the committed graph.
    """
    code, out, called, tip = _run_graph_refresh(tmp_path, "main")
    assert code == 0, out
    assert called, "graph-refresh must invoke graphify on main"
    assert tip == "chore(graph): refresh main post-merge", out


def test_ci_graph_refresh_refuses_the_retired_v2_ref(tmp_path: Path) -> None:
    """Behavioural: a push to a recreated `v2` neither rebuilds nor pushes.

    A second refreshed branch is exactly the ping-pong that was fixed; the
    step must treat `v2` like any other non-protected ref (warn, exit 0).
    """
    code, out, called, tip = _run_graph_refresh(tmp_path, "v2")
    assert code == 0, out
    assert not called, "graph-refresh must not invoke graphify on the retired v2"
    assert tip == "seed", f"graph-refresh pushed to v2: {tip!r}"


def test_ci_graph_refresh_commits_the_bootstrap_graph() -> None:
    """Hygiene (string-match): the freshness short-circuit must not fire on an
    untracked graph. `git diff -- graphify-out/graph.json` is empty while the
    directory is untracked, so a bare diff test printed "graph is fresh" on the
    first v2 refresh (run 13219) and the bootstrap graph never landed.
    """
    body = CI_WORKFLOW.read_text()
    fresh = body.index('echo "graph is fresh"')
    guard = body.rfind("git ls-files --error-unmatch graphify-out/graph.json", 0, fresh)
    assert guard != -1, "graph-refresh must check the graph is tracked before calling it fresh"
    assert "git add graphify-out/" in body


def test_graphifyignore_excludes_generated_and_data_paths() -> None:
    """Indexer excludes: do not confuse with .gitignore — graphify-out/ is committed."""
    ignore = (REPO_ROOT / ".graphifyignore").read_text()
    for path in (".venv/", "graphify-out/", "data/", ".pytest-tmp/"):
        assert path in ignore, f".graphifyignore missing {path!r}"


def test_claude_md_routes_named_symbols_through_graphify_explain() -> None:
    """Without 1bis, a committed graph is dead weight — sessions still crawl."""
    text = (REPO_ROOT / "CLAUDE.md").read_text()
    assert "graphify explain" in text
    assert "graphify-out/graph.json" in text  # the ban target
    assert "Never" in text or "never" in text
    assert len(text.splitlines()) <= 70
