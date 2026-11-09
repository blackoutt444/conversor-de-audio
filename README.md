# 🎧 Conversor de Áudio

Aplicação web em **Python/Flask** que baixa o áudio de um vídeo a partir do link e converte para o formato escolhido.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=flat-square&logo=css3&logoColor=white)

## ✨ Funcionalidades

- Cole o link de um vídeo e escolha o formato de saída: **MP3, WAV, OGG, FLAC ou AAC**
- Download da melhor faixa de áudio com **yt-dlp** e conversão com **pydub + FFmpeg**
- Cada conversão gera um arquivo com nome único (UUID), baixado direto pelo navegador
- Validação de entrada: só formatos suportados, e a rota de download não acessa arquivos fora da pasta de saída
- Interface em HTML/CSS/JavaScript puro com tema neon

## ⚙️ Como funciona

```text
Navegador ──POST /download {url, format}──► Flask
                                             │ 1. yt-dlp baixa o áudio e o FFmpeg extrai em MP3
                                             │ 2. pydub converte para o formato escolhido
Navegador ◄──── { file: "/download-file?name=…" } ┘
Navegador ──GET /download-file?name=…──► arquivo convertido
```

## 🚀 Como executar

**Requisitos:** Python 3.10+ e [FFmpeg](https://ffmpeg.org/download.html) instalado e disponível no `PATH`.

```bash
git clone https://github.com/blackoutt444/conversor-de-audio.git
cd conversor-de-audio

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python server.py
```

Acesse `http://localhost:5000`. A porta pode ser alterada pela variável de ambiente `PORT`.

Em produção, rode com Gunicorn:

```bash
gunicorn server:app
```

## 🔌 API

| Método | Rota | Descrição |
| ------ | ---- | --------- |
| `POST` | `/download` | Corpo `{"url": "<link>", "format": "mp3"}`. Retorna `{"success": true, "file": "/download-file?name=<arquivo>"}` |
| `GET`  | `/download-file?name=<arquivo>` | Baixa o arquivo convertido |

## 📁 Estrutura

```text
├── server.py            # API Flask (download, conversão e entrega do arquivo)
├── templates/
│   └── index.html       # Interface web
├── static/
│   └── favicon.png
├── requirements.txt
└── start.sh             # Script de inicialização
```

## ⚠️ Aviso

Projeto desenvolvido para fins de estudo. Use apenas com conteúdos que você tem o direito de baixar e respeite os termos de uso de cada plataforma.

## 👤 Autor

**Pedro Bezerra** · [GitHub](https://github.com/blackoutt444)
