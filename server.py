from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
from yt_dlp import YoutubeDL
from pydub import AudioSegment
import uuid

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return "Servidor Flask está rodando com yt-dlp + pydub!"

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url")
    format = data.get("format")

    if not url or not format:
        return jsonify({"success": False, "error": "URL ou formato ausente!"})

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
        final_filename = f"{audio_id}.{format}"
        final_path = os.path.join(DOWNLOAD_FOLDER, final_filename)
        audio.export(final_path, format=format)

        # Remove o arquivo temporário
        os.remove(temp_filename)

        return jsonify({
            "success": True,
            "file": f"/download-file?name={final_filename}"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/download-file")
def download_file():
    name = request.args.get("name")
    filepath = os.path.join(DOWNLOAD_FOLDER, name)
    if not os.path.exists(filepath):
        return "Arquivo não encontrado", 404
    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
