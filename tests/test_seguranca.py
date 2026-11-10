import os
import pathlib
import threading
import time

import pytest
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

import server
from conftest import TONE, VIDEO_URL

TEMPLATE = pathlib.Path(server.__file__).parent / "templates" / "index.html"


# ---------------------------------------------------------------- URLs e SSRF

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://WWW.YouTube.com/watch?v=dQw4w9WgXcQ",
    "  https://youtu.be/dQw4w9WgXcQ  ",
])
def test_aceita_links_do_youtube(url):
    assert server.validate_url(url) is None


URLS_RECUSADAS = [
    "http://localhost:5000/",
    "http://127.0.0.1/",
    "http://[::1]/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/admin",
    "http://192.168.0.1/",
    "file:///etc/passwd",
    "ftp://youtube.com/video",
    "javascript:alert(1)",
    "https://example.com/video.mp3",
    "https://youtube.com.evil.example/watch?v=1",
    "https://evil.example/?next=https://youtube.com",
    "https://usuario:senha@youtube.com/watch?v=1",
    "https://youtube.com:8080/watch?v=1",
    "https://youtube.com:99999/watch?v=1",
    "https://www.youtube.com/watch?v=" + "a" * 3000,
]


@pytest.mark.parametrize("url", URLS_RECUSADAS)
def test_recusa_url_perigosa_sem_chamar_o_yt_dlp(client, fake_ydl, url):
    response = client.post("/download", json={"url": url, "format": "mp3"})
    assert response.status_code == 400
    assert fake_ydl.calls == []


@pytest.mark.parametrize("payload", [
    {"url": ["https://youtu.be/dQw4w9WgXcQ"], "format": "mp3"},
    {"url": 123, "format": "mp3"},
    {"url": VIDEO_URL, "format": ["mp3"]},
])
def test_recusa_tipos_invalidos(client, fake_ydl, payload):
    assert client.post("/download", json=payload).status_code == 400
    assert fake_ydl.calls == []


def test_yt_dlp_real_nao_acessa_url_fora_do_youtube(downloads):
    """Segunda camada: mesmo que a validação falhasse, o yt-dlp configurado
    não tem extrator para endereços arbitrários. Não usa rede."""
    options = server.build_ydl_options(str(downloads / "x.mp3"))
    with YoutubeDL(options) as ydl:
        with pytest.raises(DownloadError, match="No suitable extractor"):
            ydl.extract_info("http://169.254.169.254/latest/meta-data/", download=False)


