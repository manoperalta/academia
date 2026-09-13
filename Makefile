# Atalhos do ambiente de desenvolvimento (i3). Sempre via docker compose dev.
COMPOSE := docker compose -f docker-compose.dev.yml

.PHONY: subir descer shell check migracoes migrar test lint formatar tenantizar docs

subir:            ## sobe postgres + constroi a imagem de dev
	$(COMPOSE) up -d db
	$(COMPOSE) build web

descer:
	$(COMPOSE) down

shell:
	$(COMPOSE) run --rm web python manage.py shell

check:
	$(COMPOSE) run --rm web python manage.py check

migracoes:        ## mostra o que falta migrar
	$(COMPOSE) run --rm web python manage.py makemigrations --check --dry-run

migrar:
	$(COMPOSE) run --rm web python manage.py migrate

test:
	$(COMPOSE) run --rm web pytest

lint:
	$(COMPOSE) run --rm web ruff check .

formatar:
	$(COMPOSE) run --rm web ruff format .

tenantizar:       ## cria a rede padrao e etiqueta os dados existentes
	$(COMPOSE) run --rm web python manage.py tenantizar --slug padrao --nome "Academia (rede padrao)"

docs:             ## gera o openapi.yaml
	$(COMPOSE) run --rm web python manage.py spectacular --file docs/openapi.yaml
