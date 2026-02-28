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


def get_ydl_opts():
    proxy = get_random_proxy()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
        "proxy": proxy,
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts


@app.get("/")
def health():
    return {"status": "running", "proxy": "webshare", "proxy_count": len(PROXY_LIST)}


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

        ydl_opts = get_ydl_opts()
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
