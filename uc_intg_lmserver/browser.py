"""
Media browser for LMS integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ucapi import StatusCodes
from ucapi.api_definitions import (
    BrowseMediaItem,
    BrowseOptions,
    BrowseResults,
    MediaClass,
    Pagination,
    SearchOptions,
    SearchResults,
)

if TYPE_CHECKING:
    from uc_intg_lmserver.device import LMServerDevice

_LOG = logging.getLogger(__name__)

PAGE_SIZE = 50


async def browse(
    device: LMServerDevice, player_id: str, options: BrowseOptions
) -> BrowseResults | StatusCodes:
    media_type = options.media_type or "root"
    media_id = options.media_id or ""
    page = _get_page(options)

    if media_type == "root" or (options.media_id is None and options.media_type is None):
        return _browse_root()

    if media_type == "artists":
        return await _browse_artists(device, page)

    if media_type == "artist":
        return await _browse_artist_albums(device, media_id, page)

    if media_type == "albums":
        return await _browse_albums(device, page)

    if media_type == "album":
        return await _browse_album_tracks(device, media_id, page)

    if media_type == "genres":
        return await _browse_genres(device, page)

    if media_type == "genre":
        return await _browse_genre_albums(device, media_id, page)

    if media_type == "playlists":
        return await _browse_playlists(device, page)

    if media_type == "playlist":
        return await _browse_playlist_tracks(device, media_id, page)

    if media_type == "favorites":
        return _browse_favorites(device, page)

    return StatusCodes.NOT_FOUND


async def search(
    device: LMServerDevice, player_id: str, options: SearchOptions
) -> SearchResults | StatusCodes:
    query = options.query if options.query else ""
    if not query:
        return StatusCodes.BAD_REQUEST

    page = 1
    if options.paging and options.paging.page:
        page = int(options.paging.page)

    start = (page - 1) * PAGE_SIZE
    client = device.client

    try:
        result = await client.search(query, start, PAGE_SIZE)
    except Exception as err:
        _LOG.error("Search failed: %s", err)
        return StatusCodes.SERVER_ERROR

    items: list[BrowseMediaItem] = []

    for artist in result.get("artists_loop", []):
        items.append(BrowseMediaItem(
            title=artist.get("artist", ""),
            media_class=MediaClass.ARTIST,
            media_type="artist",
            media_id=str(artist.get("artist_id", "")),
            can_browse=True,
            can_play=True,
        ))

    for album in result.get("albums_loop", []):
        art_id = str(album.get("artwork_track_id", ""))
        items.append(BrowseMediaItem(
            title=album.get("album", ""),
            subtitle=album.get("artist", ""),
            media_class=MediaClass.ALBUM,
            media_type="album",
            media_id=str(album.get("album_id", "")),
            thumbnail=client.get_album_artwork_url(art_id) if art_id else "",
            can_browse=True,
            can_play=True,
        ))

    for track in result.get("tracks_loop", []):
        items.append(BrowseMediaItem(
            title=track.get("track", ""),
            subtitle=track.get("artist", ""),
            media_class=MediaClass.TRACK,
            media_type="track",
            media_id=str(track.get("track_id", "")),
            can_browse=False,
            can_play=True,
        ))

    total = (
        result.get("artists_count", 0)
        + result.get("albums_count", 0)
        + result.get("tracks_count", 0)
    )

    return SearchResults(
        media=items,
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


def _get_page(options: BrowseOptions) -> int:
    if options.paging and options.paging.page:
        return int(options.paging.page)
    return 1


def _browse_root() -> BrowseResults:
    items = [
        BrowseMediaItem(
            title="Artists",
            media_class=MediaClass.DIRECTORY,
            media_type="artists",
            media_id="artists",
            can_browse=True,
            can_play=False,
        ),
        BrowseMediaItem(
            title="Albums",
            media_class=MediaClass.DIRECTORY,
            media_type="albums",
            media_id="albums",
            can_browse=True,
            can_play=False,
        ),
        BrowseMediaItem(
            title="Genres",
            media_class=MediaClass.DIRECTORY,
            media_type="genres",
            media_id="genres",
            can_browse=True,
            can_play=False,
        ),
        BrowseMediaItem(
            title="Playlists",
            media_class=MediaClass.DIRECTORY,
            media_type="playlists",
            media_id="playlists",
            can_browse=True,
            can_play=False,
        ),
        BrowseMediaItem(
            title="Favorites",
            media_class=MediaClass.DIRECTORY,
            media_type="favorites",
            media_id="favorites",
            can_browse=True,
            can_play=False,
        ),
    ]

    return BrowseResults(
        media=BrowseMediaItem(
            title="Lyrion Music Server",
            media_class=MediaClass.DIRECTORY,
            media_type="root",
            media_id="root",
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=1, limit=len(items), count=len(items)),
    )


async def _browse_artists(device: LMServerDevice, page: int) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_artists(start, PAGE_SIZE)
    total = result.get("count", 0)

    items = []
    for artist in result.get("artists_loop", []):
        items.append(BrowseMediaItem(
            title=artist.get("artist", "Unknown Artist"),
            media_class=MediaClass.ARTIST,
            media_type="artist",
            media_id=str(artist.get("id", "")),
            can_browse=True,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Artists",
            media_class=MediaClass.DIRECTORY,
            media_type="artists",
            media_id="artists",
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_artist_albums(
    device: LMServerDevice, artist_id: str, page: int
) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_albums(start, PAGE_SIZE, artist_id=artist_id)
    total = result.get("count", 0)
    client = device.client

    items = []
    for album in result.get("albums_loop", []):
        art_id = str(album.get("artwork_track_id", ""))
        items.append(BrowseMediaItem(
            title=album.get("album", "Unknown Album"),
            subtitle=album.get("artist", ""),
            media_class=MediaClass.ALBUM,
            media_type="album",
            media_id=str(album.get("id", "")),
            thumbnail=client.get_album_artwork_url(art_id) if art_id else "",
            can_browse=True,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Albums",
            media_class=MediaClass.DIRECTORY,
            media_type="artist",
            media_id=artist_id,
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_albums(device: LMServerDevice, page: int) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_albums(start, PAGE_SIZE)
    total = result.get("count", 0)
    client = device.client

    items = []
    for album in result.get("albums_loop", []):
        art_id = str(album.get("artwork_track_id", ""))
        items.append(BrowseMediaItem(
            title=album.get("album", "Unknown Album"),
            subtitle=album.get("artist", ""),
            media_class=MediaClass.ALBUM,
            media_type="album",
            media_id=str(album.get("id", "")),
            thumbnail=client.get_album_artwork_url(art_id) if art_id else "",
            can_browse=True,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Albums",
            media_class=MediaClass.DIRECTORY,
            media_type="albums",
            media_id="albums",
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_album_tracks(
    device: LMServerDevice, album_id: str, page: int
) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_tracks(start, PAGE_SIZE, album_id=album_id)
    total = result.get("count", 0)
    client = device.client

    items = []
    for track in result.get("titles_loop", []):
        coverid = str(track.get("coverid", ""))
        items.append(BrowseMediaItem(
            title=track.get("title", "Unknown Track"),
            subtitle=track.get("artist", ""),
            media_class=MediaClass.TRACK,
            media_type="track",
            media_id=str(track.get("id", "")),
            thumbnail=client.get_album_artwork_url(coverid) if coverid else "",
            can_browse=False,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Tracks",
            media_class=MediaClass.DIRECTORY,
            media_type="album",
            media_id=album_id,
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_genres(device: LMServerDevice, page: int) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_genres(start, PAGE_SIZE)
    total = result.get("count", 0)

    items = []
    for genre in result.get("genres_loop", []):
        items.append(BrowseMediaItem(
            title=genre.get("genre", "Unknown Genre"),
            media_class=MediaClass.DIRECTORY,
            media_type="genre",
            media_id=str(genre.get("id", "")),
            can_browse=True,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Genres",
            media_class=MediaClass.DIRECTORY,
            media_type="genres",
            media_id="genres",
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_genre_albums(
    device: LMServerDevice, genre_id: str, page: int
) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_albums(start, PAGE_SIZE, genre_id=genre_id)
    total = result.get("count", 0)
    client = device.client

    items = []
    for album in result.get("albums_loop", []):
        art_id = str(album.get("artwork_track_id", ""))
        items.append(BrowseMediaItem(
            title=album.get("album", "Unknown Album"),
            subtitle=album.get("artist", ""),
            media_class=MediaClass.ALBUM,
            media_type="album",
            media_id=str(album.get("id", "")),
            thumbnail=client.get_album_artwork_url(art_id) if art_id else "",
            can_browse=True,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Albums",
            media_class=MediaClass.DIRECTORY,
            media_type="genre",
            media_id=genre_id,
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_playlists(device: LMServerDevice, page: int) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_playlists(start, PAGE_SIZE)
    total = result.get("count", 0)

    items = []
    for pl in result.get("playlists_loop", []):
        items.append(BrowseMediaItem(
            title=pl.get("playlist", "Unknown Playlist"),
            media_class=MediaClass.PLAYLIST,
            media_type="playlist",
            media_id=str(pl.get("id", "")),
            can_browse=True,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Playlists",
            media_class=MediaClass.DIRECTORY,
            media_type="playlists",
            media_id="playlists",
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


async def _browse_playlist_tracks(
    device: LMServerDevice, playlist_id: str, page: int
) -> BrowseResults:
    start = (page - 1) * PAGE_SIZE
    result = await device.client.get_playlist_tracks(playlist_id, start, PAGE_SIZE)
    total = result.get("count", 0)
    client = device.client

    items = []
    for track in result.get("playlisttracks_loop", []):
        coverid = str(track.get("coverid", ""))
        items.append(BrowseMediaItem(
            title=track.get("title", "Unknown Track"),
            subtitle=track.get("artist", ""),
            media_class=MediaClass.TRACK,
            media_type="track",
            media_id=str(track.get("id", "")),
            thumbnail=client.get_album_artwork_url(coverid) if coverid else "",
            can_browse=False,
            can_play=True,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Tracks",
            media_class=MediaClass.DIRECTORY,
            media_type="playlist",
            media_id=playlist_id,
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


def _browse_favorites(device: LMServerDevice, page: int) -> BrowseResults:
    all_favs = device.favorites or []
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_favs = all_favs[start:end]

    items = []
    for i, fav in enumerate(page_favs, start + 1):
        name = fav.get("name", f"Favorite {i}")
        fav_id = str(fav.get("id", ""))

        items.append(BrowseMediaItem(
            title=name,
            media_class=MediaClass.TRACK,
            media_type="favorite",
            media_id=fav_id,
            can_play=True,
            can_browse=False,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Favorites",
            media_class=MediaClass.DIRECTORY,
            media_type="favorites",
            media_id="favorites",
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=len(all_favs)),
    )
