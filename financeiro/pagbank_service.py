import requests
import json
from datetime import datetime, timedelta
from django.conf import settings
from .models import GatewayConfig

class PagBankService:
    def __init__(self):
        self.config = GatewayConfig.objects.first()
        if not self.config or not self.config.ativo:
            raise Exception("Gateway PagBank não configurado ou inativo.")
        
        self.base_url = "https://sandbox.api.pagseguro.com" if self.config.ambiente == 'sandbox' else "https://api.pagseguro.com"
        self.headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Content-Type": "application/json",
            "x-api-version": "4.0"
        }

    def criar_pedido(self, pagamento, usuario):
        """
        Cria um pedido no PagBank para o pagamento informado.
        """
        # Formata o valor para centavos (inteiro)
        valor_centavos = int(pagamento.valor_pago * 100)
        
        # Dados do cliente
        # Tenta pegar telefone e CPF do usuário se existirem, senão usa dados fictícios para teste (sandbox)
        # Em produção, esses dados devem ser obrigatórios e validados
        telefone_numero = "999999999"
        telefone_ddd = "11"
        cpf = "12345678909" # CPF de teste
        
        # Se o usuário tiver perfil com esses dados, use-os
        # Exemplo: if hasattr(usuario, 'perfil'): ...
        
        payload = {
            "reference_id": f"pag-{pagamento.id}",
            "customer": {
                "name": usuario.get_full_name() or usuario.username,
                "email": usuario.email,
                "tax_id": cpf,
                "phones": [
                    {
                        "country": "55",
                        "area": telefone_ddd,
                        "number": telefone_numero,
                        "type": "MOBILE"
                    }
                ]
            },
            "items": [
                {
                    "reference_id": f"plano-{pagamento.plano.id}",
                    "name": pagamento.plano.nome,
                    "quantity": 1,
                    "unit_amount": valor_centavos
                }
            ],
            "notification_urls": [
                self.config.url_webhook
            ] if self.config.url_webhook else []
        }

        # Adiciona QR Code Pix como opção padrão
        payload["qr_codes"] = [
            {
                "amount": {
                    "value": valor_centavos
                },
                "expiration_date": (datetime.now() + timedelta(days=1)).isoformat()
            }
        ]

        try:
            response = requests.post(f"{self.base_url}/orders", json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Erro ao comunicar com PagBank: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_msg += f" - Detalhes: {e.response.text}"
                except:
                    pass
            raise Exception(error_msg)

    def consultar_pedido(self, order_id):
        try:
            response = requests.get(f"{self.base_url}/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro ao consultar pedido PagBank: {str(e)}")
