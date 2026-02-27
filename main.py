import os
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp

app = FastAPI(title="yt-dlp API - High Quality")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cookies file path
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")


@app.get("/")
def health():
    cookies_exist = os.path.exists(COOKIES_FILE)
    return {
        "status": "running",
        "service": "yt-dlp-api",
        "quality": "highest available",
        "cookies": "loaded" if cookies_exist else "not found",
        "endpoints": ["/info", "/video", "/direct-url", "/formats"]
    }


@app.get("/info")
def get_info(url: str):
    """Extract video metadata without downloading"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "title": info.get("title"),
                "description": info.get("description"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "uploader": info.get("uploader"),
                "upload_date": info.get("upload_date"),
                "webpage_url": info.get("webpage_url"),
                "platform": info.get("extractor"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/direct-url")
def get_direct_url(url: str):
    """Get direct video URL"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
            "format": "best",
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get("url")

            if not video_url and info.get("formats"):
                for f in reversed(info.get("formats", [])):
                    if f.get("url"):
                        video_url = f.get("url")
                        break

            return {
                "title": info.get("title"),
                "direct_url": video_url,
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/video")
def download_video(url: str, quality: str = "best"):
    """Download and return video file"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "video.mp4")

        # Simple format selection that works
        if quality == "best" or quality == "highest":
            format_sel = "bv*+ba/b"  # best video + best audio, or best combined
        elif quality == "1080p":
            format_sel = "bv*[height<=1080]+ba/b[height<=1080]/b"
        elif quality == "720p":
            format_sel = "bv*[height<=720]+ba/b[height<=720]/b"
        elif quality == "480p":
            format_sel = "bv*[height<=480]+ba/b[height<=480]/b"
        else:
            format_sel = "b"  # best available

        ydl_opts = {
            "format": format_sel,
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]

        # Find downloaded file
        if not os.path.exists(output_path):
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.mkv', '.webm')):
                    output_path = os.path.join(temp_dir, file)
                    break

        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename=f"{title}.mp4"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/formats")
def get_formats(url: str):
    """Get all available formats"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []

            for f in info.get("formats", []):
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "height": f.get("height"),
                    "filesize": f.get("filesize"),
                })

            return {
                "title": info.get("title"),
                "formats": formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
