from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT = ROOT / "backend" / "scripts" / "start_production.sh"
RENDER_BLUEPRINT = ROOT / "render.yaml"


def _write_fake_command(directory: Path, name: str, exit_code: int = 0) -> None:
    command = directory / name
    command.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"{name} $*\" >> \"$CALL_LOG\"\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    command.chmod(0o755)


def _run_start_script(
    tmp_path: Path,
    *,
    alembic_exit: int = 0,
    python_exit: int = 0,
    venue_sync_mode: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "calls.log"

    _write_fake_command(bin_dir, "alembic", alembic_exit)
    _write_fake_command(bin_dir, "python", python_exit)
    _write_fake_command(bin_dir, "uvicorn")

    env = os.environ.copy()
    env.update(
        {
            "CALL_LOG": str(log_path),
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PORT": "4321",
        }
    )
    if venue_sync_mode is not None:
        env["VENUE_SYNC_MODE"] = venue_sync_mode
    else:
        env.pop("VENUE_SYNC_MODE", None)
    result = subprocess.run(
        ["sh", str(START_SCRIPT)],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    return result, calls


def test_render_startup_migrates_seeds_then_starts_server(tmp_path: Path) -> None:
    result, calls = _run_start_script(tmp_path)

    assert result.returncode == 0
    assert calls == [
        "alembic upgrade head",
        "python -m scripts.seed_reference_data",
        "uvicorn app.main:app --host 0.0.0.0 --port 4321",
    ]
    assert all("sync_parks" not in call for call in calls)


def test_render_startup_stops_when_migration_fails(tmp_path: Path) -> None:
    result, calls = _run_start_script(tmp_path, alembic_exit=23)

    assert result.returncode == 23
    assert calls == ["alembic upgrade head"]


def test_render_startup_stops_when_reference_seed_fails(tmp_path: Path) -> None:
    result, calls = _run_start_script(tmp_path, python_exit=24)

    assert result.returncode == 24
    assert calls == [
        "alembic upgrade head",
        "python -m scripts.seed_reference_data",
    ]


def test_render_startup_can_dry_run_venue_sync_before_server(tmp_path: Path) -> None:
    result, calls = _run_start_script(tmp_path, venue_sync_mode="dry-run")

    assert result.returncode == 0
    assert calls == [
        "alembic upgrade head",
        "python -m scripts.seed_reference_data",
        "python -m scripts.sync_venues --dry-run",
        "uvicorn app.main:app --host 0.0.0.0 --port 4321",
    ]


def test_render_startup_can_apply_venue_sync_before_server(tmp_path: Path) -> None:
    result, calls = _run_start_script(tmp_path, venue_sync_mode="apply")

    assert result.returncode == 0
    assert calls == [
        "alembic upgrade head",
        "python -m scripts.seed_reference_data",
        "python -m scripts.sync_venues --apply",
        "uvicorn app.main:app --host 0.0.0.0 --port 4321",
    ]


def test_render_startup_rejects_unknown_venue_sync_mode(tmp_path: Path) -> None:
    result, calls = _run_start_script(tmp_path, venue_sync_mode="surprise")

    assert result.returncode != 0
    assert "VENUE_SYNC_MODE" in result.stderr
    assert calls == [
        "alembic upgrade head",
        "python -m scripts.seed_reference_data",
    ]


def test_render_blueprint_uses_starter_web_and_free_singapore_postgres() -> None:
    blueprint = RENDER_BLUEPRINT.read_text(encoding="utf-8")

    assert "name: group-scheduling-app" in blueprint
    assert "type: web" in blueprint
    assert "runtime: docker" in blueprint
    assert "region: singapore" in blueprint
    assert "name: group-scheduling-app\n    runtime: docker\n    region: singapore\n    plan: starter" in blueprint
    assert "name: group-scheduling-postgres\n    region: singapore\n    plan: free" in blueprint
    assert blueprint.count("plan: starter") == 1
    assert blueprint.count("plan: free") == 1
    assert "dockerfilePath: ./Dockerfile" in blueprint
    assert "dockerCommand: sh scripts/start_production.sh" in blueprint
    assert "healthCheckPath: /ready" in blueprint
    assert "name: group-scheduling-postgres" in blueprint
    assert "property: connectionString" in blueprint


def test_render_blueprint_keeps_production_safe_values_and_secrets_out_of_git() -> None:
    blueprint = RENDER_BLUEPRINT.read_text(encoding="utf-8")

    for key, value in (
        ("APP_ENVIRONMENT", "production"),
        ("AUTO_CREATE_TABLES", '"false"'),
        ("DEBUG_AUTH_ENABLED", '"false"'),
        ("USE_MOCK_PROVIDERS", '"false"'),
        ("SESSION_COOKIE_SECURE", '"true"'),
        ("STATIC_DIR", "/app/static"),
    ):
        assert f"key: {key}\n        value: {value}" in blueprint

    assert "key: APP_SESSION_SECRET\n        generateValue: true" in blueprint
    for key in (
        "FRONTEND_BASE_URL",
        "ALLOWED_ORIGINS",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "ONEMAP_TOKEN",
    ):
        assert f"key: {key}\n        sync: false" in blueprint


def test_render_blueprint_gates_calendar_and_keeps_calendar_secrets_external() -> None:
    blueprint = RENDER_BLUEPRINT.read_text(encoding="utf-8")

    assert 'key: GOOGLE_CALENDAR_ENABLED\n        value: "false"' in blueprint
    assert "key: GOOGLE_CALENDAR_REDIRECT_URI\n        sync: false" in blueprint
    assert "key: GOOGLE_CALENDAR_CREDENTIAL_KEY\n        sync: false" in blueprint
    assert (
        "key: GOOGLE_CALENDAR_OAUTH_TRANSACTION_COOKIE_NAME\n"
        "        value: group_scheduler_calendar_oauth"
    ) in blueprint
    assert "fernet" not in blueprint.lower()
