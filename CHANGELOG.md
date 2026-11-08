# Changelog

## 20261108-1500

- Added fast paths, so "play X on Spotify" and "Spotify, play X" run with no model. Anything without the word Spotify
  still goes to the model.
- Added an automatic kind: an exact artist name plays the artist, then song, album and playlist names, else the top song.
- Fixed searches for playlists, which Spotify can return with empty entries.

## 20261108-1200

- Added the `spotify_play` command: "play X on Spotify" searches the catalogue with the user's own Spotify developer app
  and plays the result on the node's go-librespot receiver.
