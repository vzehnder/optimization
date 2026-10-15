"""Isolated browser-test server for diagram exports and reach rule editing."""
import sys
from pathlib import Path
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app
from app.persistence import AnalystStore


if __name__ == "__main__":
    store = AnalystStore("sqlite:///:memory:")
    uvicorn.run(create_app(store=store, auth_enabled=True), host="127.0.0.1", port=8137)
