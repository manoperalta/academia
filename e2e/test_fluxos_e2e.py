"""Testes de ponta a ponta com navegador de verdade (Playwright).

Nao rodam sozinhos: o modulo se **pula** quando o Playwright nao esta instalado ou quando faltam as
credenciais. Para rodar:

    pip install pytest-playwright && playwright install chromium
    export E2E_URL_BASE=http://localhost:8000 E2E_USUARIO=... E2E_SENHA=...
    pytest e2e

O alvo e uma instancia de desenvolvimento com dados de demonstracao — nada aqui toca producao.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright nao instalado neste ambiente")

BASE = os.environ.get("E2E_URL_BASE", "http://localhost:8000")
USUARIO = os.environ.get("E2E_USUARIO", "")
SENHA = os.environ.get("E2E_SENHA", "")

pytestmark = pytest.mark.skipif(
    not (USUARIO and SENHA),
    reason="defina E2E_USUARIO e E2E_SENHA para rodar os testes de ponta a ponta",
)


@pytest.fixture
def pagina(navegador_do_playwright):
    return navegador_do_playwright


@pytest.fixture
def navegador_do_playwright():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch()
        contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
        yield contexto.new_page()
        contexto.close()
        navegador.close()


def entrar(pagina):
    """Login pelo portao real do sistema (nao por cookie forjado)."""
    pagina.goto(f"{BASE}/accounts/login/", wait_until="domcontentloaded")
    pagina.fill("input[name='username']", USUARIO)
    pagina.fill("input[name='password']", SENHA)
    pagina.click("button[type='submit']")
    pagina.wait_for_load_state("networkidle")


def test_login_leva_ao_painel(pagina):
    entrar(pagina)
    assert "login" not in pagina.url.lower()
    assert pagina.locator("header").first.is_visible()


def test_busca_global_acha_o_aluno(pagina):
    entrar(pagina)
    pagina.goto(f"{BASE}/gestao/busca/?q=demo", wait_until="domcontentloaded")
    assert "resultado" in pagina.content().lower()


def test_tela_de_midia_abre_e_mostra_a_lista(pagina):
    entrar(pagina)
    pagina.goto(f"{BASE}/gestao/midia/", wait_until="domcontentloaded")
    assert pagina.locator("h2").first.is_visible()
    assert pagina.locator("table").count() >= 1


def test_balcao_do_pdv_abre(pagina):
    entrar(pagina)
    pagina.goto(f"{BASE}/gestao/pdv/balcao/", wait_until="domcontentloaded")
    assert pagina.locator("form").count() >= 1


def test_fila_de_retencao_abre(pagina):
    entrar(pagina)
    pagina.goto(f"{BASE}/gestao/retencao/", wait_until="domcontentloaded")
    assert "reten" in pagina.content().lower()
