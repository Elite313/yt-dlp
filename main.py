import os
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import yt_dlp

app = FastAPI(title="yt-dlp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "running", "service": "yt-dlp-api"}


@app.get("/info")
def get_info(url: str):
    """Extract video metadata without downloading"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
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
def get_direct_url(url: str):
    """Get direct video URL (works better for Instagram)"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
            "format": "best[ext=mp4]/best",
            "extractor_args": {"youtube": {"player_client": ["android"]}}
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Get the direct URL
            video_url = info.get("url")

            # If no direct URL, try to get from formats
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
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/video")
def download_video(url: str):
    """Download and return video file directly"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "video.mp4")

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}}
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        # Return the video file
        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename=f"{title}.mp4"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/formats")
def get_formats(url: str):
    """Get available download formats"""
    try:
        ydl_opts = {"quiet": True, "no_download": True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []

            for f in info.get("formats", []):
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "filesize": f.get("filesize"),
                    "url": f.get("url"),
                })

            return {"formats": formats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
