from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os

print("Arquivos em templates:", os.listdir(os.path.join(os.getcwd(), "templates")))
print("CWD:", os.getcwd())
print("Arquivos na pasta templates:", os.listdir(os.path.join(os.getcwd(), "templates")))

app = Flask(__name__, template_folder=os.path.join(os.getcwd(), "templates"))

CORS(app)  # Permitir requisições do frontend

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url")
    format = data.get("format")

    if not url or not format:
        return jsonify({"success": False, "error": "URL ou formato ausente!"})

    # Aqui você deve implementar a lógica de download/conversão real
    # Exemplo fictício de resposta:
    return jsonify({"success": True, "file": f"https://conversor-de-audio.onrender.com/static/musica.{format}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Usa a porta do ambiente ou 5000 como fallback
    app.run(host="0.0.0.0", port=port)
