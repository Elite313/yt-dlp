import os
import re
import tempfile
import random
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp

# Force-load yt-dlp plugins (ensures bgutil POT provider registers itself)
try:
    from yt_dlp import plugins as _yt_plugins
    _yt_plugins.load_all_plugins()
except Exception:
    pass

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False

app = FastAPI(title="yt-dlp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

# WebShare proxy list - rotates randomly
PROXY_LIST = [
    "http://zdqongkx:7ahra7x6reqc@31.59.20.176:6754",
    "http://zdqongkx:7ahra7x6reqc@23.95.150.145:6114",
    "http://zdqongkx:7ahra7x6reqc@198.23.239.134:6540",
    "http://zdqongkx:7ahra7x6reqc@45.38.107.97:6014",
    "http://zdqongkx:7ahra7x6reqc@107.172.163.27:6543",
    "http://zdqongkx:7ahra7x6reqc@198.105.121.200:6462",
    "http://zdqongkx:7ahra7x6reqc@64.137.96.74:6641",
    "http://zdqongkx:7ahra7x6reqc@216.10.27.159:6837",
    "http://zdqongkx:7ahra7x6reqc@142.111.67.146:5611",
    "http://zdqongkx:7ahra7x6reqc@194.39.32.164:6461",
]

def get_random_proxy():
    return random.choice(PROXY_LIST)

# Client strategies for YouTube — android_vr bypasses PO token requirement without cookies
# Non-YouTube platforms fall back to the default (no player_client override)
YOUTUBE_CLIENT_STRATEGIES = [
    ["android_vr"],   # Best: no PO token needed, no cookies needed
    ["tv_embedded"],
    ["web"],
    ["mweb"],
    [],               # Default: let yt-dlp decide
]

def get_ydl_opts(client_index=0, url=""):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
    }

    is_youtube = "youtube.com" in url or "youtu.be" in url

    if is_youtube:
        strategies = YOUTUBE_CLIENT_STRATEGIES
        if client_index < len(strategies) and strategies[client_index]:
            client = strategies[client_index]
            # android_vr skips cookies; others use cookiefile
            if client == ["android_vr"]:
                opts["extractor_args"] = {"youtube": {"player_client": client}}
                # Do NOT pass cookies — android_vr skips them anyway and
                # passing them alongside can cause the client to be ignored
                return opts
            else:
                opts["extractor_args"] = {"youtube": {"player_client": client}}
    else:
        # Non-YouTube: use old CLIENT_STRATEGIES for metadata/info
        CLIENT_STRATEGIES_OTHER = [["tv_embedded"], ["web"], ["mweb"], [], ]
        if client_index < len(CLIENT_STRATEGIES_OTHER) and CLIENT_STRATEGIES_OTHER[client_index]:
            opts["extractor_args"] = {"youtube": {"player_client": CLIENT_STRATEGIES_OTHER[client_index]}}

    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts

def extract_with_retry(url, download=False, outtmpl=None):
    """Try multiple strategies until one works"""
    is_youtube = "youtube.com" in url or "youtu.be" in url
    num_strategies = len(YOUTUBE_CLIENT_STRATEGIES) if is_youtube else 4
    last_error = None
    for i in range(num_strategies):
        try:
            ydl_opts = get_ydl_opts(client_index=i, url=url)
            if not download:
                ydl_opts["no_download"] = True
            if outtmpl:
                ydl_opts["outtmpl"] = outtmpl
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=download)
        except Exception as e:
            last_error = e
            continue
    raise last_error


@app.get("/")
def health():
    return {"status": "running", "proxy": "webshare", "proxy_count": len(PROXY_LIST)}


# ── n8n callback proxy ────────────────────────────────────────────────────────
# n8n (cloud) can't reach localhost:8001 directly.
# This endpoint receives the callback and forwards it internally to the multiplier API.

import httpx as _httpx
from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional

MULTIPLIER_API = os.getenv("MULTIPLIER_API_BASE_URL", "http://localhost:8001")

class _N8nCallback(_BaseModel):
    video_id: _Optional[str] = None
    channel_number: _Optional[int] = None
    uploaded_video_id: str

