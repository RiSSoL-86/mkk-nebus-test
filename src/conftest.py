import os
import subprocess
import sys
from pathlib import Path

import pytest

# Test env must be set before app imports; .env is not loaded.
os.environ.update(
    {
        "ENV_FILE": "",
        "PROJECT_NAME": "Payments tests",
        "DEBUG": "false",
        "API_KEY": "test-api-key",
        "POSTGRES_DB": "mkk_nebus_test",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5433",
        "RABBITMQ_DEFAULT_USER": "test_user",
        "RABBITMQ_DEFAULT_PASS": "test_password",
        "RABBITMQ_HOST": "127.0.0.1",
        "RABBITMQ_PORT": "55672",
    }
)


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database():
    root = Path(__file__).resolve().parents[1]
    for command in (["upgrade", "head"], ["check"]):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "src/alembic.ini",
                *command,
            ],
            cwd=root,
            check=True,
        )
