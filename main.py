import os
import tempfile
import random
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp

app = FastAPI(title="yt-dlp API with Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

# Proxy configuration
# Option 1: Set your paid proxy service URL here
PAID_PROXY = os.getenv("PROXY_URL", None)  # e.g., "http://user:pass@proxy.service.com:port"

# Option 2: Free proxy list (less reliable)
FREE_PROXY_APIS = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
]


def get_free_proxies():
    """Fetch free proxies from public APIs"""
    proxies = []
    try:
        for api in FREE_PROXY_APIS:
            resp = requests.get(api, timeout=10)
            if resp.status_code == 200:
                proxy_list = resp.text.strip().split("\n")
                proxies.extend([f"http://{p.strip()}" for p in proxy_list if p.strip()])
    except:
        pass
    return proxies[:20]  # Limit to 20 proxies


def get_random_proxy():
    """Get a random working proxy"""
    if PAID_PROXY:
        return PAID_PROXY

    proxies = get_free_proxies()
    if proxies:
        return random.choice(proxies)
    return None


def get_ydl_opts(use_proxy=True):
    """Get yt-dlp options with proxy support"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "socket_timeout": 30,
    }

    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE

    # Add proxy if available
    if use_proxy:
        proxy = get_random_proxy()
        if proxy:
            opts["proxy"] = proxy

    return opts


@app.get("/")
def health():
    proxy_status = "paid proxy configured" if PAID_PROXY else "using free proxies"
    return {
        "status": "running",
        "proxy": proxy_status,
        "endpoints": ["/info", "/video", "/direct-url", "/formats"]
    }


@app.get("/info")
def get_info(url: str):
    """Extract video metadata"""
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts["no_download"] = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title"),
                "description": info.get("description"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "platform": info.get("extractor"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/direct-url")
def get_direct_url(url: str):
    """Get direct video URL"""
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts["no_download"] = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            video_url = None
            if info.get("formats"):
                for f in reversed(info.get("formats", [])):
                    if f.get("url"):
                        video_url = f.get("url")
                        break

            if not video_url:
                video_url = info.get("url")

            return {
                "title": info.get("title"),
                "direct_url": video_url,
                "thumbnail": info.get("thumbnail"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/video")
def download_video(url: str, retries: int = 3):
    """Download video with proxy rotation and retries"""
    last_error = None

    for attempt in range(retries):
        try:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, "video.%(ext)s")

            ydl_opts = get_ydl_opts(use_proxy=True)
            ydl_opts["outtmpl"] = output_path
            ydl_opts["format"] = "18/best"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "video")
                title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]

            # Find downloaded file
            final_path = None
            for file in os.listdir(temp_dir):
                if file.startswith("video."):
                    final_path = os.path.join(temp_dir, file)
                    break

            if final_path and os.path.exists(final_path):
                return FileResponse(
                    final_path,
                    media_type="video/mp4",
                    filename=f"{title}.mp4"
                )

        except Exception as e:
            last_error = str(e)
            continue  # Try next proxy

    raise HTTPException(status_code=400, detail=f"Failed after {retries} attempts: {last_error}")


@app.get("/formats")
def get_formats(url: str):
    """Get available formats"""
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts["no_download"] = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get("formats", []):
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "height": f.get("height"),
                })
            return {"title": info.get("title"), "formats": formats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
