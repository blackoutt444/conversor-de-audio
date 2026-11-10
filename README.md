# 🎧 Conversor de Áudio

[![CI](https://github.com/blackoutt444/conversor-de-audio/actions/workflows/ci.yml/badge.svg)](https://github.com/blackoutt444/conversor-de-audio/actions/workflows/ci.yml)

Aplicação web em **Python/Flask** que baixa o áudio de um vídeo a partir do link e converte para o formato escolhido.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-1572B6?style=flat-square&logo=css&logoColor=white)

## ✨ Funcionalidades

- Cole o link de um vídeo do **YouTube** e escolha o formato de saída: **MP3, WAV, OGG, FLAC ou AAC**
- Download da melhor faixa de áudio com **yt-dlp** e conversão com **pydub + FFmpeg**
- Cada conversão gera um arquivo com nome único (UUID), baixado direto pelo navegador e apagado depois de 30 minutos
- Limites de duração, tamanho e conversões simultâneas, e proteção contra SSRF (veja [Segurança e limites](#-segurança-e-limites))
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

Acesse `http://localhost:5000`. A porta pode ser alterada pela variável de ambiente `PORT`. O `python server.py` usa o servidor de desenvolvimento do Flask e serve só para uso local.

Em produção (Linux), use o `start.sh`, que inicia o Gunicorn:

```bash
./start.sh
```

| Variável | Padrão | Descrição |
| -------- | ------ | --------- |
| `PORT` | `5000` | Porta HTTP |
| `WEB_CONCURRENCY` | `2` | Número de workers do Gunicorn |
| `GUNICORN_TIMEOUT` | `300` | Segundos até o Gunicorn encerrar uma requisição. O padrão do Gunicorn (30 s) é curto demais para baixar e converter um vídeo de 10 minutos |

## 🔒 Segurança e limites

| Risco | Proteção |
| ----- | -------- |
| **SSRF** (usar o servidor para acessar endereços internos) | Só aceita `http`/`https` de `youtube.com`, `www.youtube.com`, `m.youtube.com`, `music.youtube.com` e `youtu.be`, sem usuário, senha ou porta. Como segunda camada, o yt-dlp roda só com o extrator do YouTube (`allowed_extractors`), sem o extrator genérico |
| **Abuso de recursos** | Duração máxima, tamanho máximo, playlists desativadas (`noplaylist`), timeout de rede, limite de conversões simultâneas (HTTP 503 quando ocupado) e corpo da requisição limitado a 16 KB |
| **Acúmulo de arquivos** | Os arquivos gerados expiram e são apagados a cada requisição; o temporário é removido mesmo em caso de erro |
| **XSS** | O frontend insere mensagens do servidor só como texto (`textContent`), nunca como HTML |
| **Vazamento de informação** | Erros internos vão para o log; o usuário recebe uma mensagem genérica |
| **Path traversal** | `/download-file` só entrega arquivos `<uuid>.<formato>` da pasta de downloads |
| **CORS** | Desligado por padrão, já que o frontend é servido pelo próprio Flask |

Os limites podem ser ajustados por variáveis de ambiente:

| Variável | Padrão | Descrição |
| -------- | ------ | --------- |
| `MAX_DURATION_MINUTES` | `10` | Duração máxima do vídeo. Transmissões ao vivo são recusadas |
| `MAX_FILESIZE_MB` | `50` | Tamanho máximo do download |
| `MAX_CONCURRENT_JOBS` | `2` | Conversões simultâneas **por processo** (com N workers do Gunicorn, o total é N × este valor) |
| `FILE_TTL_MINUTES` | `30` | Tempo até um arquivo gerado ser apagado |
| `CORS_ORIGINS` | *(vazio)* | Origens liberadas para chamar a API, separadas por vírgula |

## 🧪 Testes

A suíte usa **pytest** e roda no **GitHub Actions** (Python 3.12 e 3.13) a cada push e pull request. O yt-dlp é substituído por um MP3 gerado localmente, então os testes não dependem de internet, mas a conversão usa o FFmpeg de verdade.

```bash
pip install -r requirements-dev.txt
pytest -v
```

O que é verificado:

- conversão para cada formato suportado, conferindo que o arquivo abre e mantém a duração
- validação de URL: 16 casos de SSRF e URLs malformadas são recusados sem chamar o yt-dlp, e o yt-dlp real (sem rede) não aceita endereços fora do YouTube
- limites: filtro de duração (incluindo lives), opções do yt-dlp, limite de concorrência, liberação da vaga após erro e corpo grande demais
- expiração: arquivos antigos são apagados e arquivos recém-convertidos não expiram, mesmo quando o yt-dlp grava uma data antiga
- erros não expõem caminhos nem tokens, e o frontend não usa `innerHTML`
- remoção do arquivo temporário e bloqueio de acesso fora da pasta de downloads (`../`)

## 🔌 API

| Método | Rota | Descrição |
| ------ | ---- | --------- |
| `POST` | `/download` | Corpo `{"url": "<link>", "format": "mp3"}`. Retorna `{"success": true, "file": "/download-file?name=<arquivo>"}` |
| `GET`  | `/download-file?name=<arquivo>` | Baixa o arquivo convertido (404 se não existir ou já tiver expirado) |

Respostas de erro de `POST /download`, sempre no formato `{"success": false, "error": "<mensagem>"}`:

| Status | Quando |
| ------ | ------ |
| `400` | Campos ausentes, formato não suportado ou URL recusada |
| `413` | Corpo da requisição maior que 16 KB |
| `422` | Vídeo indisponível, privado, ao vivo, longo demais ou grande demais |
| `503` | Limite de conversões simultâneas atingido |
| `500` | Erro interno (o detalhe fica só no log do servidor) |

## 📁 Estrutura

```text
├── server.py            # API Flask (download, conversão e entrega do arquivo)
├── templates/
│   └── index.html       # Interface web
├── static/
│   └── favicon.png
├── tests/
│   ├── conftest.py      # Fixtures (yt-dlp simulado, pasta temporária)
│   ├── test_server.py   # Fluxo principal e conversões
│   └── test_seguranca.py # SSRF, limites, expiração e XSS
├── .github/workflows/
│   └── ci.yml           # Integração contínua
├── requirements.txt
├── requirements-dev.txt # Dependências de desenvolvimento (pytest)
└── start.sh             # Script de inicialização
```

## ⚠️ Aviso

Projeto desenvolvido para fins de estudo. Use apenas com conteúdos que você tem o direito de baixar e respeite os termos de uso de cada plataforma.

## 👤 Autor

**Pedro Bezerra** · [GitHub](https://github.com/blackoutt444)
