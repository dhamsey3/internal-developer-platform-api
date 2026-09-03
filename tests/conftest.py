import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_idp.db")
os.environ.setdefault("ENABLE_SANDBOX_SWEEPER", "false")
os.environ.setdefault("KUBERNETES_DRY_RUN", "true")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
