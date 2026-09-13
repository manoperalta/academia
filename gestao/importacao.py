"""Importacao de alunos e professores por CSV (RF-PLT-034).

Fluxo em dois tempos: ``analisar`` (dry-run, nao escreve nada) e ``aplicar`` (confirmado
pelo usuario). O relatorio e por linha, com o motivo do erro, para o operador conferir a
planilha dele sem adivinhacao.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

LIMITE_LINHAS = 5000

CABECALHOS = {
    "alunos": {
        "nome": {"nome", "aluno", "nome do aluno", "nome completo"},
        "email": {"email", "e mail", "email user", "email do aluno"},
        "telefone": {"telefone", "celular", "whatsapp", "fone", "telefone user"},
        "status": {"status", "situacao", "status user"},
        "cpf": {"cpf", "cpf cnpj", "documento", "cpf cnpj user"},
        "nascimento": {
            "nascimento",
            "data de nascimento",
            "data nasc",
            "aniversario",
            "data nascimento",
        },
    },
    "professores": {
        "nome": {"nome", "professor", "nome do professor"},
        "email": {"email", "e mail", "email prof"},
        "telefone": {"telefone", "celular", "whatsapp", "fone", "telefone prof"},
        "status": {"status", "situacao", "status prof"},
        "cpf": {"cpf", "cpf cnpj", "documento", "cpf cnpj prof"},
        "nascimento": {"nascimento", "data de nascimento", "data nasc prof"},
    },
}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def _chave(texto: str) -> str:
    return _sem_acento(texto).replace(",", " ").replace("_", " ").strip()


@dataclass
class Linha:
    numero: int
    dados: dict
    acao: str = "criar"  # criar | atualizar | ignorar | erro
    motivos: list = field(default_factory=list)


@dataclass
class Resultado:
    tipo: str
    linhas: list = field(default_factory=list)
    colunas: dict = field(default_factory=dict)
    erro_geral: str = ""
    limite: int | None = None
    uso: int = 0
    campos: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.linhas)

    @property
    def a_criar(self):
        return [linha for linha in self.linhas if linha.acao == "criar"]

    @property
    def a_atualizar(self):
        return [linha for linha in self.linhas if linha.acao == "atualizar"]

    @property
    def ignoradas(self):
        return [linha for linha in self.linhas if linha.acao == "ignorar"]

    @property
    def com_erro(self):
        return [linha for linha in self.linhas if linha.acao == "erro"]

    @property
    def disponivel(self) -> int | None:
        if self.limite is None:
            return None
        return max(self.limite - self.uso, 0)

    @property
    def excede(self) -> bool:
        disponivel = self.disponivel
        if disponivel is None:
            return False
        return len(self.a_criar) + len(self.a_atualizar) > disponivel


def decodificar(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin-1", errors="replace")


def detectar_delimitador(texto: str) -> str:
    primeira = next((linha for linha in texto.splitlines() if linha.strip()), "")
    return ";" if primeira.count(";") >= primeira.count(",") else ","


def _data(valor: str) -> date | None:
    if not valor:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            continue
    return None


def _status(valor: str, padrao: str = "Ativo") -> str:
    if not valor:
        return padrao
    return "Inativo" if _chave(valor).startswith("i") or _chave(valor) == "0" else "Ativo"


def analisar(conteudo: bytes, tipo: str, rede, atualizar_existentes: bool = False) -> Resultado:
    """Le a planilha e devolve o que aconteceria — sem gravar nada."""
    from professores.models import Professor
    from usuarios.models import Usuario

    resultado = Resultado(tipo=tipo)
    if tipo not in CABECALHOS:
        resultado.erro_geral = "Tipo de importacao desconhecido."
        return resultado

    texto = decodificar(conteudo)
    if not texto.strip():
        resultado.erro_geral = "O arquivo esta vazio."
        return resultado

    leitor = list(csv.DictReader(io.StringIO(texto), delimiter=detectar_delimitador(texto)))
    if not leitor:
        resultado.erro_geral = (
            "Nao encontrei linhas de dados (a primeira linha deve ter os titulos)."
        )
        return resultado
    if len(leitor) > LIMITE_LINHAS:
        resultado.erro_geral = f"Planilha muito grande ({len(leitor)} linhas). Divida em partes."
        return resultado

    mapa = {}
    cabecalhos = list(leitor[0].keys())
    for campo, sinonimos in CABECALHOS[tipo].items():
        for cabecalho in cabecalhos:
            if cabecalho is None:
                continue
            if _chave(cabecalho) in sinonimos:
                mapa[campo] = cabecalho
                break
    resultado.colunas = mapa
    if "nome" not in mapa:
        resultado.erro_geral = (
            'Nao encontrei a coluna de nome. A primeira linha precisa ter, no minimo, "nome".'
        )
        return resultado

    modelo = Usuario if tipo == "alunos" else Professor
    campo_email = "email_user" if tipo == "alunos" else "email_prof"
    campo_telefone = "telefone_user" if tipo == "alunos" else "telefone_prof"
    campo_cpf = "cpf_cnpj_user" if tipo == "alunos" else "cpf_cnpj_prof"
    campo_status = "status_user" if tipo == "alunos" else "status_prof"

    from plataforma.servicos import limites_efetivos, uso_do_tenant

    limites = limites_efetivos(rede)
    uso = uso_do_tenant(rede)
    resultado.limite = limites.get(tipo)
    resultado.uso = uso.get(tipo, 0)

    vistos: set[str] = set()
    for numero, bruto in enumerate(leitor, start=2):  # linha 1 = cabecalho
        dados = {}
        if mapa.get("nome"):
            dados["nome"] = (bruto.get(mapa["nome"]) or "").strip()
        if mapa.get("email"):
            dados["email"] = (bruto.get(mapa["email"]) or "").strip().lower()
        if mapa.get("telefone"):
            dados["telefone"] = (bruto.get(mapa["telefone"]) or "").strip()[:20]
        if mapa.get("cpf"):
            dados["cpf"] = (bruto.get(mapa["cpf"]) or "").strip()[:20]
        if mapa.get("status"):
            dados["status"] = _status(bruto.get(mapa["status"]) or "")
        else:
            dados["status"] = "Ativo"
        if mapa.get("nascimento"):
            dados["nascimento"] = _data(bruto.get(mapa["nascimento"]) or "")

        linha = Linha(numero=numero, dados=dados)
        if not dados.get("nome"):
            linha.acao, linha.motivos = "erro", ["sem nome"]
            resultado.linhas.append(linha)
            continue
        if dados.get("email") and ("@" not in dados["email"] or "." not in dados["email"]):
            linha.acao, linha.motivos = "erro", [f"e-mail invalido: {dados['email']}"]
            resultado.linhas.append(linha)
            continue
        chave = dados.get("email") or dados["nome"].lower()
        if chave in vistos:
            linha.acao, linha.motivos = "erro", ["duplicado no proprio arquivo"]
            resultado.linhas.append(linha)
            continue
        vistos.add(chave)

        existente = None
        if dados.get("email"):
            existente = modelo.todos.filter(rede=rede, **{campo_email: dados["email"]}).first()
        if existente is None and dados.get("cpf"):
            existente = modelo.todos.filter(rede=rede, **{campo_cpf: dados["cpf"]}).first()
        if existente is not None:
            if atualizar_existentes:
                linha.acao, linha.dados["pk"] = "atualizar", existente.pk
            else:
                linha.acao, linha.motivos = "ignorar", ["ja existe nesta academia"]
        resultado.linhas.append(linha)

    # aplica o teto do pacote na ordem do arquivo
    disponivel = resultado.disponivel
    if disponivel is not None:
        restantes = disponivel
        for linha in resultado.linhas:
            if linha.acao in {"criar", "atualizar"}:
                if restantes <= 0:
                    linha.acao = "erro"
                    linha.motivos = [f"limite do pacote atingido ({resultado.limite} {tipo})"]
                else:
                    restantes -= 1

    # campos auxiliares usados ao gravar
    resultado.campos = {
        "email": campo_email,
        "telefone": campo_telefone,
        "cpf": campo_cpf,
        "status": campo_status,
    }
    return resultado


def aplicar(resultado: Resultado, rede) -> dict:
    """Grava o que foi confirmado. Cada linha vira um registro; erros sao so informados."""
    from api.auditoria import registrar
    from professores.models import Professor
    from usuarios.models import Usuario

    modelo = Usuario if resultado.tipo == "alunos" else Professor
    campos = resultado.campos or {
        "email": "email_user" if resultado.tipo == "alunos" else "email_prof",
        "telefone": "telefone_user" if resultado.tipo == "alunos" else "telefone_prof",
        "cpf": "cpf_cnpj_user" if resultado.tipo == "alunos" else "cpf_cnpj_prof",
        "status": "status_user" if resultado.tipo == "alunos" else "status_prof",
    }
    resumo = {
        "criados": 0,
        "atualizados": 0,
        "ignorados": len(resultado.ignoradas),
        "erros": len(resultado.com_erro),
    }
    for linha in resultado.linhas:
        dados = linha.dados
        valores = {campos["status"]: dados.get("status", "Ativo")}
        if dados.get("email"):
            valores[campos["email"]] = dados["email"]
        if dados.get("telefone"):
            valores[campos["telefone"]] = dados["telefone"]
        if dados.get("cpf"):
            valores[campos["cpf"]] = dados["cpf"]
        if linha.acao == "criar":
            nascimento = {
                "data_nasc" if resultado.tipo == "alunos" else "data_nasc_prof": dados.get(
                    "nascimento"
                )
            }
            modelo.todos.create(
                rede=rede,
                nome=dados["nome"],
                **{k: v for k, v in nascimento.items() if v},
                **valores,
            )
            resumo["criados"] += 1
        elif linha.acao == "atualizar" and dados.get("pk"):
            modelo.todos.filter(pk=dados["pk"]).update(nome=dados["nome"], **valores)
            resumo["atualizados"] += 1
    registrar(
        "importar",
        resultado.tipo,
        descricao=(
            f"Importacao CSV: {resumo['criados']} criados, {resumo['atualizados']} "
            f"atualizados, {resumo['ignorados']} ignorados, {resumo['erros']} com erro"
        ),
    )
    return resumo


def _campos_do_modelo(modelo, desejados):
    nomes = {campo.name for campo in modelo._meta.get_fields()}
    return [nome for nome in desejados if nome in nomes]


#: cabecalho aceito -> campo do modelo (por tipo de cadastro)
MAPA_MULTIUNIDADE = {
    "alunos": {
        "nome": "nome",
        "email": "email_user",
        "telefone": "telefone_user",
        "cpf": "cpf_cnpj_user",
        "nascimento": "data_nasc",
        "status": "status_user",
        "endereco": "endereco_user",
        "numero": "numero_end_user",
        "bairro": "bairro_user",
        "cep": "cep_user",
    },
    "professores": {
        "nome": "nome",
        "email": "email_prof",
        "telefone": "telefone_prof",
        "cpf": "cpf_cnpj_prof",
        "nascimento": "data_nasc_prof",
        "status": "status_prof",
    },
}
SINONIMOS_MULTIUNIDADE = {
    "email": {"email", "e-mail", "email_user", "email_prof"},
    "telefone": {"telefone", "celular", "whatsapp", "fone"},
    "cpf": {"cpf", "cpf_cnpj", "documento"},
    "nascimento": {"nascimento", "data_de_nascimento", "data_nasc", "aniversario"},
    "status": {"status", "situacao", "ativo"},
    "endereco": {"endereco", "rua", "logradouro"},
    "numero": {"numero", "num", "n"},
    "bairro": {"bairro"},
    "cep": {"cep"},
    "nome": {"nome", "nome_completo", "aluno", "professor"},
    "unidade": {"unidade", "unidade_nome", "filial", "codigo_da_unidade"},
}


def _linha_normalizada(linha: dict) -> dict:
    return {_chave(chave or ""): (valor or "").strip() for chave, valor in linha.items()}


def _valor_por_sinonimo(valores: dict, campo: str) -> str:
    for apelido in SINONIMOS_MULTIUNIDADE.get(campo, {campo}):
        if valores.get(apelido):
            return valores[apelido]
    return ""


def analisar_aplicar_multiunidade(
    conteudo: bytes,
    rede,
    tipo: str = "alunos",
    atualizar_existentes: bool = False,
    dry_run: bool = False,
) -> dict:
    """Importacao com coluna ``unidade`` e relatorio de conferencia por unidade (RF-RED-023).

    Aceita o nome ou o codigo da unidade em cada linha; o relatorio agrupa o resultado
    por unidade, para o cliente conferir antes de considerar a migracao concluida.
    """
    from core.models import Unidade
    from usuarios.models import Usuario

    texto = decodificar(conteudo)
    delimitador = detectar_delimitador(texto)
    linhas = [
        _linha_normalizada(linha)
        for linha in csv.DictReader(io.StringIO(texto), delimiter=delimitador)
        if any((valor or "").strip() for valor in linha.values())
    ]
    if not linhas:
        return {"ok": False, "mensagem": "Arquivo vazio ou sem linhas de dados.", "por_unidade": {}}

    if not _valor_por_sinonimo(linhas[0], "unidade") and "unidade" not in linhas[0]:
        return {
            "ok": False,
            "por_unidade": {},
            "mensagem": "Para importar em varias unidades, inclua a coluna 'unidade' "
            "(nome ou codigo da unidade).",
        }

    modelo = Usuario if tipo == "alunos" else _modelo_de_professores()
    mapa = MAPA_MULTIUNIDADE.get(tipo, MAPA_MULTIUNIDADE["alunos"])
    campos_validos = set(_campos_do_modelo(modelo, list(mapa.values())))
    unidades = {
        unidade.nome.strip().lower(): unidade for unidade in Unidade.objects.filter(rede=rede)
    }
    unidades.update(
        {
            (unidade.codigo or "").strip().lower(): unidade
            for unidade in Unidade.objects.filter(rede=rede)
            if unidade.codigo
        }
    )

    por_unidade: dict[str, dict] = {}
    criados = 0
    for numero, valores in enumerate(linhas, start=2):
        rotulo = _valor_por_sinonimo(valores, "unidade")
        relatorio = por_unidade.setdefault(rotulo or "(sem unidade)", {"criados": 0, "erros": []})
        unidade = unidades.get(rotulo.lower())
        if unidade is None:
            relatorio["erros"].append(f"linha {numero}: unidade {rotulo!r} nao encontrada na rede")
            continue

        dados: dict = {}
        for campo in mapa:
            valor = _valor_por_sinonimo(valores, campo)
            if not valor:
                continue
            if campo == "nascimento":
                valor = _data(valor)
                if valor is None:
                    relatorio["erros"].append(f"linha {numero}: data de nascimento invalida")
                    continue
            if campo == "status":
                valor = _status(valor, "Ativo")
            dados[campo] = valor

        if not dados.get("nome"):
            relatorio["erros"].append(f"linha {numero}: sem nome")
            continue
        dados = {campo: valor for campo, valor in dados.items() if campo in campos_validos}
        if dry_run:
            relatorio["criados"] += 1
            criados += 1
            continue
        try:
            modelo.todos.create(rede=rede, unidade=unidade, **dados)
        except Exception as erro:
            relatorio["erros"].append(f"linha {numero}: {str(erro)[:160]}")
            continue
        relatorio["criados"] += 1
        criados += 1

    total_erros = sum(len(dados["erros"]) for dados in por_unidade.values())
    return {
        "ok": criados > 0,
        "tipo": tipo,
        "criados": criados,
        "atualizados": 0,
        "erros": total_erros,
        "por_unidade": por_unidade,
        "mensagem": f"{criados} registro(s) em {len(por_unidade)} unidade(s); "
        f"{total_erros} linha(s) com problema.",
    }


def _modelo_de_professores():
    from professores.models import Professor

    return Professor
