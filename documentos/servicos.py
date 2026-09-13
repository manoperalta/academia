"""Documentos de negocio em PDF, montados a partir dos dados reais do sistema.

Cada funcao recebe objetos do proprio sistema e devolve ``bytes`` de um PDF pronto para
baixar ou imprimir. Nenhuma inventa dado: campo que nao existe no objeto simplesmente nao
aparece no documento.
"""

from __future__ import annotations

import hashlib
from datetime import date

from django.utils import timezone

from documentos.pdf import DocumentoPDF, como_texto, moeda, numero

RODAPE = "Documento gerado pelo SafeStack Academia"


def _identidade(rede) -> tuple[str, str]:
    """(nome, linha de identificacao) da rede, sem inventar CNPJ que nao existe."""
    nome = getattr(rede, "nome", "") or "Academia"
    documento = getattr(rede, "cnpj", "") or ""
    return nome, f"CNPJ {documento}" if documento else ""


def _unidade_linha(unidade) -> str:
    if unidade is None:
        return ""
    partes = [getattr(unidade, "nome", "") or ""]
    endereco = getattr(unidade, "endereco", "") or ""
    cidade = getattr(unidade, "cidade", "") or ""
    uf = getattr(unidade, "uf", "") or ""
    if endereco:
        partes.append(endereco)
    if cidade:
        partes.append(f"{cidade}/{uf}" if uf else cidade)
    ramal = getattr(unidade, "telefone", "") or ""
    if ramal:
        partes.append(f"tel. {ramal}")
    return " - ".join(parte for parte in partes if parte)


def _assinatura(documento: bytes) -> str:
    """Codigo curto de conferencia: permite checar se o PDF saiu do sistema sem alteracao."""
    return hashlib.sha256(documento).hexdigest()[:16]


def _cabecalho(rede, titulo: str, unidade=None, subtitulo: str = "") -> DocumentoPDF:
    nome, documento = _identidade(rede)
    partes = [nome]
    if documento:
        partes.append(documento)
    linha_unidade = _unidade_linha(unidade)
    if linha_unidade:
        partes.append(linha_unidade)
    return DocumentoPDF(
        titulo=titulo,
        subtitulo=subtitulo or " - ".join(partes),
        rodape=f"{nome} - {RODAPE}",
    )


def _aluno_do_usuario(usuario):
    """Perfil de aluno do login informado (o aluno e ``usuarios.Usuario``)."""
    from usuarios.models import Usuario

    return Usuario.todos.filter(user=usuario).select_related("rede", "unidade").first()


def _plano_do_aluno(usuario):
    """Pagamento mais recente do aluno, usado como matricula vigente."""
    from financeiro.models import Pagamento

    return (
        Pagamento.objects.filter(usuario=usuario)
        .select_related("plano", "unidade", "rede")
        .order_by("-data_pagamento", "-id")
        .first()
    )


def comprovante_de_matricula(usuario, emitido_em: date | None = None) -> bytes:
    """Comprovante de matricula: identifica o aluno, a unidade e a vigencia do plano."""
    aluno = _aluno_do_usuario(usuario)
    rede = getattr(aluno, "rede", None) or getattr(usuario, "rede", None)
    unidade = getattr(aluno, "unidade", None)
    pagamento = _plano_do_aluno(usuario)
    doc = _cabecalho(
        rede, "Comprovante de matricula", unidade, subtitulo="Comprovante de matricula do aluno"
    )
    doc.secao("Aluno")
    doc.par("Nome", getattr(aluno, "nome", "") or getattr(usuario, "username", ""))
    doc.par("Matricula", f"{usuario.pk:06d}")
    doc.par("Situacao", getattr(aluno, "status_user", "") or "")
    doc.par("Unidade", getattr(unidade, "nome", "") or "")
    doc.par("Codigo da unidade", getattr(unidade, "codigo", "") or "")
    doc.secao("Plano vigente")
    if pagamento is None:
        doc.texto("Nenhum pagamento registrado para este aluno.", cor=(0.4, 0.4, 0.4))
    else:
        plano = getattr(pagamento, "plano", None)
        doc.par("Plano", getattr(plano, "nome", "") or "")
        doc.par("Valor", moeda(getattr(pagamento, "valor_pago", 0)))
        doc.par(
            "Vigencia",
            f"{como_texto(getattr(pagamento, 'data_inicio', None))} a "
            f"{como_texto(getattr(pagamento, 'data_fim', None))}",
        )
        doc.par("Situacao do pagamento", getattr(pagamento, "status", "") or "")
    doc.secao("Observacoes")
    doc.texto(
        "Apresente este comprovante junto com um documento com foto para acessar a academia.",
        tamanho=9,
    )
    doc.texto("A matricula e pessoal e intransferivel.", tamanho=9)
    doc.espaco(10)
    doc.texto(
        f"Emitido em {como_texto(emitido_em or timezone.localdate())}.",
        tamanho=8.5,
        cor=(0.4, 0.4, 0.4),
    )
    return doc.salvar()


