#!/usr/bin/env bash
# Inicia a aplicação em produção com Gunicorn.
# O timeout precisa cobrir o download e a conversão de um vídeo no limite de
# duração (MAX_DURATION_MINUTES); o padrão do Gunicorn (30 s) é curto demais.
set -euo pipefail

exec gunicorn server:app \
  --bind "0.0.0.0:${PORT:-5000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-300}"
