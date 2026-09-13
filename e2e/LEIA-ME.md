# Testes de ponta a ponta (Playwright)

Estes testes abrem um navegador de verdade e percorrem o painel. Ficam fora do caminho da suite
padrao: o modulo se pula quando o Playwright nao esta instalado ou quando faltam credenciais.

## Como rodar

```bash
pip install pytest-playwright
playwright install chromium

export E2E_URL_BASE=http://localhost:8000
export E2E_USUARIO=<usuario do painel>
export E2E_SENHA=<senha>

pytest e2e -v
```

Use uma instancia de **desenvolvimento** com dados de demonstracao. Nada aqui deve apontar para
producao: os testes navegam e clicam como um usuario real.
