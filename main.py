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
        "quality": "highest (1080p+)",
        "cookies": "loaded" if cookies_exist else "not found"
    }


@app.get("/info")
def get_info(url: str):
    """Extract video metadata without downloading"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        }

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
def get_direct_url(url: str, quality: str = "highest"):
    """Get direct video URL"""
    try:
        if quality == "highest":
            format_sel = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "1080p":
            format_sel = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
        elif quality == "720p":
            format_sel = "best[height<=720][ext=mp4]/best[height<=720]/best"
        else:
            format_sel = "best[ext=mp4]/best"

        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
            "format": format_sel,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get("url")

            if not video_url and info.get("formats"):
                for f in reversed(info.get("formats", [])):
                    if f.get("url") and f.get("ext") == "mp4":
                        video_url = f.get("url")
                        break
                if not video_url:
                    video_url = info["formats"][-1].get("url")

            return {
                "title": info.get("title"),
                "direct_url": video_url,
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "resolution": info.get("resolution"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/video")
def download_video(url: str, quality: str = "highest"):
    """Download and return video file in highest quality (1080p+)"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "video.mp4")

        # Format selection for highest quality with audio
        if quality == "highest":
            # Try to get 1080p or higher with best audio
            format_sel = "bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        elif quality == "1080p":
            format_sel = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
        elif quality == "720p":
            format_sel = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"
        elif quality == "480p":
            format_sel = "best[height<=480][ext=mp4]/best[height<=480]"
        else:
            format_sel = "best[ext=mp4]/best"

        ydl_opts = {
            "format": format_sel,
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            # Merge video + audio into mp4
            "merge_output_format": "mp4",
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            # Clean title for filename
            title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]

        # Check if file exists
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
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []

            for f in info.get("formats", []):
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "height": f.get("height"),
                    "width": f.get("width"),
                    "fps": f.get("fps"),
                    "filesize": f.get("filesize"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                })

            return {
                "title": info.get("title"),
                "best_quality": f"{info.get('height', 'N/A')}p" if info.get('height') else "N/A",
                "formats": formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
