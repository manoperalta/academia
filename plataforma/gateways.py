"""Gateway de pagamento: Asaas (real) e modo simulado (sem credencial)."""

from __future__ import annotations

import logging

logger = logging.getLogger("plataforma")


class GatewayError(Exception):
    """Erro de comunicacao com o gateway (rede, credencial ou resposta invalida)."""


class GatewayBase:
    nome = "base"

    def criar_cobranca(self, fatura) -> dict:
        raise NotImplementedError

    def consultar(self, gateway_id: str) -> dict:
        raise NotImplementedError

    def cancelar(self, gateway_id: str) -> bool:
        raise NotImplementedError


class GatewaySimulado(GatewayBase):
    """Sem credencial configurada: devolve dados deterministicos (dev e testes)."""

    nome = "simulado"

    def criar_cobranca(self, fatura) -> dict:
        return {
            "id": f"sim-{fatura.numero}",
            "status": "PENDING",
            "forma": "pix",
            "link_pagamento": f"https://simulado.local/fatura/{fatura.numero}",
            "pix_copia_cola": f"00020126SIMULADO{fatura.numero}5204000053039865802BR",
            "pix_qr_code": "",
        }

    def consultar(self, gateway_id: str) -> dict:
        return {"id": gateway_id, "status": "PENDING"}

    def cancelar(self, gateway_id: str) -> bool:
        return True


class GatewayAsaas(GatewayBase):
    """Cliente da API do Asaas (Pix, boleto e cartao).

    Coloque a chave em ConfiguracaoPlataforma (painel da plataforma). Sem chave, o
    sistema opera no modo simulado — assim a cobranca roda em dev/teste sem dinheiro real.
    """

    nome = "asaas"
    BASES = {
        "sandbox": "https://api-sandbox.asaas.com/v3",
        "producao": "https://api.asaas.com/v3",
    }

    def __init__(
        self, api_key: str, ambiente: str = "sandbox", base_url: str = "", timeout: int = 20
    ):
        self.api_key = api_key
        self.base_url = (base_url or self.BASES.get(ambiente) or self.BASES["sandbox"]).rstrip("/")
        self.timeout = timeout

    def _chamar(self, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        try:
            import requests
        except ImportError as erro:  # pragma: no cover - requests ja esta nas dependencias
            raise GatewayError(f"biblioteca requests ausente: {erro}") from erro
        url = f"{self.base_url}{caminho}"
        try:
            resposta = requests.request(
                metodo,
                url,
                json=corpo,
                timeout=self.timeout,
                headers={
                    "access_token": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "SafeStack-Academia/1.0",
                },
            )
        except Exception as erro:
            raise GatewayError(f"falha de rede ao chamar {url}: {erro}") from erro
        if resposta.status_code >= 400:
            raise GatewayError(f"Asaas {resposta.status_code}: {resposta.text[:300]}")
        return resposta.json() if resposta.content else {}

    def _garantir_cliente(self, rede) -> str:
        busca = self._chamar("GET", f"/customers?externalReference={rede.slug}&limit=1")
        encontrados = busca.get("data") or []
        if encontrados:
            return encontrados[0]["id"]
        criado = self._chamar(
            "POST",
            "/customers",
            {
                "name": rede.nome,
                "cpfCnpj": "".join(filter(str.isdigit, rede.cnpj or "")) or None,
                "email": rede.email_responsavel or None,
                "externalReference": rede.slug,
            },
        )
        return criado["id"]

    def criar_cobranca(self, fatura) -> dict:
        corpo = {
            "customer": self._garantir_cliente(fatura.rede),
            "billingType": "PIX",
            "value": float(fatura.valor_final),
            "dueDate": fatura.vencimento.isoformat(),
            "description": f"Fatura {fatura.numero} - {fatura.rede.nome}",
            "externalReference": fatura.numero,
        }
        dados = self._chamar("POST", "/payments", corpo)
        qr = {}
        try:
            qr = self._chamar("GET", f"/payments/{dados['id']}/pixQrCode")
        except GatewayError as erro:
            logger.warning("Nao consegui obter o QR code da fatura %s: %s", fatura.numero, erro)
        return {
            "id": dados["id"],
            "status": dados.get("status", ""),
            "forma": "pix",
            "link_pagamento": dados.get("invoiceUrl", ""),
            "pix_copia_cola": qr.get("payload", ""),
            "pix_qr_code": qr.get("encodedImage", ""),
        }

    def consultar(self, gateway_id: str) -> dict:
        return self._chamar("GET", f"/payments/{gateway_id}")

    def cancelar(self, gateway_id: str) -> bool:
        self._chamar("DELETE", f"/payments/{gateway_id}")
        return True


def gateway_atual() -> GatewayBase:
    """Gateway conforme a configuracao da plataforma (simulado quando nao ha chave)."""
    from plataforma.models import ConfiguracaoPlataforma

    configuracao = ConfiguracaoPlataforma.obter()
    if configuracao.gateway_em_modo_simulado:
        return GatewaySimulado()
    return GatewayAsaas(
        configuracao.asaas_api_key, configuracao.asaas_ambiente, configuracao.asaas_base_url
    )
