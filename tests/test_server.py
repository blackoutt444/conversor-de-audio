import shutil

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

import server

if shutil.which("ffprobe") is None:
    # Sem ffprobe o pydub não inspeciona o arquivo, mas o ffmpeg basta para converter
    import pydub.audio_segment

    pydub.audio_segment.mediainfo_json = lambda *args, **kwargs: None

TONE_MS = 1000
TONE = Sine(440).to_audio_segment(duration=TONE_MS)


class FakeYoutubeDL:
    """Substitui o yt-dlp: grava um MP3 local em vez de baixar da internet."""

    def __init__(self, opts):
        self.outtmpl = opts["outtmpl"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        TONE.export(self.outtmpl, format="mp3")


@pytest.fixture
def downloads(tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    return folder


@pytest.fixture
def client(downloads, monkeypatch):
    monkeypatch.setattr(server, "DOWNLOAD_FOLDER", str(downloads))
    monkeypatch.setattr(server, "YoutubeDL", FakeYoutubeDL)
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_pagina_inicial(client):
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("payload", [{}, {"url": "https://exemplo/video"}, {"format": "mp3"}])
def test_campos_obrigatorios(client, payload):
    response = client.post("/download", json=payload)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_requisicao_sem_json(client):
    assert client.post("/download").status_code == 400


def test_formato_nao_suportado(client):
    response = client.post("/download", json={"url": "https://exemplo/video", "format": "exe"})
    assert response.status_code == 400


def test_download_nao_sai_da_pasta(client, downloads):
    (downloads.parent / "segredo.txt").write_text("não deveria vazar")
    assert client.get("/download-file?name=../segredo.txt").status_code == 404


def test_arquivo_inexistente(client):
    assert client.get("/download-file?name=nao-existe.mp3").status_code == 404


@pytest.mark.parametrize("audio_format", sorted(server.ALLOWED_FORMATS))
def test_converte_para_cada_formato(client, downloads, audio_format):
    response = client.post("/download", json={"url": "https://exemplo/video", "format": audio_format})
    body = response.get_json()
    assert response.status_code == 200, body
    assert body["success"] is True

    file_response = client.get(body["file"])
    assert file_response.status_code == 200
    assert "attachment" in file_response.headers["Content-Disposition"]

    # Só o arquivo final fica na pasta: o temporário foi removido
    files = list(downloads.iterdir())
    assert len(files) == 1
    assert files[0].suffix == f".{audio_format}"

    # O áudio convertido abre e mantém a duração original
    converted = AudioSegment.from_file(files[0])
    assert abs(len(converted) - TONE_MS) < 100
