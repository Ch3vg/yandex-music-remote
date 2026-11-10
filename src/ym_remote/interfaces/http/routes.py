from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from ym_remote.interfaces.http.images import render_icon, render_qr
from ym_remote.interfaces.http.pages import MANIFEST, OPEN_HTML, SERVICE_WORKER
from ym_remote.interfaces.ws.handler import parse_message
from ym_remote.models.errors import RemoteError
from ym_remote.schemas.catalog import (
    AlbumDetailWire,
    ArtistDetailWire,
    ArtistFamiliarWire,
    ArtistRefWire,
    ArtistTracksPageWire,
    CatalogTrackWire,
    HomeWire,
    LikesWire,
    PlaylistCardWire,
    PlaylistDetailWire,
    SearchResponseWire,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _dist(request: Request) -> Path | None:
    root = Path(request.app.state.settings.root) / "web" / "dist"
    if (root / "index.html").is_file():
        return root
    return None


@router.get("/")
async def index(request: Request):
    dist = _dist(request)
    if dist is None:
        raise HTTPException(404, "Пульт не собран")
    return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})


@router.get("/open")
async def open_page():
    return HTMLResponse(OPEN_HTML)


@router.get("/manifest.webmanifest")
async def manifest():
    return JSONResponse(MANIFEST, media_type="application/manifest+json")


@router.get("/sw.js")
async def service_worker():
    return Response(
        SERVICE_WORKER,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@router.get("/apple-touch-icon.png")
async def apple_icon():
    return Response(render_icon(180), media_type="image/png")


@router.get("/icon-192.png")
async def icon_192():
    return Response(render_icon(192), media_type="image/png")


@router.get("/icon-512.png")
async def icon_512():
    return Response(render_icon(512), media_type="image/png")


@router.get("/network-info")
async def network_info(request: Request):
    return request.app.state.network.info()


@router.get("/qr")
async def qr(request: Request, ip: str | None = None):
    network = request.app.state.network
    host = network.qr_host(ip)
    png = render_qr(f"http://{host}:{network.port}/")
    return Response(png, media_type="image/png")


@router.get("/cdp-status")
async def cdp_status(request: Request):
    monitor = request.app.state.services.monitor
    try:
        available = await monitor.bar_available()
    except Exception:
        available = False
    return {"available": bool(available)}


@router.get("/search")
async def search(request: Request, q: str = ""):
    try:
        tracks = await request.app.state.services.search.search(q)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return [CatalogTrackWire.from_track(track).model_dump() for track in tracks]


@router.get("/api/search")
async def api_search(request: Request, q: str = ""):
    try:
        view = await request.app.state.services.search.search_all(q)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return SearchResponseWire.from_view(view).model_dump()


@router.get("/api/library/home")
async def library_home(request: Request):
    try:
        home = await request.app.state.services.library.home()
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    payload = HomeWire(
        likes=LikesWire(
            title=home.likes.title or "Мне нравится",
            tracks=[CatalogTrackWire.from_track(track) for track in home.tracks],
            kind=home.likes.kind,
            uid=home.likes.uid,
            playlist_uuid=home.likes.uuid,
            track_count=home.likes.track_count,
            cover_url=home.likes.cover.list_url() if home.likes.cover else None,
        ),
        playlists=[PlaylistCardWire.from_playlist(playlist) for playlist in home.playlists],
    )
    return payload.model_dump()


@router.get("/api/library/playlist/{kind}")
async def library_playlist(kind: int, request: Request):
    try:
        playlist = await request.app.state.services.library.playlist(kind)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return PlaylistDetailWire.from_playlist(playlist).model_dump()


@router.get("/api/library/artist/{artist_id}")
async def library_artist(artist_id: int, request: Request):
    try:
        detail = await request.app.state.services.library.artist(artist_id)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return ArtistDetailWire.from_detail(detail).model_dump()


@router.get("/api/library/artist/{artist_id}/tracks")
async def library_artist_tracks(
    artist_id: int,
    request: Request,
    page: int = 0,
    page_size: int = 50,
):
    try:
        page_data = await request.app.state.services.library.artist_tracks(
            artist_id, page=page, page_size=page_size
        )
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return ArtistTracksPageWire.from_page(page_data).model_dump()


@router.get("/api/library/artist/{artist_id}/familiar")
async def library_artist_familiar(artist_id: int, request: Request):
    try:
        familiar = await request.app.state.services.library.artist_familiar(artist_id)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    if isinstance(familiar, tuple):
        from ym_remote.models.music import FamiliarTracks

        familiar = FamiliarTracks(collection=familiar, wave=())
    return ArtistFamiliarWire.from_familiar(familiar).model_dump()


@router.get("/api/library/album/{album_id}")
async def library_album(album_id: int, request: Request):
    try:
        album = await request.app.state.services.library.album(album_id)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return AlbumDetailWire.from_album(album).model_dump()


@router.get("/api/library/artists")
async def library_artists(request: Request, ids: str = ""):
    parsed_ids: list[int] = []
    seen: set[int] = set()
    for part in (ids or "").split(","):
        token = part.strip()
        if not token.isdigit():
            continue
        aid = int(token)
        if aid > 0 and aid not in seen:
            seen.add(aid)
            parsed_ids.append(aid)
    try:
        artists = await request.app.state.services.library.artists_by_ids(parsed_ids)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"artists": [ArtistRefWire.from_artist(item).model_dump() for item in artists]}


@router.get("/api/library/track/{track_id}/artists")
async def library_track_artists(track_id: int, request: Request):
    try:
        artists = await request.app.state.services.library.track_artists(track_id)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"artists": [ArtistRefWire.from_artist(artist).model_dump() for artist in artists]}


@router.get("/api/library/resolve-artist")
async def library_resolve_artist(
    request: Request,
    title: str = "",
    artist: str = "",
):
    try:
        artists = await request.app.state.services.library.resolve_artists(title, artist)
    except RemoteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"artists": [ArtistRefWire.from_artist(item).model_dump() for item in artists]}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    hub = websocket.app.state.hub
    handler = websocket.app.state.handler
    await hub.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            message = parse_message(raw)
            if message is None:
                continue
            await handler.handle(websocket, message)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("websocket handler error")
    finally:
        hub.disconnect(websocket)


@router.get("/{full_path:path}")
async def dist_file(full_path: str, request: Request):
    dist = _dist(request)
    if dist is None or not full_path or ".." in full_path.split("/"):
        raise HTTPException(404, "Не найдено")
    candidate = (dist / full_path).resolve()
    try:
        candidate.relative_to(dist.resolve())
    except ValueError as exc:
        raise HTTPException(404, "Не найдено") from exc
    if candidate.is_file():
        return FileResponse(candidate)
    raise HTTPException(404, "Не найдено")
