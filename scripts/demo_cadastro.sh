#!/usr/bin/env bash
# Roda a demonstracao do cadastro self-service dentro do container de desenvolvimento.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker-compose.dev.yml run --rm -T web python manage.py shell < scripts/demo_cadastro.py
