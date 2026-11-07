"""Each settings module is loaded in a fresh interpreter so module-level env reads are isolated."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent

PROBE = (
    "import django; django.setup(); from django.conf import settings; "
    "print(settings.DEBUG, ','.join(settings.ALLOWED_HOSTS), settings.DATABASES['default']['ENGINE'])"
)

ENV_KEYS = ("DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DJANGO_ALLOWED_HOSTS", "DATABASE_URL")
PG_URL = "postgres://u:p@h:5432/d"


def _run(module: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env["DJANGO_SETTINGS_MODULE"] = f"numo9.settings.{module}"
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("module", ["dev", "test"])
def test_local_settings_load_without_env(module: str) -> None:
    result = _run(module)
    assert result.returncode == 0, result.stderr


def test_dev_defaults_debug_true() -> None:
    assert _run("dev").stdout.split()[0] == "True"


@pytest.mark.parametrize("module", ["staging", "prod"])
def test_deployed_settings_require_secret_key(module: str) -> None:
    result = _run(module, {"DJANGO_ALLOWED_HOSTS": "x", "DATABASE_URL": PG_URL})
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY is required" in result.stderr


@pytest.mark.parametrize("module", ["staging", "prod"])
@pytest.mark.parametrize("missing", ["DJANGO_ALLOWED_HOSTS", "DATABASE_URL"])
def test_deployed_settings_require_hosts_and_database(module: str, missing: str) -> None:
    env = {"DJANGO_SECRET_KEY": "s", "DJANGO_ALLOWED_HOSTS": "x", "DATABASE_URL": PG_URL}
    del env[missing]
    result = _run(module, env)
    assert result.returncode != 0
    assert f"{missing} is required" in result.stderr


@pytest.mark.parametrize("module", ["staging", "prod"])
def test_deployed_settings_load_from_env_and_force_debug_off(module: str) -> None:
    result = _run(
        module,
        {
            "DJANGO_SECRET_KEY": "s",
            "DJANGO_DEBUG": "true",
            "DJANGO_ALLOWED_HOSTS": "api.numo9.example, staging.numo9.example",
            "DATABASE_URL": PG_URL,
        },
    )
    assert result.returncode == 0, result.stderr
    debug, hosts, engine = result.stdout.split()
    assert debug == "False"
    assert hosts == "api.numo9.example,staging.numo9.example"
    assert engine == "django.db.backends.postgresql"


def test_invalid_boolean_rejected() -> None:
    result = _run("dev", {"DJANGO_DEBUG": "maybe"})
    assert result.returncode != 0
    assert "must be a boolean" in result.stderr
