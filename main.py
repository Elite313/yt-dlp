import os
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp

app = FastAPI(title="yt-dlp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
PROXY_URL = os.getenv("PROXY_URL", "http://zdqongkx:7ahra7x6reqc@198.23.239.134:6540")


def get_ydl_opts(for_download=False):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
        # Use iOS client - most reliable for bypassing restrictions
        "extractor_args": {"youtube": {"player_client": ["ios", "android"]}},
    }
    # Only use proxy if needed
    if PROXY_URL:
        opts["proxy"] = PROXY_URL
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    # For downloads, use format that doesn't require merging
    if for_download:
        opts["format"] = "best[ext=mp4]/best"
    return opts


@app.get("/")
def health():
    return {"status": "running", "proxy": "webshare"}


@app.get("/info")
def get_info(url: str):
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts["no_download"] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/direct-url")
def get_direct_url(url: str):
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts["no_download"] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
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

        ydl_opts = get_ydl_opts(for_download=True)
        ydl_opts["outtmpl"] = os.path.join(temp_dir, "%(id)s.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
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
        ydl_opts = get_ydl_opts()
        ydl_opts["no_download"] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
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
