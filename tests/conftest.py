"""A fake Spotify accounts/search server and go-librespot, so nothing touches the network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self) -> dict:
        return self._payload


class FakeHttp:
    """Stands in for the requests module: records calls and answers from `search_items`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.search_items: dict[str, list] = {}
        self.token_status = 200
        self.search_status = 200
        self.play_status = 204
        self.play_raises = False

    def post(self, url: str, **kw):
        self.calls.append(("POST", url, kw))
        if url.endswith("/api/token"):
            return FakeResponse(self.token_status, {"access_token": "tok", "expires_in": 3600})
        if self.play_raises:
            raise OSError("connection refused")
        return FakeResponse(self.play_status)

    def get(self, url: str, **kw):
        self.calls.append(("GET", url, kw))
        kind = kw["params"]["type"]
        return FakeResponse(self.search_status, {f"{kind}s": {"items": self.search_items.get(kw["params"]["q"], self.search_items.get("*", []))}})


@pytest.fixture
def http() -> FakeHttp:
    h = FakeHttp()
    h.search_items["*"] = [None, {"uri": "spotify:track:1", "name": "Hysteria", "artists": [{"name": "Muse"}]}]
    return h
