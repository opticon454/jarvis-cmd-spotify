# jarvis-cmd-spotify

A [Jarvis](https://github.com/alexberardi/jarvis-server) Pantry package: say "Hey Jarvis, play Hysteria by Muse on
Spotify" and the node plays it through its own Spotify Connect speaker.

## How it works

1. Jarvis hears "play ... on Spotify" and calls the `spotify_play` command with the song, album, artist or playlist.
2. The command finds it with the Spotify Web API, using **your own developer app** (client credentials, catalogue only).
3. It tells the node's [go-librespot](https://github.com/devgianlu/go-librespot) receiver to play it, on the account
   the node is already paired with.

## Requirements

- Spotify Premium, and the node running go-librespot (see `docs/agent/spotify-connect.md` in jarvis-server).
- A free Spotify developer app: <https://developer.spotify.com/dashboard>. No user login is used.

## Settings

Entered in the Jarvis app; nothing is stored in this repository.

| Setting                 | Required | Meaning                                                    |
| ----------------------- | -------- | ---------------------------------------------------------- |
| `SPOTIFY_CLIENT_ID`     | Yes      | Your Spotify developer app's client ID.                    |
| `SPOTIFY_CLIENT_SECRET` | Yes      | Its client secret (stored encrypted by Jarvis).            |
| `SPOTIFY_LIBRESPOT_URL` | No       | go-librespot's local API. Default `http://127.0.0.1:3678`. |
| `SPOTIFY_MARKET`        | No       | Two-letter country to search in. Default `AU`.             |

## Tests

```bash
PYTHONPATH=/path/to/jarvis-command-sdk python3 -m pytest
```

The tests use a fake Spotify and receiver; no network and no account are needed.

## Licence

Apache-2.0. This package talks to go-librespot (GPL-3.0) over HTTP and does not include it. Not affiliated with Spotify.
