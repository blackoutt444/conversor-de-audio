import os
import re
import threading
import time
import uuid
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from pydub import AudioSegment
from werkzeug.exceptions import RequestEntityTooLarge
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, match_filter_func

app = Flask(__name__)

# O corpo das requisições é só {"url", "format"}: 16 KB é mais do que suficiente
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

# O frontend é servido pelo próprio Flask e não precisa de CORS. Libere outras
# origens só se for necessário, por exemplo: CORS_ORIGINS=https://meusite.com
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if CORS_ORIGINS:
    CORS(app, origins=CORS_ORIGINS)

DOWNLOAD_FOLDER = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Formatos de saída aceitos (evita repassar valores arbitrários ao FFmpeg)
ALLOWED_FORMATS = {"mp3", "wav", "ogg", "flac", "aac"}

# Só links do YouTube. Junto com allowed_extractors no yt-dlp, isso impede que o
# servidor seja usado para acessar endereços internos ou arbitrários (SSRF).
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
MAX_URL_LENGTH = 2048

# Limites de processamento (configuráveis por variável de ambiente)
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_MINUTES", 10)) * 60
MAX_FILESIZE_BYTES = int(os.environ.get("MAX_FILESIZE_MB", 50)) * 1024 * 1024
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", 2))
FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_MINUTES", 30)) * 60

# Conversões simultâneas por processo
conversion_slots = threading.BoundedSemaphore(MAX_CONCURRENT_JOBS)

# Nome dos arquivos entregues: <uuid>.<formato>
OUTPUT_NAME = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(mp3|wav|ogg|flac|aac)$")


def error_response(message, status):
    return jsonify({"success": False, "error": message}), status


def validate_url(url):
    """Retorna uma mensagem de erro, ou None se o link for aceito."""
    if not isinstance(url, str) or not url.strip():
        return "URL ausente."
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        return "URL longa demais."
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return "URL inválida."
    if parts.scheme not in ("http", "https"):
        return "Use um link http ou https."
    if parts.username or parts.password or port is not None:
        return "URL inválida."
    if (parts.hostname or "") not in ALLOWED_HOSTS:
        return "Só são aceitos links do YouTube."
    return None


def build_ydl_options(output_path):
    return {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        # Só o extrator do YouTube: o extrator genérico buscaria qualquer URL
        "allowed_extractors": ["youtube"],
        # Um link com &list= baixa só o vídeo, nunca a playlist inteira
        "noplaylist": True,
        # Recusa vídeos longos e transmissões ao vivo (sem duração definida)
        "match_filter": match_filter_func([f"duration <= {MAX_DURATION_SECONDS}"]),
        "max_filesize": MAX_FILESIZE_BYTES,
        "socket_timeout": 30,
        # Sem isso o yt-dlp grava a data de publicação do vídeo no arquivo,
        # e a limpeza por idade o apagaria antes do download
        "updatetime": False,
    }


def cleanup_expired_files(now=None):
    """Apaga os arquivos gerados há mais de FILE_TTL_SECONDS. Retorna quantos apagou."""
    now = time.time() if now is None else now
    removed = 0
    for entry in os.scandir(DOWNLOAD_FOLDER):
        try:
            if entry.is_file() and now - entry.stat().st_mtime > FILE_TTL_SECONDS:
                os.remove(entry.path)
                removed += 1
        except FileNotFoundError:
            pass  # outra requisição já apagou
    return removed


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return error_response("Requisição grande demais.", 413)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    cleanup_expired_files()

    data = request.get_json(silent=True) or {}
    url = data.get("url")
    audio_format = data.get("format")

    if not url or not audio_format:
        return error_response("URL ou formato ausente!", 400)

    if not isinstance(audio_format, str) or audio_format not in ALLOWED_FORMATS:
        return error_response("Formato não suportado.", 400)

    url_error = validate_url(url)
    if url_error:
        return error_response(url_error, 400)

    if not conversion_slots.acquire(blocking=False):
        return error_response("Servidor ocupado. Tente novamente em instantes.", 503)

    # Nomes únicos: o temporário precisa ser diferente do final, senão a
    # limpeza do temporário apagaria o próprio resultado quando o formato é MP3
    audio_id = str(uuid.uuid4())
    temp_filename = os.path.join(DOWNLOAD_FOLDER, f"{audio_id}_original.mp3")
    final_filename = f"{audio_id}.{audio_format}"
    final_path = os.path.join(DOWNLOAD_FOLDER, final_filename)

    try:
        # 1. Baixa o áudio com yt-dlp
        with YoutubeDL(build_ydl_options(temp_filename)) as ydl:
            ydl.download([url.strip()])

        if not os.path.exists(temp_filename):
            # O yt-dlp pula sem erro o que os filtros recusam (duração ou tamanho)
            return error_response(
                f"Vídeo indisponível, ao vivo, com mais de {MAX_DURATION_SECONDS // 60} minutos "
                f"ou maior que {MAX_FILESIZE_BYTES // (1024 * 1024)} MB.",
                422,
            )

        # 2. Converte para o formato desejado usando pydub
        if audio_format == "mp3":
            # Já está em MP3: evita uma segunda compressão com perda
            os.replace(temp_filename, final_path)
        else:
            audio = AudioSegment.from_file(temp_filename, format="mp3")
            # O FFmpeg grava AAC puro pelo muxer "adts" (não existe muxer "aac")
            ffmpeg_format = "adts" if audio_format == "aac" else audio_format
            audio.export(final_path, format=ffmpeg_format)

        # A expiração conta a partir de agora
        os.utime(final_path, None)

        return jsonify({
            "success": True,
            "file": f"/download-file?name={final_filename}"
        })

    except DownloadError:
        app.logger.warning("Falha no download de %s", url, exc_info=True)
        return error_response(
            "Não foi possível baixar este vídeo. Verifique se o link é público e tente de novo.", 422
        )

    except Exception:
        # O detalhe vai para o log; o usuário recebe uma mensagem genérica
        app.logger.exception("Erro ao processar %s", url)
        return error_response("Erro interno ao processar o áudio.", 500)

    finally:
        conversion_slots.release()
        # Remove o temporário mesmo se algo falhar no meio do caminho. Uma falha
        # aqui não pode substituir a resposta já montada; a limpeza por idade
        # apaga o arquivo depois.
        try:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except OSError:
            app.logger.warning("Não foi possível remover %s", temp_filename, exc_info=True)


@app.route("/download-file")
def download_file():
    cleanup_expired_files()
    name = request.args.get("name", "")
    if not OUTPUT_NAME.fullmatch(name):
        return "Arquivo não encontrado", 404
    # send_from_directory também bloqueia caminhos fora da pasta e responde 404
    # quando o arquivo não existe (ou já expirou)
    return send_from_directory(DOWNLOAD_FOLDER, name, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
