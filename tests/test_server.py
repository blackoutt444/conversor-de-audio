import pytest
from pydub import AudioSegment

import server
from conftest import TONE_MS, VIDEO_URL


def test_pagina_inicial(client):
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("payload", [{}, {"url": VIDEO_URL}, {"format": "mp3"}])
def test_campos_obrigatorios(client, payload):
    response = client.post("/download", json=payload)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_requisicao_sem_json(client):
    assert client.post("/download").status_code == 400


def test_formato_nao_suportado(client):
    response = client.post("/download", json={"url": VIDEO_URL, "format": "exe"})
    assert response.status_code == 400


def test_download_nao_sai_da_pasta(client, downloads):
    (downloads.parent / "segredo.txt").write_text("não deveria vazar")
    assert client.get("/download-file?name=../segredo.txt").status_code == 404


def test_arquivo_inexistente(client):
    name = "00000000-0000-0000-0000-000000000000.mp3"
    assert client.get(f"/download-file?name={name}").status_code == 404


@pytest.mark.parametrize("audio_format", sorted(server.ALLOWED_FORMATS))
def test_converte_para_cada_formato(client, downloads, audio_format):
    response = client.post("/download", json={"url": VIDEO_URL, "format": audio_format})
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