def recibo_de_pagamento(pagamento) -> bytes:
    """Recibo do pagamento, com o periodo coberto e codigo de conferencia."""
    rede = getattr(pagamento, "rede", None)
    unidade = getattr(pagamento, "unidade", None)
    usuario = getattr(pagamento, "usuario", None)
    aluno = _aluno_do_usuario(usuario) if usuario is not None else None
    doc = _cabecalho(rede, "Recibo de pagamento", unidade, subtitulo="Recibo de mensalidade")
    doc.secao("Pagador")
    doc.par("Nome", getattr(aluno, "nome", "") or getattr(usuario, "username", ""))
    doc.par("Matricula", f"{usuario.pk:06d}" if usuario else "")
    doc.secao("Pagamento")
    plano = getattr(pagamento, "plano", None)
    doc.tabela(
        [("Descricao", 3, "esquerda"), ("Valor", 1, "direita")],
        [[getattr(plano, "nome", "") or "Mensalidade", moeda(getattr(pagamento, "valor_pago", 0))]],
    )
    doc.par("Data do pagamento", como_texto(getattr(pagamento, "data_pagamento", None)))
    doc.par(
        "Periodo coberto",
        f"{como_texto(getattr(pagamento, 'data_inicio', None))} a "
        f"{como_texto(getattr(pagamento, 'data_fim', None))}",
    )
    doc.par("Situacao", getattr(pagamento, "status", "") or "")
    doc.par("Forma", getattr(pagamento, "forma_pagamento", "") or "")
    doc.secao("Total")
    doc.par("Total pago", moeda(getattr(pagamento, "valor_pago", 0)))
    doc.espaco(8)
    doc.texto(
        "Documento sem valor fiscal. O recibo fiscal e emitido pela unidade.",
        tamanho=8.5,
        cor=(0.4, 0.4, 0.4),
    )
    conteudo = doc.salvar()
    return conteudo


