from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
from yt_dlp import YoutubeDL
from pydub import AudioSegment
import uuid

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Formatos de saída aceitos (evita repassar valores arbitrários ao FFmpeg)
ALLOWED_FORMATS = {"mp3", "wav", "ogg", "flac", "aac"}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    audio_format = data.get("format")

    if not url or not audio_format:
        return jsonify({"success": False, "error": "URL ou formato ausente!"}), 400

    if audio_format not in ALLOWED_FORMATS:
        return jsonify({"success": False, "error": "Formato não suportado."}), 400

    try:
        # Nome temporário único
        audio_id = str(uuid.uuid4())
        temp_filename = os.path.join(DOWNLOAD_FOLDER, f"{audio_id}.mp3")

        # 1. Baixa o áudio com yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_filename,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 2. Converte para o formato desejado usando pydub
        audio = AudioSegment.from_file(temp_filename, format="mp3")
        final_filename = f"{audio_id}.{audio_format}"
        final_path = os.path.join(DOWNLOAD_FOLDER, final_filename)
        # O FFmpeg grava AAC puro pelo muxer "adts" (não existe muxer "aac")
        ffmpeg_format = "adts" if audio_format == "aac" else audio_format
        audio.export(final_path, format=ffmpeg_format)

        # Remove o arquivo temporário
        os.remove(temp_filename)

        return jsonify({
            "success": True,
            "file": f"/download-file?name={final_filename}"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/download-file")
def download_file():
    name = request.args.get("name", "")
    # send_from_directory bloqueia caminhos fora da pasta (ex.: "../server.py")
    # e responde 404 quando o arquivo não existe.
    return send_from_directory(DOWNLOAD_FOLDER, name, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
