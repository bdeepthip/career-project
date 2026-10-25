"""
Start the app exactly the way you do (`python app.py` reading .env)
in a separate process, so a missing-.env bug can't hide behind test settings.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def run_startup(tmp_path, env_text):
    shutil.copytree(PROJECT / "jobtrack", tmp_path / "jobtrack")
    shutil.copy(PROJECT / "app.py", tmp_path / "app.py")
    if env_text is not None:
        (tmp_path / ".env").write_text(env_text)

    env = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "DATABASE")}
    return subprocess.run(
        [sys.executable, "-c", "import app; print('KEY=' + app.app.secret_key)"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )


def test_app_reads_secret_key_from_env_file(tmp_path):
    result = run_startup(tmp_path, "SECRET_KEY=from-dotenv-file\n")
    assert result.returncode == 0, result.stderr
    assert "KEY=from-dotenv-file" in result.stdout


def test_app_refuses_to_start_without_secret_key(tmp_path):
    result = run_startup(tmp_path, None)
    assert result.returncode != 0
    assert "SECRET_KEY is not set" in result.stderr
