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


@app.get("/")
def health():
    return {"status": "running", "service": "yt-dlp-api", "quality": "highest"}


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
def get_direct_url(url: str, quality: str = "highest"):
    """Get direct video URL"""
    try:
        # Format selection based on quality
        if quality == "highest":
            format_sel = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "720p":
            format_sel = "best[height<=720][ext=mp4]/best[height<=720]/best"
        elif quality == "480p":
            format_sel = "best[height<=480][ext=mp4]/best[height<=480]/best"
        else:
            format_sel = "best[ext=mp4]/best"

        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "no_warnings": True,
            "format": format_sel,
            "extractor_args": {"youtube": {"player_client": ["android"]}}
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
    """Download and return video file in highest quality"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "video.mp4")

        # Format selection for highest quality
        # This gets best video + best audio and merges them
        if quality == "highest":
            format_sel = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
        elif quality == "1080p":
            format_sel = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"
        elif quality == "720p":
            format_sel = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
        elif quality == "480p":
            format_sel = "best[height<=480][ext=mp4]/best"
        else:
            format_sel = "best[ext=mp4]/best"

        ydl_opts = {
            "format": format_sel,
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            # Merge video + audio into mp4
            "merge_output_format": "mp4",
            # Post-processing
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        # Check if file exists (might have different extension after merge)
        if not os.path.exists(output_path):
            # Try to find the downloaded file
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
    """Get all available formats with quality info"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}}
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
                "formats": formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
