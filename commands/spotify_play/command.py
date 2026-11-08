"""SpotifyPlayCommand: "play <something> on Spotify" through the node's own Spotify Connect speaker."""

import sys
from pathlib import Path
from typing import Any, List, Optional

for _candidate in ("spotify_shared", "lib"):
    _lib_dir: str = str(Path.home() / ".jarvis" / "packages" / "spotify_play" / _candidate)
    if _lib_dir not in sys.path:
        sys.path.insert(0, _lib_dir)

try:
    from jarvis_log_client import JarvisLogger
except ImportError:
    import logging

    class JarvisLogger:  # noqa: E303
        def __init__(self, **kw: str) -> None:
            self._log = logging.getLogger(kw.get("service", __name__))

        def error(self, msg: str, **kw: object) -> None: self._log.error(msg)

from jarvis_command_sdk import (
    CommandExample,
    CommandResponse,
    IJarvisCommand,
    IJarvisSecret,
    JarvisPackage,
    JarvisParameter,
    JarvisSecret,
    JarvisStorage,
    RequestInformation,
)

from spotify_shared.spotify_service import KINDS, SpotifyError, SpotifyService

logger = JarvisLogger(service="spotify-play")


class SpotifyPlayCommand(IJarvisCommand):
    """Voice search and play on Spotify."""

    def __init__(self) -> None:
        self._storage = JarvisStorage("spotify_play")

    @property
    def command_name(self) -> str:
        return "spotify_play"

    @property
    def description(self) -> str:
        return (
            "Play a song, album, artist or playlist on Spotify. query is what to play, kind says what it is "
            "(track unless the user says album, artist or playlist), artist narrows a song or album. Use whenever "
            "the user says 'play ... on Spotify' or 'from Spotify'."
        )

    @property
    def associated_service(self) -> Optional[str]:
        return "Spotify"

    @property
    def keywords(self) -> List[str]:
        return ["spotify", "play", "play on spotify", "play from spotify", "put on", "song", "album", "playlist"]

    @property
    def parameters(self) -> List[JarvisParameter]:
        return [
            JarvisParameter("query", "string", required=True,
                            description="What to play: a song, album, artist or playlist name, without the word Spotify"),
            JarvisParameter("kind", "string", required=False, enum_values=KINDS,
                            description="track (default), album, artist or playlist"),
            JarvisParameter("artist", "string", required=False,
                            description="The artist, when the user named one for a song or album"),
        ]

    @property
    def required_secrets(self) -> List[IJarvisSecret]:
        return [
            JarvisSecret("SPOTIFY_CLIENT_ID", "Client ID of your own Spotify developer app", "integration", "string",
                         is_sensitive=False, friendly_name="Spotify client ID"),
            JarvisSecret("SPOTIFY_CLIENT_SECRET", "Client secret of that app", "integration", "string",
                         friendly_name="Spotify client secret"),
            JarvisSecret("SPOTIFY_LIBRESPOT_URL", "Local go-librespot API (default http://127.0.0.1:3678)",
                         "integration", "string", required=False, is_sensitive=False, friendly_name="Receiver URL"),
            JarvisSecret("SPOTIFY_MARKET", "Two-letter country code to search in (default AU)", "integration",
                         "string", required=False, is_sensitive=False, friendly_name="Market"),
        ]

    @property
    def required_packages(self) -> List[JarvisPackage]:
        return [JarvisPackage("requests", ">=2.31.0")]

    @property
    def setup_guide(self) -> Optional[str]:
        return (
            "## Connect Spotify\n\n"
            "The node plays through its own Spotify Connect speaker (go-librespot), already paired with your Premium "
            "account. This command only needs to *find* music, so it uses a free developer app of your own.\n\n"
            "1. Go to https://developer.spotify.com/dashboard and create an app. The redirect URI can be "
            "`http://127.0.0.1`; no user login is used.\n"
            "2. Copy the app's client ID and client secret into this command's settings.\n"
            "3. Leave the receiver URL empty unless go-librespot listens somewhere other than port 3678.\n"
        )

    def generate_prompt_examples(self) -> List[CommandExample]:
        return [
            CommandExample("Play Hysteria by Muse on Spotify",
                           {"query": "Hysteria", "kind": "track", "artist": "Muse"}, is_primary=True),
            CommandExample("Play the album Black Holes and Revelations", {"query": "Black Holes and Revelations", "kind": "album"}),
            CommandExample("Play some Muse from Spotify", {"query": "Muse", "kind": "artist"}),
            CommandExample("Play my Discover Weekly playlist on Spotify", {"query": "Discover Weekly", "kind": "playlist"}),
        ]

    def generate_adapter_examples(self) -> List[CommandExample]:
        rows = [
            ("Play Bohemian Rhapsody on Spotify", "Bohemian Rhapsody", "track", None),
            ("Play Thunderstruck by AC/DC from Spotify", "Thunderstruck", "track", "AC/DC"),
            ("Put on Back in Black by AC/DC on Spotify", "Back in Black", "track", "AC/DC"),
            ("Play the album Rumours on Spotify", "Rumours", "album", None),
            ("Play Abbey Road by The Beatles on Spotify", "Abbey Road", "album", "The Beatles"),
            ("Play Taylor Swift on Spotify", "Taylor Swift", "artist", None),
            ("Play some Tame Impala from Spotify", "Tame Impala", "artist", None),
            ("Play the Chill Hits playlist on Spotify", "Chill Hits", "playlist", None),
            ("Spotify, play Running Up That Hill", "Running Up That Hill", "track", None),
        ]
        out = []
        for text, query, kind, artist in rows:
            params = {"query": query, "kind": kind}
            if artist:
                params["artist"] = artist
            out.append(CommandExample(text, params))
        return out

    def _service(self) -> SpotifyService:
        import requests

        cid = self._storage.get_secret("SPOTIFY_CLIENT_ID")
        secret = self._storage.get_secret("SPOTIFY_CLIENT_SECRET")
        if not (cid and secret):
            raise SpotifyError("Spotify isn't set up yet. Add the client ID and secret in the app.")
        return SpotifyService(requests, cid, secret, self._storage.get_secret("SPOTIFY_LIBRESPOT_URL") or "",
                              self._storage.get_secret("SPOTIFY_MARKET") or "AU")

    def run(self, request_info: RequestInformation, **kwargs: Any) -> CommandResponse:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return CommandResponse.error_response(error_details="What would you like me to play?",
                                                  context_data={"error": "missing_query"})
        try:
            service = self._service()
            match = service.search(query, str(kwargs.get("kind") or "track").lower(), kwargs.get("artist"))
            service.play(match)
        except SpotifyError as exc:
            return CommandResponse.error_response(error_details=str(exc), context_data={"error": "spotify_error"})
        except Exception as exc:  # noqa: BLE001 - never raise into the voice pipeline
            logger.error("Spotify play failed", error=str(exc))
            return CommandResponse.error_response(error_details="Spotify didn't respond. Try again in a moment.",
                                                  context_data={"error": "unexpected", "detail": str(exc)})
        return CommandResponse.success_response(
            context_data={"message": f"Playing {match.spoken()}.", "uri": match.uri}, wait_for_input=False)