def demonstrativo_de_repasse(repasse) -> bytes:
    """Memoria de calculo do repasse/royalty, linha a linha, com conferencia pelo hash."""
    rede = getattr(repasse, "rede", None)
    unidade = getattr(repasse, "unidade", None)
    doc = _cabecalho(
        rede,
        "Demonstrativo de repasse",
        unidade,
        subtitulo="Royalty e fundo de marketing do periodo",
    )
    doc.par("Unidade", getattr(unidade, "nome", ""))
    doc.par(
        "Periodo",
        f"{como_texto(getattr(repasse, 'inicio', None))} a "
        f"{como_texto(getattr(repasse, 'fim', None))}",
    )
    doc.par("Situacao", getattr(repasse, "situacao", "") or "")
    doc.par("Vencimento", como_texto(getattr(repasse, "vencimento", None)))
    doc.secao("Memoria de calculo")
    base = getattr(repasse, "base_de_calculo", 0)
    linhas = [
        ["Receita bruta do periodo", moeda(getattr(repasse, "receita_bruta", 0)), "", ""],
        ["Exclusoes (taxas e estornos)", moeda(getattr(repasse, "exclusoes", 0)), "", ""],
        ["Receita liquida", moeda(getattr(repasse, "receita_liquida", 0)), "", ""],
        ["Base de calculo", moeda(base), "", ""],
        [
            "Royalty",
            moeda(base),
            numero(getattr(repasse, "percentual", 0), 3),
            moeda(getattr(repasse, "valor_do_royalty", 0)),
        ],
        [
            "Fundo de marketing",
            moeda(base),
            numero(getattr(repasse, "fundo_de_marketing", 0), 2),
            moeda(getattr(repasse, "valor_do_fundo", 0)),
        ],
    ]
    if getattr(repasse, "valor_fixo", 0):
        linhas.append(["Valor fixo da regra", "", "", moeda(repasse.valor_fixo)])
    if getattr(repasse, "piso_aplicado", False):
        linhas.append(["Piso minimo aplicado", "", "", moeda(repasse.valor_devido)])
    doc.tabela(
        [
            ("Linha", 3.2, "esquerda"),
            ("Base", 1.3, "direita"),
            ("%", 0.8, "direita"),
            ("Valor", 1.3, "direita"),
        ],
        linhas,
    )
    doc.par("Total devido", moeda(getattr(repasse, "valor_devido", 0)))
    doc.par("Total pago", moeda(getattr(repasse, "valor_pago", 0)))
    doc.secao("Conferencia")
    doc.par("Hash do calculo", getattr(repasse, "hash_do_calculo", "") or "nao calculado")
    doc.texto(
        "Recalcule a partir da receita e das regras da rede: o resultado tem de bater "
        "com o total acima e com o hash.",
        tamanho=9,
        cor=(0.35, 0.35, 0.35),
    )
    observacoes = getattr(repasse, "observacoes", "") or ""
    if observacoes:
        doc.espaco(6)
        doc.par("Observacoes", observacoes)
    return doc.salvar()


def extrato_de_comissao(apuracao) -> bytes:
    """Extrato de comissao do professor, com as linhas da apuracao e a situacao do pagamento."""
    rede = getattr(apuracao, "rede", None)
    unidade = getattr(apuracao, "unidade", None)
    professor = getattr(apuracao, "professor", None)
    doc = _cabecalho(rede, "Extrato de comissao", unidade, subtitulo="Remuneracao variavel")
    doc.par("Professor", getattr(professor, "nome", ""))
    doc.par(
        "Periodo",
        f"{como_texto(getattr(apuracao, 'inicio', None))} a "
        f"{como_texto(getattr(apuracao, 'fim', None))}",
    )
    doc.par("Situacao", getattr(apuracao, "situacao", "") or "")
    doc.secao("Memoria de calculo")
    linhas = []
    itens = list(apuracao.itens.all()) if hasattr(apuracao, "itens") else []
    for item in itens:
        linhas.append(
            [
                getattr(item, "descricao", ""),
                moeda(getattr(item, "base", 0)),
                numero(getattr(item, "percentual", 0), 3),
                moeda(getattr(item, "valor", 0)),
            ]
        )
    if not linhas:
        linhas.append(
            ["Valor apurado no periodo", "", "", moeda(getattr(apuracao, "valor_devido", 0))]
        )
    doc.tabela(
        [
            ("Linha", 3.2, "esquerda"),
            ("Base", 1.3, "direita"),
            ("%", 0.8, "direita"),
            ("Valor", 1.3, "direita"),
        ],
        linhas,
    )
    doc.par("Total devido", moeda(getattr(apuracao, "valor_devido", 0)))
    doc.par("Total pago", moeda(getattr(apuracao, "valor_pago", 0)))
    doc.par("Saldo", moeda(getattr(apuracao, "saldo", 0)))
    doc.par("Pago em", como_texto(getattr(apuracao, "pago_em", None)) or "-")
    doc.secao("Conferencia")
    doc.par("Hash do calculo", getattr(apuracao, "hash_do_calculo", "") or "nao calculado")
    return doc.salvar()