def test_sem_cors_por_padrao(client):
    response = client.post("/download", json={}, headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers


# ------------------------------------------------- Limites de download e processamento

def test_opcoes_de_limite_do_yt_dlp():
    options = server.build_ydl_options("x.mp3")
    assert options["noplaylist"] is True
    assert options["allowed_extractors"] == ["youtube"]
    assert options["max_filesize"] == server.MAX_FILESIZE_BYTES
    assert options["socket_timeout"] == 30
    assert options["updatetime"] is False


@pytest.mark.parametrize("info, aceito", [
    ({"duration": 60}, True),
    ({"duration": server.MAX_DURATION_SECONDS}, True),
    ({"duration": server.MAX_DURATION_SECONDS + 1}, False),
    ({"is_live": True}, False),  # transmissão ao vivo não tem duração
])
def test_filtro_de_duracao(info, aceito):
    match_filter = server.build_ydl_options("x.mp3")["match_filter"]
    resultado = match_filter({"id": "x", "title": "t", **info}, incomplete=False)
    assert (resultado is None) is aceito


def test_video_recusado_pelos_filtros_retorna_422(client, fake_ydl, downloads, monkeypatch):
    # Quando um filtro recusa o vídeo, o yt-dlp termina sem erro e sem arquivo
    monkeypatch.setattr(fake_ydl, "download", lambda self, urls: None)
    response = client.post("/download", json={"url": VIDEO_URL, "format": "mp3"})
    assert response.status_code == 422
    assert response.get_json()["success"] is False
    assert list(downloads.iterdir()) == []


def test_limite_de_conversoes_simultaneas(client, fake_ydl, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "conversion_slots", slots)
    payload = {"url": VIDEO_URL, "format": "mp3"}

    slots.acquire()  # simula uma conversão em andamento
    try:
        assert client.post("/download", json=payload).status_code == 503
        assert fake_ydl.calls == []
    finally:
        slots.release()

    assert client.post("/download", json=payload).status_code == 200


def test_vaga_e_liberada_mesmo_quando_a_conversao_falha(client, fake_ydl, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "conversion_slots", slots)

    def falha(self, urls):
        raise RuntimeError("falhou no meio")

    monkeypatch.setattr(fake_ydl, "download", falha)
    assert client.post("/download", json={"url": VIDEO_URL, "format": "mp3"}).status_code == 500
    assert slots.acquire(blocking=False) is True
    slots.release()


def test_falha_ao_apagar_temporario_nao_quebra_a_resposta(client, fake_ydl, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "conversion_slots", slots)

    def baixa_e_falha(self, urls):
        TONE.export(self.opts["outtmpl"], format="mp3")
        raise RuntimeError("falhou depois de baixar")

    def remove_bloqueado(path):
        raise PermissionError("arquivo em uso")

    monkeypatch.setattr(fake_ydl, "download", baixa_e_falha)
    monkeypatch.setattr(server.os, "remove", remove_bloqueado)

    response = client.post("/download", json={"url": VIDEO_URL, "format": "mp3"})
    assert response.status_code == 500
    assert response.get_json()["error"] == "Erro interno ao processar o áudio."
    assert slots.acquire(blocking=False) is True
    slots.release()


def test_corpo_grande_demais(client, fake_ydl):
    response = client.post("/download", data="x" * (32 * 1024), content_type="application/json")
    assert response.status_code == 413
    assert response.get_json()["success"] is False
    assert fake_ydl.calls == []


# ------------------------------------------------------ Expiração e limpeza

def test_arquivos_expirados_sao_apagados(client, downloads):
    antigo = downloads / "11111111-1111-1111-1111-111111111111.mp3"
    recente = downloads / "22222222-2222-2222-2222-222222222222.mp3"
    antigo.write_bytes(b"x")
    recente.write_bytes(b"x")
    expirou = time.time() - server.FILE_TTL_SECONDS - 60
    os.utime(antigo, (expirou, expirou))

    assert client.get(f"/download-file?name={antigo.name}").status_code == 404
    assert not antigo.exists()
    assert client.get(f"/download-file?name={recente.name}").status_code == 200
    assert recente.exists()


def test_limpeza_tambem_roda_a_cada_conversao(client, downloads):
    antigo = downloads / "33333333-3333-3333-3333-333333333333.wav"
    antigo.write_bytes(b"x")
    expirou = time.time() - server.FILE_TTL_SECONDS - 60
    os.utime(antigo, (expirou, expirou))

    assert client.post("/download", json={"url": VIDEO_URL, "format": "mp3"}).status_code == 200
    assert not antigo.exists()


def test_mp3_com_data_antiga_do_video_nao_expira_na_hora(client, fake_ydl, monkeypatch):
    # O yt-dlp pode gravar no arquivo a data de publicação do vídeo
    def download_com_data_antiga(self, urls):
        TONE.export(self.opts["outtmpl"], format="mp3")
        um_ano_atras = time.time() - 365 * 24 * 3600
        os.utime(self.opts["outtmpl"], (um_ano_atras, um_ano_atras))

    monkeypatch.setattr(fake_ydl, "download", download_com_data_antiga)
    response = client.post("/download", json={"url": VIDEO_URL, "format": "mp3"})
    assert response.status_code == 200
    assert client.get(response.get_json()["file"]).status_code == 200


@pytest.mark.parametrize("name", ["abc_original.mp3", "notas.txt", "../server.py", ""])
def test_so_entrega_arquivos_finais(client, downloads, name):
    (downloads / "abc_original.mp3").write_bytes(b"x")
    (downloads / "notas.txt").write_text("x")
    assert client.get(f"/download-file?name={name}").status_code == 404


# ------------------------------------------ Mensagens de erro e XSS no frontend

def test_erro_interno_nao_expoe_detalhes(client, fake_ydl, monkeypatch):
    def falha(self, urls):
        raise RuntimeError(r"C:\segredo\config.py token=abc123")

    monkeypatch.setattr(fake_ydl, "download", falha)
    response = client.post("/download", json={"url": VIDEO_URL, "format": "mp3"})
    assert response.status_code == 500
    assert response.get_json()["error"] == "Erro interno ao processar o áudio."
    assert "segredo" not in response.get_data(as_text=True)


def test_falha_de_download_retorna_mensagem_generica(client, fake_ydl, monkeypatch):
    def falha(self, urls):
        raise DownloadError("ERROR: <img src=x onerror=alert(1)> /home/app/cookies.txt")

    monkeypatch.setattr(fake_ydl, "download", falha)
    response = client.post("/download", json={"url": VIDEO_URL, "format": "mp3"})
    assert response.status_code == 422
    text = response.get_data(as_text=True)
    assert "cookies.txt" not in text
    assert "<img" not in text


def test_frontend_nao_insere_html_vindo_do_servidor():
    html = TEMPLATE.read_text(encoding="utf-8")
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in html, f"{sink} encontrado em index.html"
    assert "textContent" in html
