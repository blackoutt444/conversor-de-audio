import shutil
import threading

import pytest
from pydub.generators import Sine

import server

if shutil.which("ffprobe") is None:
    # Sem ffprobe o pydub não inspeciona o arquivo, mas o ffmpeg basta para converter
    import pydub.audio_segment

    pydub.audio_segment.mediainfo_json = lambda *args, **kwargs: None

TONE_MS = 1000
TONE = Sine(440).to_audio_segment(duration=TONE_MS)
VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class FakeYoutubeDL:
    """Substitui o yt-dlp: grava um MP3 local em vez de baixar da internet."""

    calls = []

    def __init__(self, opts):
        self.opts = opts
        FakeYoutubeDL.calls.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        TONE.export(self.opts["outtmpl"], format="mp3")


@pytest.fixture
def downloads(tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    return folder


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYoutubeDL.calls = []
    monkeypatch.setattr(server, "YoutubeDL", FakeYoutubeDL)
    return FakeYoutubeDL


@pytest.fixture
def client(downloads, fake_ydl, monkeypatch):
    monkeypatch.setattr(server, "DOWNLOAD_FOLDER", str(downloads))
    monkeypatch.setattr(server, "conversion_slots", threading.BoundedSemaphore(server.MAX_CONCURRENT_JOBS))
    server.app.config["TESTING"] = True
    return server.app.test_client()
