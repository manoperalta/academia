"""Catalogo das integracoes de terceiros: quem entra, o que ele entrega e como testar.

Fonte unica da verdade da tela de integracoes. Cada provedor declara os campos que o
terceiro fornece (chave da API, token, usuario, certificado, codigo do contrato...) e a
tela monta o formulario a partir daqui: **ao selecionar o provedor aparecem exatamente os
campos daquele provedor**, em vez de um formulario unico com campo que nao serve para nada.

Regra de ouro: campo de segredo (``tipo == "senha"``) nunca volta para a tela; para trocar,
o operador digita de novo. Sem valor novo, o valor atual e mantido.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Tipos de campo aceitos na tela.
TEXTO = "texto"
SENHA = "senha"
URL = "url"
INTEIRO = "inteiro"
BOOLEANO = "booleano"
SELECAO = "selecao"
ARQUIVO = "arquivo"

#: Categorias usadas para agrupar os provedores na tela.
PAGAMENTO = "Pagamento e Pix"
FISCAL = "Fiscal"
BEM_ESTAR = "Bem-estar e parceiros"
CERTIFICADO = "Certificado digital"
ACESSO = "Controle de acesso"
COMUNICACAO = "Comunicacao"


@dataclass(frozen=True)
class Campo:
    """Um valor que o terceiro fornece."""

    nome: str
    rotulo: str
    tipo: str = TEXTO
    obrigatorio: bool = True
    ajuda: str = ""
    opcoes: tuple[tuple[str, str], ...] = ()
    exemplo: str = ""

    @property
    def sensivel(self) -> bool:
        return self.tipo == SENHA

    @property
    def de_arquivo(self) -> bool:
        return self.tipo == ARQUIVO


@dataclass(frozen=True)
class Integracao:
    """Um provedor de terceiro e o que ele exige para funcionar."""

    chave: str
    nome: str
    categoria: str
    resumo: str
    campos: tuple[Campo, ...]
    #: Modelo do sistema que recebe os valores (espelho), quando existir.
    espelho: str = ""
    #: Como o sistema se comporta hoje, sem chave real (transparencia na tela).
    situacao_atual: str = ""
    docs: str = ""
    aviso: str = ""
    campos_extra: dict = field(default_factory=dict)


ASAAS = Integracao(
    chave="asaas",
    nome="Asaas (pagamentos e Pix)",
    categoria=PAGAMENTO,
    resumo="Cobranca recorrente da mensalidade, Pix com QR e baixa por webhook.",
    espelho="financeiro.GatewayConfig",
    situacao_atual=(
        "Sem chave cadastrada o gateway roda em modo simulado (nada e cobrado de verdade)."
    ),
    docs="https://docs.asaas.com/",
    campos=(
        Campo(
            "chave_api",
            "Chave da API",
            SENHA,
            ajuda="Chave gerada no painel do Asaas (Integracoes > Chaves de API).",
            exemplo="$aact_...",
        ),
        Campo(
            "ambiente",
            "Ambiente",
            SELECAO,
            opcoes=(("sandbox", "Sandbox (testes)"), ("producao", "Producao")),
            ajuda="Comece no sandbox e troque para producao depois de validar.",
        ),
        Campo(
            "url_base",
            "URL base da API",
            URL,
            obrigatorio=False,
            ajuda="Deixe vazio para usar a URL oficial do ambiente.",
            exemplo="https://api-sandbox.asaas.com/v3",
        ),
        Campo(
            "segredo_do_webhook",
            "Segredo do webhook",
            SENHA,
            obrigatorio=False,
            ajuda="Token que o Asaas envia no cabecalho; usado para conferir a baixa.",
        ),
        Campo("chave_pix", "Chave Pix do recebedor", obrigatorio=False),
        Campo(
            "tipo_de_chave_pix",
            "Tipo da chave Pix",
            SELECAO,
            obrigatorio=False,
            opcoes=(
                ("cnpj", "CNPJ"),
                ("cpf", "CPF"),
                ("email", "E-mail"),
                ("telefone", "Telefone"),
                ("aleatoria", "Chave aleatoria"),
            ),
        ),
        Campo("nome_do_recebedor", "Nome do recebedor", obrigatorio=False),
        Campo("cidade_do_recebedor", "Cidade do recebedor", obrigatorio=False),
    ),
)

NFSE = Integracao(
    chave="nfse",
    nome="NFS-e (nota de servico)",
    categoria=FISCAL,
    resumo="Emissao da nota de servico das mensalidades e cancelamento com motivo.",
    espelho="fiscal.ConfiguracaoFiscal",
    situacao_atual="Sem token do provedor a nota sai como minuta, sem envio ao municipio.",
    campos=(
        Campo(
            "provedor",
            "Provedor",
            SELECAO,
            obrigatorio=False,
            opcoes=(
                ("padrao", "Padrao nacional (gov.br)"),
                ("ginfes", "Ginfes"),
                ("issnet", "ISSNet"),
                ("outro", "Outro"),
            ),
        ),
        Campo(
            "ambiente",
            "Ambiente",
            SELECAO,
            opcoes=(("homologacao", "Homologacao"), ("producao", "Producao")),
        ),
        Campo("token", "Token do provedor", SENHA, obrigatorio=False),
        Campo("inscricao_municipal", "Inscricao municipal", obrigatorio=False),
        Campo("municipio", "Municipio", obrigatorio=False),
        Campo(
            "codigo_do_servico",
            "Codigo do servico",
            obrigatorio=False,
            ajuda="Codigo da lista de servicos usado na nota (ex.: 6.01).",
        ),
        Campo("aliquota_iss", "Aliquota do ISS (%)", obrigatorio=False, exemplo="5.00"),
        Campo("serie", "Serie do RPS", obrigatorio=False),
        Campo(
            "emitir_automaticamente",
            "Emitir automaticamente ao receber",
            BOOLEANO,
            obrigatorio=False,
        ),
    ),
)

WELLHUB = Integracao(
    chave="wellhub",
    nome="Wellhub (bem-estar corporativo)",
    categoria=BEM_ESTAR,
    resumo="Alunos que chegam pelo beneficio corporativo e a conciliacao do repasse.",
    situacao_atual=(
        "A Wellhub nao liberou API para este contrato: o caminho hoje e a importacao do "
        "extrato mensal em Parceiros e conciliacao."
    ),
    campos=(
        Campo(
            "modo",
            "Modo de integracao",
            SELECAO,
            opcoes=(
                ("importacao", "Importacao do extrato (disponivel hoje)"),
                ("api", "API direta (quando liberada)"),
            ),
            ajuda="A importacao do extrato funciona sem credencial.",
        ),
        Campo("client_id", "Client ID", obrigatorio=False),
        Campo("client_secret", "Client secret", SENHA, obrigatorio=False),
        Campo("codigo_do_contrato", "Codigo do contrato", obrigatorio=False),
        Campo("url_base", "URL base da API", URL, obrigatorio=False),
        Campo(
            "ambiente",
            "Ambiente",
            SELECAO,
            obrigatorio=False,
            opcoes=(("sandbox", "Sandbox"), ("producao", "Producao")),
        ),
    ),
)

CERTIFICADO = Integracao(
    chave="certificado_icp",
    nome="Certificado digital A1 (ICP-Brasil)",
    categoria=CERTIFICADO,
    resumo="Certificado e-CNPJ usado para assinar a NFS-e e assinar contratos.",
    situacao_atual="Sem certificado o contrato sai como minuta e a NFS-e nao e assinada.",
    campos=(
        Campo(
            "arquivo",
            "Arquivo do certificado (.pfx)",
            ARQUIVO,
            ajuda="Enviado pela autoridade certificadora. Guarde o original em local seguro.",
        ),
        Campo("senha_do_certificado", "Senha do certificado", SENHA),
        Campo("cnpj", "CNPJ do titular", exemplo="00.000.000/0000-00"),
        Campo("titular", "Titular", obrigatorio=False),
        Campo("validade", "Vale ate", obrigatorio=False, ajuda="Data impressa no certificado."),
    ),
)

CATRACA = Integracao(
    chave="catraca",
    nome="Catraca / controle de acesso",
    categoria=ACESSO,
    resumo="Leitor da porta que libera a entrada do aluno e devolve o registro de acesso.",
    situacao_atual=(
        "O endpoint do equipamento ja existe; sem equipamento cadastrado a liberacao pode "
        "ser testada pelo painel."
    ),
    aviso=(
        "O token abaixo e o mesmo que precisa ser gravado no equipamento: use o botao "
        "Gerar token para criar um novo e cole no cadastro do leitor."
    ),
    campos=(
        Campo(
            "modelo",
            "Modelo do equipamento",
            SELECAO,
            opcoes=(
                ("control_id", "Control iD"),
                ("henry", "Henry"),
                ("topdata", "Topdata"),
                ("outro", "Outro"),
            ),
        ),
        Campo(
            "identificador_do_equipamento",
            "Identificador do equipamento",
            ajuda="Codigo unico do leitor; o equipamento envia no cabecalho X-Dispositivo.",
        ),
        Campo(
            "token",
            "Token de integracao",
            SENHA,
            ajuda="Criado aqui e gravado no equipamento. Use Gerar token para criar um novo.",
        ),
        Campo("host", "IP ou host do equipamento", obrigatorio=False, exemplo="192.168.88.50"),
        Campo("porta", "Porta", INTEIRO, obrigatorio=False, exemplo="80"),
        Campo("usuario", "Usuario do equipamento", obrigatorio=False),
        Campo("senha_do_equipamento", "Senha do equipamento", SENHA, obrigatorio=False),
    ),
)

WHATSAPP = Integracao(
    chave="whatsapp",
    nome="WhatsApp (mensagens da academia)",
    categoria=COMUNICACAO,
    resumo="Aviso de vencimento, confirmacao de agendamento e comunicados.",
    espelho="notificacoes.ConfiguracaoWhatsapp",
    situacao_atual="Sem provedor configurado as mensagens ficam registradas, mas nao saem.",
    campos=(
        Campo(
            "provedor",
            "Provedor",
            SELECAO,
            opcoes=(
                ("evolution", "Evolution API (servidor proprio)"),
                ("meta", "Meta Cloud API"),
                ("zapi", "Z-API"),
            ),
        ),
        Campo("url_base", "URL base", URL),
        Campo("chave_api", "Chave da API", SENHA),
        Campo("instancia", "Instancia", obrigatorio=False),
        Campo("numero_remetente", "Numero remetente (Phone Number ID)", obrigatorio=False, exemplo="5551999999999"),
        Campo("conta_comercial", "Conta comercial (Business Account ID)", obrigatorio=False),
        Campo("segredo_do_webhook", "Segredo do webhook", SENHA, obrigatorio=False),
    ),
)

SMTP = Integracao(
    chave="smtp",
    nome="E-mail (SMTP)",
    categoria=COMUNICACAO,
    resumo="Boas-vindas, recuperacao de senha e recibos por e-mail.",
    espelho="notificacoes.ConfiguracaoEmail",
    situacao_atual="Sem SMTP o sistema apenas registra o e-mail que enviaria.",
    campos=(
        Campo("host", "Servidor SMTP", exemplo="smtp.seudominio.com.br"),
        Campo("porta", "Porta", INTEIRO, exemplo="587"),
        Campo("usuario", "Usuario", obrigatorio=False),
        Campo("senha", "Senha", SENHA, obrigatorio=False),
        Campo(
            "usar_tls",
            "Usar TLS",
            BOOLEANO,
            obrigatorio=False,
            ajuda="Ligado por padrao nos servidores atuais (porta 587).",
        ),
        Campo("remetente_nome", "Nome do remetente", obrigatorio=False, exemplo="Academia System"),
        Campo("remetente_email", "E-mail do remetente", obrigatorio=False, exemplo="academia@seudominio.com.br"),
    ),
)

CATALOGO: dict[str, Integracao] = {
    integracao.chave: integracao
    for integracao in (ASAAS, NFSE, WELLHUB, CERTIFICADO, CATRACA, WHATSAPP, SMTP)
}

CHAVES = tuple(CATALOGO)


def por_categoria() -> dict[str, list[Integracao]]:
    """Provedores agrupados por categoria, na ordem em que a tela mostra."""
    grupos: dict[str, list[Integracao]] = {}
    for integracao in CATALOGO.values():
        grupos.setdefault(integracao.categoria, []).append(integracao)
    return grupos


def obter(chave: str) -> Integracao | None:
    return CATALOGO.get((chave or "").strip().lower())


def campos_obrigatorios(chave: str) -> tuple[Campo, ...]:
    integracao = obter(chave)
    if integracao is None:
        return ()
    return tuple(campo for campo in integracao.campos if campo.obrigatorio)


def campos_sensiveis(chave: str) -> tuple[str, ...]:
    integracao = obter(chave)
    if integracao is None:
        return ()
    return tuple(campo.nome for campo in integracao.campos if campo.sensivel)
