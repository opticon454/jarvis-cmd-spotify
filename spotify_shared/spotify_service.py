"""Find something on Spotify and play it on the node's go-librespot receiver.

Search uses the client-credentials flow (no user login, catalogue only). Playback is one POST to go-librespot's local
API, which plays on the account the node is already paired with. No credential is stored here: the caller passes them in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_URL = "https://api.spotify.com/v1/search"
DEFAULT_LIBRESPOT = "http://127.0.0.1:3678"
KINDS = ["track", "album", "artist", "playlist"]
AUTO = "auto"  # unsure what was asked for: search all four and prefer an exact name, artists first
_TIMEOUT = 8


class SpotifyError(Exception):
    """A failure whose message is fit to speak."""


@dataclass
class Match:
    kind: str
    name: str
    by: str  # the artist, or the playlist owner; may be empty
    uri: str

    def spoken(self) -> str:
        return f"{self.name} by {self.by}" if self.by and self.kind in ("track", "album") else self.name


def build_query(query: str, kind: str, artist: Optional[str]) -> str:
    """Field filters narrow a track or album search when the artist was said; plain text otherwise."""
    query, artist = query.strip(), (artist or "").strip()
    if artist and kind in ("track", "album"):
        return f'{kind}:"{query}" artist:"{artist}"'
    return query


def _by(kind: str, item: dict) -> str:
    if kind in ("track", "album"):
        return ", ".join(a.get("name", "") for a in (item.get("artists") or [])[:2] if a)
    if kind == "playlist":
        return (item.get("owner") or {}).get("display_name") or ""
    return ""


class SpotifyService:
    def __init__(self, http: Any, client_id: str, client_secret: str, librespot_url: str = "", market: str = "AU") -> None:
        self._http = http
        self._id, self._secret = client_id, client_secret
        self._base = (librespot_url or DEFAULT_LIBRESPOT).rstrip("/")
        self._market = (market or "AU").strip().upper()
        self._token = ""
        self._expires = 0.0

    def _bearer(self) -> str:
        if self._token and time.time() < self._expires - 30:
            return self._token
        r = self._http.post(TOKEN_URL, data={"grant_type": "client_credentials"}, auth=(self._id, self._secret),
                            timeout=_TIMEOUT)
        if r.status_code in (400, 401):
            raise SpotifyError("Spotify rejected the client ID and secret. Check them in the app.")
        if r.status_code != 200:
            raise SpotifyError("Spotify isn't answering. Try again in a moment.")
        body = r.json()
        self._token = body["access_token"]
        self._expires = time.time() + float(body.get("expires_in", 3600))
        return self._token

    def search(self, query: str, kind: str = AUTO, artist: Optional[str] = None) -> Match:
        kind = kind if kind in KINDS else AUTO
        types = ",".join(KINDS) if kind == AUTO else kind
        params = {"q": build_query(query, kind, artist), "type": types, "limit": 5, "market": self._market}
        r = self._http.get(SEARCH_URL, params=params, headers={"Authorization": f"Bearer {self._bearer()}"},
                           timeout=_TIMEOUT)
        if r.status_code == 429:
            raise SpotifyError("Spotify is busy. Try again in a minute.")
        if r.status_code != 200:
            raise SpotifyError("Spotify search failed. Try again in a moment.")
        body = r.json()
        # Spotify can return null entries in the list (seen for playlists), so skip them.
        found = {k: [i for i in (body.get(f"{k}s") or {}).get("items", []) if i and i.get("uri")]
                 for k in (KINDS if kind == AUTO else [kind])}
        if not any(found.values()) and artist:  # the artist filter is strict; fall back to the plain words
            return self.search(f"{query} {artist}", kind, None)
        if kind == AUTO:
            for k in ("artist", "track", "album", "playlist"):  # an exact name wins; "play Muse" is the band, not a song
                exact = [i for i in found[k] if i.get("name", "").casefold() == query.strip().casefold()]
                if exact:
                    return Match(k, exact[0]["name"], _by(k, exact[0]), exact[0]["uri"])
        for k in ("track", "artist", "album", "playlist") if kind == AUTO else [kind]:
            if found.get(k):
                top = found[k][0]
                return Match(k, top.get("name", query), _by(k, top), top["uri"])
        raise SpotifyError(f"I couldn't find {query} on Spotify.")

    def play(self, match: Match) -> None:
        try:
            r = self._http.post(f"{self._base}/player/play", json={"uri": match.uri}, timeout=_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - requests' errors differ by version
            raise SpotifyError("This node's Spotify speaker isn't running.") from exc
        if r.status_code >= 400:
            raise SpotifyError("This node's Spotify speaker couldn't start that. Open Spotify once and pick this node.")
