from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.main import create_app
from app.persistence import AnalystStore


def main() -> None:
    store = AnalystStore("sqlite:///:memory:")
    app = create_app(store=store, auth_enabled=True)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("REACT_SMOKE_PORT", "8123")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
