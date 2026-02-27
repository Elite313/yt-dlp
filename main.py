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


@app.get("/")
def health():
    return {
        "status": "running",
        "endpoints": ["/info", "/video", "/direct-url", "/formats"]
    }


@app.get("/info")
def get_info(url: str):
    """Extract video metadata"""
    try:
        ydl_opts = {"quiet": True, "no_download": True}
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

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
        ydl_opts = {"quiet": True, "no_download": True}
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Get URL from formats
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
def download_video(url: str):
    """Download and return video file"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "video.%(ext)s")

        ydl_opts = {
            "outtmpl": output_path,
            "quiet": True,
        }
        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

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

        if not final_path:
            raise HTTPException(status_code=500, detail="Download failed")

        return FileResponse(
            final_path,
            media_type="video/mp4",
            filename=f"{title}.mp4"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/formats")
def get_formats(url: str):
    """Get available formats"""
    try:
        ydl_opts = {"quiet": True, "no_download": True}
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
                })
            return {"title": info.get("title"), "formats": formats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
