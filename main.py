import os
import tempfile
import random
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

# Different client strategies to try
CLIENT_STRATEGIES = [
    ["tv_embedded"],
    ["web"],
    ["mweb"],
    ["android"],
    [],  # No client specification - let yt-dlp decide
]

def get_ydl_opts(client_index=0):
    proxy = get_random_proxy()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
        "proxy": proxy,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    }
    # Apply client strategy if specified
    if client_index < len(CLIENT_STRATEGIES) and CLIENT_STRATEGIES[client_index]:
        opts["extractor_args"] = {"youtube": {"player_client": CLIENT_STRATEGIES[client_index]}}
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts

def extract_with_retry(url, download=False, outtmpl=None):
    """Try multiple strategies until one works"""
    last_error = None
    for i in range(len(CLIENT_STRATEGIES)):
        try:
            ydl_opts = get_ydl_opts(client_index=i)
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

        info = extract_with_retry(url, download=True, outtmpl=outtmpl)
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