def carteirinha_do_aluno(usuario) -> bytes:
    """Carteirinha do aluno: identifica a rede e vale em qualquer unidade dela."""
    aluno = _aluno_do_usuario(usuario)
    rede = getattr(aluno, "rede", None)
    unidade = getattr(aluno, "unidade", None)
    pagamento = _plano_do_aluno(usuario)
    doc = _cabecalho(
        rede, "Carteirinha do aluno", unidade, subtitulo="Valida em qualquer unidade da rede"
    )
    doc.espaco(4)
    doc.moldura(150)
    doc.texto(getattr(rede, "nome", "") or "", tamanho=13, fonte="negrito", recuo=12)
    doc.espaco(2)
    doc.texto(
        getattr(aluno, "nome", "") or getattr(usuario, "username", ""),
        tamanho=15,
        fonte="negrito",
        recuo=12,
    )
    doc.par("Matricula", f"{usuario.pk:06d}", tamanho=10)
    doc.par("Unidade de origem", getattr(unidade, "nome", ""), tamanho=10)
    if pagamento is not None:
        doc.par("Valido ate", como_texto(getattr(pagamento, "data_fim", None)), tamanho=10)
    doc.par("Situacao", getattr(aluno, "status_user", "") or "", tamanho=10)
    doc.espaco(8)
    doc.texto(
        "Apresente esta carteirinha (impressa ou no celular) na entrada. Ela e valida em "
        "todas as unidades da rede e nao substitui documento com foto quando solicitado.",
        tamanho=8.5,
        cor=(0.35, 0.35, 0.35),
    )
    return doc.salvar()


def contrato_de_adesao(usuario, plano=None) -> bytes:
    """Contrato de adesao em modelo padrao, para revisao juridica antes de assinar."""
    aluno = _aluno_do_usuario(usuario)
    rede = getattr(aluno, "rede", None)
    unidade = getattr(aluno, "unidade", None)
    documento = getattr(rede, "cnpj", "") or ""
    nome_aluno = getattr(aluno, "nome", "") or getattr(usuario, "username", "")
    doc = _cabecalho(
        rede, "Contrato de adesao", unidade, subtitulo="Termo de prestacao de servicos"
    )
    doc.secao("Partes")
    doc.texto(
        f"CONTRATADA: {getattr(rede, 'nome', '')}" + (f", CNPJ {documento}" if documento else ""),
        tamanho=9.5,
    )
    doc.texto(f"CONTRATANTE: {nome_aluno}, matricula {usuario.pk:06d}", tamanho=9.5)
    doc.secao("Objeto")
    if plano is not None:
        doc.texto(
            f"Prestacao de servicos de atividade fisica no plano "
            f"{getattr(plano, 'nome', '')}, no valor de {moeda(getattr(plano, 'valor', 0))} "
            f"por periodo, na unidade {getattr(unidade, 'nome', '')}.",
            tamanho=9.5,
        )
    else:
        doc.texto(
            f"Prestacao de servicos de atividade fisica na unidade "
            f"{getattr(unidade, 'nome', '')}, conforme plano contratado.",
            tamanho=9.5,
        )
    doc.secao("Condicoes gerais")
    for clausula in (
        "O acesso as dependencias depende de mensalidade em dia e de atestacao de saude "
        "entregue na matricula.",
        "O plano e pessoal e intransferivel; a frequencia e registrada por check-in.",
        "O cancelamento segue a politica de cancelamento vigente na rede, informada na assinatura.",
        "Dados pessoais sao tratados conforme a LGPD, com finalidade de execucao do contrato; "
        "o titular pode pedir exportacao ou anonimizacao a qualquer momento.",
        "Este modelo e uma minuta: revise com apoio juridico antes de usar em producao.",
    ):
        doc.texto(f"- {clausula}", tamanho=9)
    doc.espaco(14)
    doc.linha(espessura=0.6, cor=(0.4, 0.4, 0.4), largura=220)
    doc.texto("Assinatura do contratante", tamanho=8.5, cor=(0.4, 0.4, 0.4))
    doc.espaco(8)
    doc.linha(espessura=0.6, cor=(0.4, 0.4, 0.4), largura=220)
    doc.texto("Assinatura da contratada", tamanho=8.5, cor=(0.4, 0.4, 0.4))
    return doc.salvar()