@app.post("/upload/n8n-callback")
def n8n_callback_proxy(body: _N8nCallback):
    """Proxy n8n callback to the multiplier API running on localhost:8001."""
    try:
        resp = _httpx.post(
            f"{MULTIPLIER_API}/upload/n8n-callback",
            json=body.dict(),
            timeout=10,
        )
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/info")
def get_info(url: str):
    try:
        info = extract_with_retry(url, download=False)
        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/metadata")
def get_metadata(url: str):
    """Get comprehensive metadata for YouTube, Instagram, and other platforms"""
    try:
        info = extract_with_retry(url, download=False)

        # Detect platform
        extractor = info.get("extractor", "").lower()
        platform = "unknown"
        if "youtube" in extractor:
            platform = "youtube"
        elif "instagram" in extractor:
            platform = "instagram"
        elif "tiktok" in extractor:
            platform = "tiktok"
        elif "twitter" in extractor or "x.com" in extractor:
            platform = "twitter"
        elif "facebook" in extractor:
            platform = "facebook"

        # Format duration nicely
        duration_seconds = info.get("duration")
        duration_formatted = None
        if duration_seconds:
            minutes, seconds = divmod(int(duration_seconds), 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_formatted = f"{minutes}:{seconds:02d}"

        # Get best thumbnail
        thumbnails = info.get("thumbnails", [])
        best_thumbnail = info.get("thumbnail")
        if thumbnails:
            # Get highest resolution thumbnail
            sorted_thumbs = sorted(
                [t for t in thumbnails if t.get("width")],
                key=lambda x: x.get("width", 0),
                reverse=True
            )
            if sorted_thumbs:
                best_thumbnail = sorted_thumbs[0].get("url", best_thumbnail)

        return {
            "platform": platform,
            "id": info.get("id"),
            "title": info.get("title"),
            "description": info.get("description"),

            # Engagement metrics
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "dislikes": info.get("dislike_count"),
            "comments": info.get("comment_count"),
            "reposts": info.get("repost_count"),  # For TikTok/Twitter

            # Duration
            "duration_seconds": duration_seconds,
            "duration_formatted": duration_formatted,

            # Uploader info
            "uploader": info.get("uploader"),
            "uploader_id": info.get("uploader_id"),
            "uploader_url": info.get("uploader_url"),
            "channel": info.get("channel"),
            "channel_id": info.get("channel_id"),
            "channel_url": info.get("channel_url"),
            "channel_follower_count": info.get("channel_follower_count"),

            # Dates
            "upload_date": info.get("upload_date"),  # YYYYMMDD format
            "timestamp": info.get("timestamp"),  # Unix timestamp

            # Media
            "thumbnail": best_thumbnail,
            "thumbnails": [t.get("url") for t in thumbnails if t.get("url")][:5],  # Top 5

            # Categories & Tags
            "tags": info.get("tags", []),
            "categories": info.get("categories", []),

            # Platform-specific
            "is_live": info.get("is_live"),
            "was_live": info.get("was_live"),
            "age_limit": info.get("age_limit"),
            "webpage_url": info.get("webpage_url"),

            # Video quality info
            "resolution": info.get("resolution"),
            "fps": info.get("fps"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/stats")
def get_stats(url: str):
    """Get just the engagement stats (views, likes, comments)"""
    try:
        info = extract_with_retry(url, download=False)
        return {
            "title": info.get("title"),
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "comments": info.get("comment_count"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _load_instagram_cookies(L: "instaloader.Instaloader") -> bool:
    """Load all Instagram cookies from cookies.txt into the instaloader session."""
    if not os.path.exists(COOKIES_FILE):
        return False
    found = False
    with open(COOKIES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, path, secure, _, name, value = parts[:7]
            if "instagram" not in domain:
                continue
            L.context._session.cookies.set(name, value, domain=domain)
            found = True
    return found


def _list_instagram_reels(username: str, limit: int, after: Optional[str], before: Optional[str]) -> dict:
    """Fetch reels from an Instagram profile using instaloader's get_reels()."""
    if not INSTALOADER_AVAILABLE:
        raise HTTPException(status_code=501, detail="instaloader is not installed.")

    L = instaloader.Instaloader(quiet=True, download_pictures=False, download_videos=False)
    if not _load_instagram_cookies(L):
        raise HTTPException(status_code=401, detail="No Instagram cookies found in cookies.txt")

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        raise HTTPException(status_code=404, detail=f"Instagram profile '{username}' not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not load Instagram profile: {e}")

    dt_after  = datetime.strptime(after,  "%Y%m%d").replace(tzinfo=timezone.utc) if after  else None
    dt_before = datetime.strptime(before, "%Y%m%d").replace(tzinfo=timezone.utc) if before else None

    videos = []
    try:
        for reel in profile.get_reels():
            post_dt = reel.date_utc.replace(tzinfo=timezone.utc)

            if dt_after  and post_dt < dt_after:
                continue
            if dt_before and post_dt > dt_before:
                continue

            shortcode = reel.shortcode
            videos.append({
                "id":               shortcode,
                "title":            reel.title or (reel.caption or "")[:80] or shortcode,
                "url":              f"https://www.instagram.com/reel/{shortcode}/",
                "thumbnail":        reel.url,
                "duration_seconds": reel.video_duration,
                "upload_date":      post_dt.strftime("%Y%m%d"),
                "views":            reel.video_view_count,
                "likes":            reel.likes,
                "comments":         reel.comments,
            })

            if len(videos) >= limit:
                break
    except Exception:
        pass  # Return whatever was collected before the error

    return {
        "platform":      "instagram",
        "channel":       profile.full_name or username,
        "channel_url":   f"https://www.instagram.com/{username}/",
        "followers":     profile.followers,
        "filters":       {"limit": limit, "after": after, "before": before},
        "total_fetched": len(videos),
        "videos":        videos,
    }


@app.get("/channel/list")
def list_channel_videos(
    url: str,
    limit: int = Query(default=50, ge=1, le=500, description="Max number of videos to fetch"),
    after: Optional[str] = Query(default=None, description="Fetch videos published after this date (YYYYMMDD)"),
    before: Optional[str] = Query(default=None, description="Fetch videos published before this date (YYYYMMDD)"),
    type: str = Query(default="all", description="Filter by type: 'shorts', 'reels', 'all'"),
):
    """
    List all shorts/reels from a YouTube channel or Instagram profile.

    YouTube examples:
      - https://www.youtube.com/@channelname/shorts   ← YouTube Shorts only
      - https://www.youtube.com/@channelname           ← All videos

    Instagram examples:
      - https://www.instagram.com/username/reels/     ← Instagram Reels only
      - https://www.instagram.com/username/           ← All posts
    """
    # Validate date formats
    for label, val in [("after", after), ("before", before)]:
        if val:
            try:
                datetime.strptime(val, "%Y%m%d")
            except ValueError:
                raise HTTPException(status_code=422, detail=f"'{label}' must be in YYYYMMDD format, e.g. 20240101")

    # Route Instagram URLs to instaloader (yt-dlp Instagram profile extraction is broken)
    if "instagram.com" in url:
        match = re.search(r"instagram\.com/([^/?#]+)", url)
        username = match.group(1) if match else None
        if not username:
            raise HTTPException(status_code=422, detail="Could not parse Instagram username from URL")
        return _list_instagram_reels(username, limit, after, before)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",   # Fast — no individual video requests
        "playlistend": limit,
        "socket_timeout": 60,
        "ignoreerrors": True,
    }
    if after:
        ydl_opts["dateafter"] = after
    if before:
        ydl_opts["datebefore"] = before
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if info is None:
        platform_hint = ""
        if "instagram.com" in url:
            platform_hint = (
                " Instagram requires login cookies to list channel reels. "
                "Export your Instagram cookies to cookies.txt and place it next to main.py, then retry."
            )
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract data from the provided URL. It may be unsupported, private, or require authentication.{platform_hint}"
        )

    # Support both flat playlists and nested (e.g. channel tabs)
    entries = info.get("entries", [])
    # Some channel pages return tab entries — unwrap one level
    if entries and isinstance(entries[0], dict) and "entries" in entries[0]:
        entries = entries[0].get("entries", [])

    # Detect platform
    extractor = info.get("extractor", "").lower()
    platform = "youtube" if "youtube" in extractor else ("instagram" if "instagram" in extractor else "unknown")

    # If the URL already points to a dedicated shorts/reels tab, duration won't be
    # available in flat mode — trust the platform's own categorisation instead.
    url_lower = url.lower()
    url_is_shorts_tab = "/shorts" in url_lower
    url_is_reels_tab  = "/reels"  in url_lower

    videos = []
    for entry in entries:
        if not entry:
            continue

        duration = entry.get("duration")

        # Type filter — only apply duration check when duration is actually known
        # AND the URL is not already scoped to a shorts/reels tab.
        if type == "shorts" and not url_is_shorts_tab:
            if duration is not None and duration > 60:
                continue
        if type == "reels" and not url_is_reels_tab:
            if duration is not None and duration > 90:
                continue

        # Build a proper watch/reel URL when the flat entry only has an ID
        video_id  = entry.get("id")
        video_url = entry.get("url") or entry.get("webpage_url")
        if not video_url and video_id:
            if platform == "youtube":
                video_url = (
                    f"https://www.youtube.com/shorts/{video_id}"
                    if url_is_shorts_tab
                    else f"https://www.youtube.com/watch?v={video_id}"
                )
            elif platform == "instagram":
                video_url = f"https://www.instagram.com/reel/{video_id}/"

        videos.append({
            "id": video_id,
            "title": entry.get("title"),
            "url": video_url,
            "thumbnail": entry.get("thumbnail"),
            "duration_seconds": duration,
            "upload_date": entry.get("upload_date"),
            "views": entry.get("view_count"),
            "likes": entry.get("like_count"),
        })

    return {
        "platform": platform,
        "channel": info.get("uploader") or info.get("channel") or info.get("title"),
        "channel_url": info.get("uploader_url") or info.get("channel_url") or url,
        "filters": {
            "limit": limit,
            "after": after,
            "before": before,
            "type": type,
        },
        "total_fetched": len(videos),
        "videos": videos,
    }


@app.get("/channel/video")
def get_channel_video(url: str):
    """
    Get full metadata for a single video/reel/short.
    Same as /metadata — use this when you already have the video URL from /channel/list.
    """
    return get_metadata(url)


@app.get("/direct-url")
def get_direct_url(url: str):
    try:
        info = extract_with_retry(url, download=False)
        video_url = None
        for f in reversed(info.get("formats", [])):
            if f.get("url"):
                video_url = f.get("url")
                break
        return {"title": info.get("title"), "direct_url": video_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/video")
def download_video(url: str):
    try:
        temp_dir = tempfile.mkdtemp()
        outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")

        # Format priority: highest quality MP4 with video+audio merged
        # bestvideo+bestaudio merges best separate streams (1080p+) via ffmpeg
        # Falls back to best combined stream if merge isn't possible
        FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

        is_youtube = "youtube.com" in url or "youtu.be" in url
        num_strategies = len(YOUTUBE_CLIENT_STRATEGIES) if is_youtube else 4
        last_error = None
        info = None
        for client_index in range(num_strategies):
            try:
                ydl_opts = get_ydl_opts(client_index=client_index, url=url)
                ydl_opts["format"] = FORMAT
                ydl_opts["merge_output_format"] = "mp4"
                ydl_opts["outtmpl"] = outtmpl
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                break
            except Exception as e:
                last_error = e
                continue
        if info is None:
            raise last_error
        title = info.get("title", "video")
        title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        video_id = info.get("id", "video")
        ext = info.get("ext", "mp4")

        # Find the downloaded file
        downloaded_file = os.path.join(temp_dir, f"{video_id}.{ext}")

        if not os.path.exists(downloaded_file):
            # Search for any file in temp_dir
            for f in os.listdir(temp_dir):
                downloaded_file = os.path.join(temp_dir, f)
                break

        if not os.path.exists(downloaded_file):
            raise HTTPException(status_code=500, detail="Download failed - no file found")

        return FileResponse(
            downloaded_file,
            media_type="video/mp4",
            filename=f"{title}.mp4"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/formats")
def get_formats(url: str):
    try:
        info = extract_with_retry(url, download=False)
        formats = []
        for f in info.get("formats", []):
            formats.append({
                "id": f.get("format_id"),
                "ext": f.get("ext"),
                "res": f.get("resolution"),
                "h": f.get("height"),
            })
        return {"formats": formats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
