"""
plugins/desktop_downloader.py — Universal Desktop Downloader for JARVIS.

Enables downloading any file, document, PDF, image, archive, or media
(YouTube, Vimeo, web video, and audio) directly to the user's Desktop.

Features:
  1. Auto-detects media platform URLs (YouTube, Twitter/X, Instagram, TikTok, etc.)
     and downloads high-quality video or audio via yt-dlp.
  2. Directly streams web files (PDF, ZIP, images, docs, executables) via requests/urllib.
  3. Saves directly to the Windows Desktop (or custom destination).
  4. Provides real-time activity updates to the JARVIS HUD.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from core import outcome

PLUGIN = {
    "name": "desktop_downloader",
    "description": (
        "Downloads any file, document, PDF, image, archive, or video/audio directly onto the user's Desktop. "
        "Supports YouTube, web videos, audio tracks, and direct web file URLs. Use for requests like "
        "'download this file to my desktop', 'download this YouTube video to my desktop', "
        "'download audio from <url>', or 'download this PDF/image from <url>'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "The URL of the file, web page, or video to download.",
            },
            "media_type": {
                "type": "STRING",
                "description": "Type of download: 'auto' (default), 'video', 'audio', or 'file'.",
            },
            "file_name": {
                "type": "STRING",
                "description": "Optional custom filename to save as on the Desktop.",
            },
            "destination": {
                "type": "STRING",
                "description": "Optional target folder. Defaults to user's Desktop.",
            },
        },
        "required": ["url"],
    },
}

_DESKTOP_DIR = Path.home() / "Desktop"

_VIDEO_DOMAINS = (
    "youtube.com", "youtu.be", "vimeo.com", "twitter.com", "x.com",
    "tiktok.com", "instagram.com", "facebook.com", "fb.watch", "reddit.com"
)


def _resolve_dest(custom_path: Optional[str] = None) -> Path:
    """Resolve target directory, defaulting to Windows Desktop."""
    if custom_path:
        p = Path(custom_path.strip().strip("\"'")).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    _DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    return _DESKTOP_DIR


def _is_media_host(url: str) -> bool:
    """Check if the URL belongs to a known media hosting platform."""
    domain = urllib.parse.urlparse(url).netloc.lower()
    return any(host in domain for host in _VIDEO_DOMAINS)


def _download_media(url: str, dest_dir: Path, as_audio: bool, custom_name: Optional[str], player) -> str:
    """Download video or audio using yt-dlp."""
    try:
        import yt_dlp
    except ImportError:
        return "Sir, yt-dlp is not installed in the environment."

    out_pattern = f"{custom_name}.%(ext)s" if custom_name else "%(title)s.%(ext)s"
    out_tmpl = str(dest_dir / out_pattern)

    ydl_opts: Dict[str, Any] = {
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    if as_audio:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    if player:
        mode = "audio" if as_audio else "video"
        player.write_log(f"JARVIS: Starting {mode} download to Desktop from {url[:50]}...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Media")
            ext = "mp3" if as_audio else info.get("ext", "mp4")

        msg = f"Sir, I have downloaded '{title}' directly to your Desktop as an {ext.upper()} file."
        if player:
            player.write_log(f"JARVIS: Download complete: '{title}' -> Desktop")
        return msg
    except Exception as e:
        return f"Sir, media download encountered an issue: {e}"


def _download_direct_file(url: str, dest_dir: Path, custom_name: Optional[str], player) -> str:
    """Stream download any web file to the Desktop."""
    clean_url = url.strip()
    if player:
        player.write_log(f"JARVIS: Downloading file from {clean_url[:60]}...")

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(clean_url, stream=True, timeout=30, headers=headers)
        resp.raise_for_status()

        # Determine filename
        target_name = custom_name
        if not target_name:
            cd = resp.headers.get("content-disposition", "")
            match = re.search(r'filename=["\']?([^"\';]+)["\']?', cd)
            if match:
                target_name = match.group(1).strip()
            else:
                path_part = urllib.parse.urlparse(clean_url).path
                target_name = Path(path_part).name or "downloaded_file"

        target_file = dest_dir / target_name
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(target_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        size_mb = downloaded / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb >= 1.0 else f"{downloaded / 1024:.1f} KB"

        msg = f"Sir, '{target_file.name}' ({size_str}) has been downloaded directly to your Desktop."
        if player:
            player.write_log(f"JARVIS: Saved '{target_file.name}' ({size_str}) -> {target_file}")
        return msg
    except Exception as e:
        return f"Sir, failed to download the file: {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the desktop_downloader plugin."""
    url = str(parameters.get("url", "")).strip()
    if not url:
        return "Sir, please provide the URL or link you would like me to download to your Desktop."

    media_type = str(parameters.get("media_type", "auto")).strip().lower()
    custom_name = parameters.get("file_name")
    dest_dir = _resolve_dest(parameters.get("destination"))

    try:
        # Check if URL is media platform or media requested
        if media_type == "audio":
            return _download_media(url, dest_dir, as_audio=True, custom_name=custom_name, player=player)
        elif media_type == "video" or _is_media_host(url):
            return _download_media(url, dest_dir, as_audio=False, custom_name=custom_name, player=player)
        else:
            return _download_direct_file(url, dest_dir, custom_name=custom_name, player=player)
    except Exception as e:
        outcome.notify_failure("desktop_downloader", f"Download failed: {e}")
        return f"Sir, download operations encountered an error: {e}"

