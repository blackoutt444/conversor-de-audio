from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Permitir requisições do frontend

@app.route("/")
def home():
    return "Servidor Flask está rodando!"

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url")
    format = data.get("format")

    if not url or not format:
        return jsonify({"success": False, "error": "URL ou formato ausente!"})

    # Aqui seria onde você faria o download/conversão do áudio
    # Exemplo fictício de resposta:
    return jsonify({"success": True, "file": f"/downloads/musica.{format}"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
