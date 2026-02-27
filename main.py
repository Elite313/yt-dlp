from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
                "video_url": info.get("url"),
                "platform": info.get("extractor"),
            }
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
                })

            return {"formats": formats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/download-url")
def get_download_url(url: str, format: str = "best"):
    """Get direct download URL"""
    try:
        ydl_opts = {
            "quiet": True,
            "no_download": True,
            "format": format,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "title": info.get("title"),
                "download_url": info.get("url"),
                "ext": info.get("ext"),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
