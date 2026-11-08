import pytest

from commands.spotify_play.command import SpotifyPlayCommand
from jarvis_command_sdk import IJarvisCommand
from spotify_shared.spotify_service import Match, SpotifyError, SpotifyService, build_query


def service(http, url=""):
    return SpotifyService(http, "id", "secret", url)


class TestQuery:
    def test_artist_filters_a_track_but_not_an_artist_search(self):
        assert build_query("Hysteria", "track", "Muse") == 'track:"Hysteria" artist:"Muse"'
        assert build_query("Muse", "artist", "Muse") == "Muse"
        assert build_query(" Rumours ", "album", None) == "Rumours"


class TestSearch:
    def test_skips_null_entries_and_names_the_artist(self, http):
        m = service(http).search("Hysteria", "track", "Muse")
        assert (m.uri, m.spoken()) == ("spotify:track:1", "Hysteria by Muse")

    def test_unknown_kind_searches_tracks(self, http):
        service(http).search("x", "podcast")
        assert http.calls[-1][2]["params"]["type"] == "track"

    def test_token_is_fetched_once_and_uses_the_secret_as_basic_auth(self, http):
        s = service(http)
        s.search("a"), s.search("b")
        tokens = [c for c in http.calls if c[1].endswith("/api/token")]
        assert len(tokens) == 1 and tokens[0][2]["auth"] == ("id", "secret")

    def test_artist_filter_falls_back_to_plain_words(self, http):
        http.search_items = {'track:"Hysteria" artist:"Muze"': [],
                             "Hysteria Muze": [{"uri": "spotify:track:2", "name": "Hysteria", "artists": []}]}
        assert service(http).search("Hysteria", "track", "Muze").uri == "spotify:track:2"

    def test_no_result_is_spoken(self, http):
        http.search_items = {"*": [None]}
        with pytest.raises(SpotifyError, match="couldn't find Nothing"):
            service(http).search("Nothing")

    @pytest.mark.parametrize("field,status,text", [("token_status", 401, "rejected"), ("token_status", 500, "isn't answering"),
                                                   ("search_status", 429, "busy"), ("search_status", 500, "search failed")])
    def test_failures_are_speakable(self, http, field, status, text):
        setattr(http, field, status)
        with pytest.raises(SpotifyError, match=text):
            service(http).search("x")


class TestPlay:
    def test_posts_the_uri_to_the_receiver(self, http):
        service(http, "http://10.0.0.5:9999/").play(Match("track", "n", "", "spotify:track:1"))
        method, url, kw = http.calls[-1]
        assert (url, kw["json"]) == ("http://10.0.0.5:9999/player/play", {"uri": "spotify:track:1"})

    def test_default_receiver_is_port_3678(self, http):
        service(http).play(Match("track", "n", "", "u"))
        assert http.calls[-1][1] == "http://127.0.0.1:3678/player/play"

    def test_receiver_down_and_refusal_are_speakable(self, http):
        http.play_raises = True
        with pytest.raises(SpotifyError, match="isn't running"):
            service(http).play(Match("track", "n", "", "u"))
        http.play_raises, http.play_status = False, 500
        with pytest.raises(SpotifyError, match="couldn't start"):
            service(http).play(Match("track", "n", "", "u"))


class TestCommand:
    @pytest.fixture
    def command(self, http, monkeypatch):
        cmd = SpotifyPlayCommand()
        monkeypatch.setattr(cmd, "_service", lambda: service(http))
        return cmd

    def test_interface(self):
        cmd = SpotifyPlayCommand()
        assert isinstance(cmd, IJarvisCommand) and cmd.command_name == "spotify_play"
        assert {s.key for s in cmd.required_secrets} == {"SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
                                                         "SPOTIFY_LIBRESPOT_URL", "SPOTIFY_MARKET"}
        assert {s.key for s in cmd.required_secrets if s.is_sensitive} == {"SPOTIFY_CLIENT_SECRET"}
        assert cmd.generate_adapter_examples() and cmd.generate_prompt_examples()

    def test_plays_and_confirms(self, command, http):
        r = command.run(None, query="Hysteria", kind="track", artist="Muse")
        assert r.context_data["message"] == "Playing Hysteria by Muse." and http.calls[-1][1].endswith("/player/play")

    def test_missing_query_asks(self, command):
        assert "What would you like" in command.run(None).error_details

    def test_unconfigured_says_so(self, monkeypatch):
        cmd = SpotifyPlayCommand()
        monkeypatch.setattr(cmd._storage, "get_secret", lambda k: None, raising=False)
        assert "isn't set up" in cmd.run(None, query="x").error_details

    def test_spotify_error_is_returned_not_raised(self, command, http):
        http.search_status = 429
        assert "busy" in command.run(None, query="x").error_details
