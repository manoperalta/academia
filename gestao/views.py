"""Painel administrativo do tenant: telas dos 10 modulos do PRD (secao 7.2)."""
from __future__ import annotations

import csv
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage, get_connection
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from academia.models import Configuracao, IdentidadeVisual
from agendamento.models import Agendamento
from api.auditoria import registrar
from api.models import RegistroAuditoria
from aulas.models import Aulas
from core.models import ConviteEquipe, Unidade, VinculoUsuario
from core.papeis import Papel
from core.tenancy import unidades_do_usuario
from financeiro.models import Despesa, Pagamento, Plano
from gestao.emails import enviar_email
from gestao.forms import (
    criar_ou_vincular_usuario,
    AlunoForm, AulaForm, ConfiguracaoForm, ConviteForm, DespesaForm, EmailConfigForm,
    FichaSaudeForm, IdentidadeForm, NovaContaForm, PagamentoForm, PainelForm, PlanoForm,
    ProfessorForm, WhatsappConfigForm,
)
from gestao.mixins import EdicaoMixin, PainelMixin
from plataforma.mixins import ModuloDePacoteMixin
from plataforma.models import Fatura, ModuloPacote, Pacote
from plataforma.servicos import modulo_disponivel
from gestao.permissoes import Modulo, nivel, pode
from notificacoes.models import ConfiguracaoEmail, ConfiguracaoWhatsapp
from painel.models import Painel
from professores.models import Professor
from usuarios.models import FichaSaude, Usuario


def escopo_unidade(qs, request):
    """Restringe a consulta a unidade atual (incluindo registros sem unidade definida)."""
    unidade = getattr(request, "unidade", None)
    if unidade is None or not hasattr(qs.model, "unidade"):
        return qs
    return qs.filter(Q(unidade=unidade) | Q(unidade__isnull=True))


def da_rede(qs, request, campo="rede"):
    rede = getattr(request, "rede", None)
    if rede is None:
        return qs
    return qs.filter(**{campo: rede})


# ===================================================================== GENERICOS
class ListaPainel(PainelMixin, ListView):
    """Listagem padrao do painel: busca, paginacao e HTMX."""

    template_name = "gestao/lista.html"
    template_parcial = "gestao/_tabela.html"
    paginate_by = 25
    colunas: list[tuple[str, str]] = []
    campo_busca: tuple[str, ...] = ()
    url_novo: str | None = None
    url_editar: str | None = None
    url_detalhe: str | None = None
    url_arquivar: str | None = None
    texto_vazio = "Nenhum registro encontrado."
    mostrar_arquivados = True
    incluir_arquivados = False
    #: ordem deterministica da listagem (pagina sem ordem da resultados inconsistentes)
    ordenacao: tuple = ("pk",)
    url_extra: str | None = None
    rotulo_extra = ""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.model, "arquivado_em"):
            ver_arquivados = self.request.GET.get("arquivados") == "1"
            if not (ver_arquivados or getattr(self, "incluir_arquivados", False)):
                qs = qs.filter(arquivado_em__isnull=True)
        termo = self.request.GET.get("q", "").strip()
        if termo and self.campo_busca:
            condicao = Q()
            for campo in self.campo_busca:
                condicao |= Q(**{f"{campo}__icontains": termo})
            qs = qs.filter(condicao)
        qs = self.ajustar(escopo_unidade(qs, self.request))
        return qs if qs.ordered else qs.order_by(*self.ordenacao)

    def ajustar(self, qs):
        return qs

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return [self.template_parcial]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            colunas=self.colunas,
            url_novo=self.url_novo,
            url_editar=self.url_editar,
            url_detalhe=self.url_detalhe,
            url_arquivar=self.url_arquivar,
            url_extra=self.url_extra,
            rotulo_extra=self.rotulo_extra,
            termo=self.request.GET.get("q", ""),
            mostrar_arquivados=self.mostrar_arquivados,
            filtrando_arquivados=self.request.GET.get("arquivados") == "1",
            texto_vazio=self.texto_vazio,
        )
        return contexto


class CriarPainel(EdicaoMixin, CreateView):
    template_name = "gestao/formulario.html"
    entidade = ""
    url_sucesso = "gestao:visao_geral"
    acao_auditoria = "criar"
    #: recurso do pacote que este cadastro consome (bloqueia no teto, RF-TEN-040)
    recurso_de_limite = ""

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["url_voltar"] = reverse(self.url_sucesso)
        return contexto

    def get_success_url(self):
        return reverse(self.url_sucesso)

    def aviso_de_sucesso(self) -> str:
        return f"{self.object} cadastrado com sucesso."

    def form_valid(self, form):
        if self.recurso_de_limite:
            from plataforma.servicos import pode_cadastrar

            liberado, mensagem = pode_cadastrar(self.request.rede, self.recurso_de_limite)
            if not liberado:
                messages.error(self.request, mensagem)
                registrar(
                    "limite", self.entidade, descricao=f"Cadastro recusado pelo limite: {mensagem}",
                    request=self.request,
                )
                return redirect(self.request.path)
        resposta = super().form_valid(form)
        registrar(
            self.acao_auditoria,
            self.entidade,
            entidade_id=self.object.pk,
            descricao=f"{self.entidade} {self.object} via painel",
            request=self.request,
        )
        messages.success(self.request, self.aviso_de_sucesso())
        return resposta


class EditarPainel(EdicaoMixin, UpdateView):
    template_name = "gestao/formulario.html"
    entidade = ""
    url_sucesso = "gestao:visao_geral"
    acao_auditoria = "alterar"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["url_voltar"] = reverse(self.url_sucesso)
        return contexto

    def get_success_url(self):
        return reverse(self.url_sucesso)

    def form_valid(self, form):
        resposta = super().form_valid(form)
        registrar(
            self.acao_auditoria,
            self.entidade,
            entidade_id=self.object.pk,
            descricao=f"{self.entidade} {self.object} alterado via painel",
            request=self.request,
        )
        messages.success(self.request, f"{self.object} atualizado com sucesso.")
        return resposta


class ArquivarPainel(EdicaoMixin, View):
    """Arquiva (soft delete) ou restaura um registro. Sempre POST."""

    modelo = None
    entidade = ""
    url_voltar = "gestao:visao_geral"

    def post(self, request, pk):
        objeto = get_object_or_404(self.modelo.objects, pk=pk)
        if getattr(objeto, "arquivado_em", None) is None:
            objeto.arquivar()
            acao, verbo = "arquivar", "arquivado"
        else:
            objeto.restaurar()
            acao, verbo = "restaurar", "restaurado"
        registrar(
            acao, self.entidade, entidade_id=objeto.pk,
            descricao=f"{self.entidade} {objeto} {verbo} via painel", request=request,
        )
        messages.success(request, f"{objeto} {verbo}.")
        return redirect(self.url_voltar)


# ===================================================================== VISAO GERAL
CHAVE_IMPORTACAO = "importacao_csv"


class ImportarView(PainelMixin, TemplateView):
    """Importacao de alunos/professores por CSV, com conferencia antes de gravar."""

    template_name = "gestao/importar.html"
    modulo = Modulo.ALUNOS
    nivel_minimo = "editar"
    titulo = "Importar planilha"
    subtitulo = "Alunos e professores por CSV, com relatorio linha por linha"

    TIPOS = {"alunos": "Alunos", "professores": "Professores"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.setdefault("tipos", self.TIPOS)
        contexto.setdefault("tipo", self.request.GET.get("tipo", "alunos"))
        contexto.setdefault("atualizar_existentes", False)
        contexto.setdefault("linhas_previa", None)
        return contexto

    def post(self, request):
        from gestao.importacao import analisar

        acao = request.POST.get("acao", "analisar")
        tipo = request.POST.get("tipo", "alunos")
        atualizar = request.POST.get("atualizar_existentes") == "on"

        if acao == "confirmar":
            conteudo = request.session.get(CHAVE_IMPORTACAO, {}).get(tipo, "")
            if not conteudo:
                messages.error(request, "A planilha expirou. Envie o arquivo novamente.")
                return redirect("gestao:importar")
            resultado = analisar(conteudo.encode("utf-8"), tipo, request.rede, atualizar)
            from gestao.importacao import aplicar

            resumo = aplicar(resultado, request.rede)
            messages.success(
                request,
                f"Importacao concluida: {resumo['criados']} criados, "
                f"{resumo['atualizados']} atualizados, {resumo['ignorados']} ignorados e "
                f"{resumo['erros']} linhas com erro.",
            )
            registrar("importar", tipo, descricao=f"Importacao confirmada: {resumo}", request=request)
            request.session.pop(CHAVE_IMPORTACAO, None)
            return redirect(f"{reverse('gestao:importar')}?tipo={tipo}")

        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            messages.error(request, "Escolha um arquivo CSV.")
            return redirect(f"{reverse('gestao:importar')}?tipo={tipo}")
        conteudo = arquivo.read()
        resultado = analisar(conteudo, tipo, request.rede, atualizar)
        guardado = request.session.get(CHAVE_IMPORTACAO, {})
        guardado[tipo] = conteudo.decode("utf-8", errors="replace")
        request.session[CHAVE_IMPORTACAO] = guardado
        registrar("importar", tipo,
                  descricao=f"Planilha conferida: {resultado.total} linhas analisadas",
                  request=request)
        contexto = {
            **self.get_context_data(),
            "linhas_previa": resultado,
            "tipo": tipo,
            "atualizar_existentes": atualizar,
            "resultado": resultado,
        }
        return render(request, self.template_name, contexto)


class ImportarModeloView(PainelMixin, View):
    """Baixa o modelo de planilha (para o cliente preencher exatamente o que esperamos)."""

    modulo = Modulo.ALUNOS
    nivel_minimo = "editar"

    def get(self, request):
        tipo = request.GET.get("tipo", "alunos")
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = f'attachment; filename="modelo_{tipo}.csv"'
        resposta.write("\ufeff")
        escritor = csv.writer(resposta, delimiter=";")
        if tipo == "professores":
            escritor.writerow(["nome", "email", "telefone", "cpf", "nascimento", "status"])
            escritor.writerow(["Maria Souza", "maria@exemplo.com", "51999999999",
                               "123.456.789-09", "10/05/1990", "Ativo"])
        else:
            escritor.writerow(["nome", "email", "telefone", "cpf", "nascimento", "status"])
            escritor.writerow(["Joao Silva", "joao@exemplo.com", "51988888888",
                               "111.444.777-35", "22/03/1995", "Ativo"])
        return resposta


class MeuPlanoView(PainelMixin, TemplateView):
    """Pacote, limites, avisos e faturas da academia (RF-TEN-040..043)."""

    template_name = "gestao/plano.html"
    modulo = Modulo.PLANO
    titulo = "Meu plano"
    subtitulo = "Pacote, limites e faturas"

    def get_context_data(self, **kwargs):
        from plataforma.servicos import situacao_do_tenant

        contexto = super().get_context_data(**kwargs)
        situacao = situacao_do_tenant(self.request.rede)
        atual = situacao.get("pacote")
        outros = Pacote.objects.filter(ativo=True).exclude(pk=getattr(atual, "pk", None))
        contexto.update(
            situacao=situacao,
            faturas=Fatura.objects.filter(rede=self.request.rede).order_by("-vencimento")[:12],
            modulos_disponiveis=dict(ModuloPacote.choices),
            outros_pacotes=outros,
            aguardando_troca=getattr(situacao["assinatura"], "pacote_agendado", None),
        )
        return contexto


class MudarPacoteView(PainelMixin, View):
    """Upgrade imediato (com fatura proporcional) ou downgrade no proximo ciclo."""

    modulo = Modulo.PLANO
    nivel_minimo = "admin"

    def post(self, request, pk):
        from plataforma.servicos import CadastroError, trocar_pacote_do_tenant

        pacote = get_object_or_404(Pacote, pk=pk, ativo=True)
        try:
            resultado = trocar_pacote_do_tenant(request.rede, pacote, request=request,
                                               usuario=request.user)
        except CadastroError as erro:
            messages.error(request, str(erro))
            return redirect("gestao:plano")
        fatura = resultado.get("fatura")
        if fatura is not None:
            messages.success(request, f"{resultado['aviso']} Pix da fatura {fatura.numero} em Meu plano.")
        else:
            messages.success(request, resultado["aviso"])
        return redirect("gestao:plano")


class VisaoGeralView(PainelMixin, TemplateView):
    template_name = "gestao/visao_geral.html"
    modulo = Modulo.VISAO_GERAL
    titulo = "Visao geral"
    subtitulo = "Como esta a academia agora"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)
        alunos = escopo_unidade(Usuario.objects.all(), self.request)
        pagamentos = escopo_unidade(Pagamento.objects.all(), self.request)
        contexto.update(
            alunos_ativos=alunos.filter(status_user="Ativo").count(),
            alunos_total=alunos.count(),
            alunos_arquivados=escopo_unidade(Usuario.objects.all(), self.request)
            .filter(arquivado_em__isnull=False)
            .count(),
            professores=escopo_unidade(Professor.objects.filter(status_prof="Ativo"), self.request).count(),
            aulas=escopo_unidade(Aulas.objects.all(), self.request).count(),
            planos=escopo_unidade(Plano.objects.all(), self.request).count(),
            receita_mes=pagamentos.filter(
                status="pago", data_pagamento__gte=inicio_mes
            ).aggregate(total=Sum("valor_pago"))["total"] or 0,
            a_receber=pagamentos.filter(status="pendente").aggregate(total=Sum("valor_pago"))[
                "total"
            ] or 0,
            ultimos_alunos=alunos.order_by("-id")[:5],
            ultimos_pagamentos=pagamentos.select_related("usuario", "plano").order_by("-id")[:5],
            passos=self.passos_do_assistente(self.request),
        )
        return contexto

    @staticmethod
    def passos_do_assistente(request) -> list[dict]:
        """Checklist de configuracao (assistente da secao 7.3), calculado dos dados reais."""
        rede = request.rede
        config = Configuracao.todos.filter(rede=rede).first()
        identidade = IdentidadeVisual.todos.filter(rede=rede).first()
        email = ConfiguracaoEmail.todos.filter(rede=rede, ativo=True).first()
        passos = [
            {"rotulo": "Dados da academia", "feito": bool(config and config.cnpj),
             "rota": "gestao:identidade", "dica": "CNPJ, endereco e mensagens"},
            {"rotulo": "Unidade cadastrada", "feito": Unidade.todos.filter(rede=rede).exists(),
             "rota": "gestao:equipe", "dica": "Matriz ou filial"},
            {"rotulo": "Identidade visual", "feito": bool(identidade and identidade.logotipo),
             "rota": "gestao:identidade", "dica": "Logotipo e favicon"},
            {"rotulo": "Equipe com acesso", "feito": VinculoUsuario.todos.filter(rede=rede).count() > 1,
             "rota": "gestao:equipe", "dica": "Convide recepcao e professores"},
            {"rotulo": "Primeiro professor", "feito": Professor.objects.exists(),
             "rota": "gestao:professor_novo", "dica": "Cadastre quem da as aulas"},
            {"rotulo": "Primeira aula", "feito": Aulas.objects.exists(),
             "rota": "gestao:aula_nova", "dica": "Video ou aula presencial"},
            {"rotulo": "Primeiro plano", "feito": Plano.objects.exists(),
             "rota": "gestao:plano_novo", "dica": "Valores e periodicidade"},
            {"rotulo": "Primeiro aluno", "feito": Usuario.objects.exists(),
             "rota": "gestao:aluno_novo", "dica": "Com acesso ao sistema"},
            {"rotulo": "E-mail configurado", "feito": bool(email),
             "rota": "gestao:comunicacao", "dica": "SMTP da academia"},
        ]
        feitos = sum(1 for passo in passos if passo["feito"])
        for passo in passos:
            passo["percentual"] = round(100 * feitos / len(passos))
        return passos


# ===================================================================== MODULOS
def _colunas_aluno():
    return [("Nome", "nome"), ("E-mail", "email_user"), ("Telefone", "telefone_user"),
            ("Status", "status_user"), ("Acesso", "user.username")]


def _colunas_professor():
    return [("Nome", "nome"), ("E-mail", "email_prof"), ("Telefone", "telefone_prof"),
            ("Status", "status_prof")]


def _colunas_aula():
    return [("Aula", "nome"), ("Categoria", "categorias_exercicios"),
            ("Restricao", "restricao"), ("Video", "file_de_video")]


def _colunas_plano():
    return [("Plano", "nome"), ("Periodicidade", "tipo"), ("Valor", "valor")]


def _colunas_pagamento():
    return [("Aluno", "usuario.username"), ("Plano", "plano.nome"), ("Valor", "valor_pago"),
            ("Inicio", "data_inicio"), ("Fim", "data_fim"), ("Status", "status")]


class AlunosView(ListaPainel):
    model = Usuario
    modulo = Modulo.ALUNOS
    titulo = "Alunos"
    colunas = _colunas_aluno()
    campo_busca = ("nome", "email_user", "telefone_user", "cpf_cnpj_user")
    url_novo = "gestao:aluno_novo"
    url_editar = "gestao:aluno_editar"
    url_detalhe = "gestao:aluno_detalhe"
    url_arquivar = "gestao:aluno_arquivar"
    texto_vazio = "Nenhum aluno cadastrado ainda."

    def ajustar(self, qs):
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status_user=status)
        return qs.select_related("user")


class AlunoDetalheView(PainelMixin, DetailView):
    model = Usuario
    template_name = "gestao/aluno_detalhe.html"
    modulo = Modulo.ALUNOS
    titulo = "Ficha do aluno"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = self.object
        ficha = getattr(aluno, "fichasaude", None)
        usuario_de_login = aluno.user if aluno.user_id else None
        contexto.update(
            ficha=ficha,
            ficha_form=self.ficha_form(ficha),
            pagamentos=escopo_unidade(
                Pagamento.objects.filter(usuario=usuario_de_login)
                if usuario_de_login
                else Pagamento.objects.none(),
                self.request,
            ),
            agendamentos=escopo_unidade(
                Agendamento.objects.filter(aluno=usuario_de_login)
                if usuario_de_login
                else Agendamento.objects.none(),
                self.request,
            ).order_by("-data_agendamento")[:10],
            pode_anonimizar=nivel(self.request.user, Modulo.PRIVACIDADE.value,
                                  rede=self.request.rede) >= 3,
        )
        return contexto

    def ficha_form(self, ficha):
        from core.seguranca import registrar_acesso_sensivel
        from plataforma.servicos import impersonacao_ativa

        if impersonacao_ativa(self.request) is not None:
            return None  # suporte nao acessa ficha de saude (PRD 11.4)
        # LGPD art. 11: toda leitura de ficha de saude fica registrada (RNF-006e)
        registrar_acesso_sensivel(self.request.rede, self.request.user, self.object,
                                  origem="painel", acao="leitura")
        return FichaSaudeForm(instance=ficha)

    def post(self, request, *args, **kwargs):
        """Salva a ficha de saude do aluno."""
        from plataforma.servicos import impersonacao_ativa

        if impersonacao_ativa(request) is not None:
            raise PermissionDenied("A ficha de saude nao fica disponivel no acesso de suporte.")
        self.object = self.get_object()
        if not pode(request.user, Modulo.ALUNOS, "editar", rede=request.rede):
            raise PermissionDenied("Seu papel nao permite alterar dados de alunos.")
        ficha = getattr(self.object, "fichasaude", None)
        form = FichaSaudeForm(request.POST, request.FILES, instance=ficha)
        if form.is_valid():
            nova = form.save(commit=False)
            nova.usuario = self.object
            nova.save()
            registrar("alterar", "ficha_saude", entidade_id=self.object.pk,
                      descricao="Ficha de saude atualizada via painel", request=request)
            messages.success(request, "Ficha de saude atualizada.")
            return redirect("gestao:aluno_detalhe", pk=self.object.pk)
        contexto = self.get_context_data(object=self.object, ficha_form=form)
        return self.render_to_response(contexto)


class ProfessoresView(ListaPainel):
    model = Professor
    modulo = Modulo.PROFESSORES
    titulo = "Professores"
    colunas = _colunas_professor()
    campo_busca = ("nome", "email_prof", "telefone_prof")
    ordenacao = ("nome",)
    url_novo = "gestao:professor_novo"
    url_editar = "gestao:professor_editar"
    url_arquivar = "gestao:professor_arquivar"


class ProfessorNovo(CriarPainel):
    model = Professor
    form_class = ProfessorForm
    entidade = "professor"
    url_sucesso = "gestao:professores"
    titulo = "Novo professor"
    modulo = Modulo.PROFESSORES
    recurso_de_limite = "professores"

    def form_valid(self, form):
        resposta = super().form_valid(form)
        if getattr(form, "senha_temporaria", ""):
            messages.info(
                self.request,
                f"Senha temporaria do acesso: {form.senha_temporaria}",
            )
        return resposta


class ProfessorEditar(EditarPainel):
    model = Professor
    form_class = ProfessorForm
    entidade = "professor"
    url_sucesso = "gestao:professores"
    titulo = "Editar professor"
    modulo = Modulo.PROFESSORES


class ProfessorArquivar(ArquivarPainel):
    modelo = Professor
    entidade = "professor"
    url_voltar = "gestao:professores"


class AulasView(ListaPainel):
    model = Aulas
    modulo = Modulo.AULAS
    titulo = "Aulas e videos"
    colunas = _colunas_aula()
    campo_busca = ("nome", "descricao")
    ordenacao = ("nome",)
    ordenacao = ("nome",)
    url_novo = "gestao:aula_nova"
    url_editar = "gestao:aula_editar"
    url_arquivar = "gestao:aula_arquivar"

    def ajustar(self, qs):
        categoria = self.request.GET.get("categoria")
        if categoria:
            qs = qs.filter(categorias_exercicios=categoria)
        return qs.select_related("professor")


class AulaNova(CriarPainel):
    model = Aulas
    form_class = AulaForm
    entidade = "aula"
    url_sucesso = "gestao:aulas"
    titulo = "Nova aula"
    modulo = Modulo.AULAS
    aviso_ok = "Aula cadastrada."

    def aviso_de_sucesso(self) -> str:
        return self.aviso_ok


class AulaEditar(EditarPainel):
    model = Aulas
    form_class = AulaForm
    entidade = "aula"
    url_sucesso = "gestao:aulas"
    titulo = "Editar aula"
    modulo = Modulo.AULAS


class AulaArquivar(ArquivarPainel):
    modelo = Aulas
    entidade = "aula"
    url_voltar = "gestao:aulas"


# ------------------------------------------------------------------- AGENDA
class AgendaView(PainelMixin, TemplateView):
    template_name = "gestao/agenda.html"
    modulo = Modulo.AGENDA
    titulo = "Agenda e paineis"
    subtitulo = "Grade de aulas e presenca"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        agenda = escopo_unidade(Painel.objects.all(), self.request).order_by("data", "hora_inicio")
        contexto.update(
            paineis=agenda.filter(data__gte=hoje)[:30],
            agendamentos=escopo_unidade(Agendamento.objects.all(), self.request)
            .select_related("painel", "aluno")
            .order_by("-data_agendamento")[:30],
            total_agendamentos=escopo_unidade(Agendamento.objects.all(), self.request).count(),
        )
        return contexto


class PainelNovo(CriarPainel):
    model = Painel
    form_class = PainelForm
    entidade = "painel"
    url_sucesso = "gestao:agenda"
    titulo = "Nova grade de aulas"
    modulo = Modulo.AGENDA


class PainelEditar(EditarPainel):
    model = Painel
    form_class = PainelForm
    entidade = "painel"
    url_sucesso = "gestao:agenda"
    titulo = "Editar grade"
    modulo = Modulo.AGENDA


class AgendamentoConcluir(PainelMixin, View):
    """Check-in: marca o agendamento como concluido."""

    modulo = Modulo.AGENDA
    nivel_minimo = "editar"

    def post(self, request, pk):
        agendamento = get_object_or_404(
            Agendamento.objects, pk=pk
        )
        agendamento.status = "Concluido"
        agendamento.save(update_fields=["status"])
        registrar("alterar", "agendamento", entidade_id=agendamento.pk,
                  descricao="Check-in realizado no painel", request=request)
        messages.success(request, "Presenca confirmada.")
        return redirect("gestao:agenda")


# --------------------------------------------------------------- FINANCEIRO
class FinanceiroView(PainelMixin, TemplateView):
    template_name = "gestao/financeiro.html"
    modulo = Modulo.FINANCEIRO
    titulo = "Financeiro"
    subtitulo = "Planos, recebimentos e despesas"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)
        pagamentos = escopo_unidade(Pagamento.objects.all(), self.request)
        despesas = escopo_unidade(Despesa.objects.all(), self.request)
        receita_mes = pagamentos.filter(status="pago", data_pagamento__gte=inicio_mes).aggregate(
            total=Sum("valor_pago")
        )["total"] or 0
        despesa_mes = despesas.filter(data__gte=inicio_mes).aggregate(total=Sum("valor"))[
            "total"
        ] or 0
        contexto.update(
            receita_mes=receita_mes,
            despesa_mes=despesa_mes,
            resultado_mes=receita_mes - despesa_mes,
            pendentes=pagamentos.filter(status="pendente").aggregate(total=Sum("valor_pago"))[
                "total"
            ] or 0,
            vencendo=pagamentos.filter(
                status="pago", data_fim__gte=hoje, data_fim__lte=hoje + timedelta(days=7)
            ).count(),
            planos=escopo_unidade(Plano.objects.all(), self.request)[:10],
            ultimos_pagamentos=pagamentos.select_related("usuario", "plano").order_by("-id")[:10],
        )
        return contexto


class PlanosView(ListaPainel):
    model = Plano
    modulo = Modulo.FINANCEIRO
    titulo = "Planos"
    colunas = _colunas_plano()
    campo_busca = ("nome", "descricao")
    ordenacao = ("nome",)
    ordenacao = ("nome",)
    url_novo = "gestao:plano_novo"
    url_editar = "gestao:plano_editar"
    url_arquivar = "gestao:plano_arquivar"


class PlanoNovo(CriarPainel):
    model = Plano
    form_class = PlanoForm
    entidade = "plano"
    url_sucesso = "gestao:planos"
    titulo = "Novo plano"
    modulo = Modulo.FINANCEIRO


class PlanoEditar(EditarPainel):
    model = Plano
    form_class = PlanoForm
    entidade = "plano"
    url_sucesso = "gestao:planos"
    titulo = "Editar plano"
    modulo = Modulo.FINANCEIRO


class PlanoArquivar(ArquivarPainel):
    modelo = Plano
    entidade = "plano"
    url_voltar = "gestao:planos"


class PagamentosView(ListaPainel):
    model = Pagamento
    modulo = Modulo.FINANCEIRO
    titulo = "Pagamentos"
    colunas = _colunas_pagamento()
    url_novo = "gestao:pagamento_novo"
    url_editar = "gestao:pagamento_editar"
    mostrar_arquivados = False

    def ajustar(self, qs):
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs.select_related("usuario", "plano")


class PagamentoNovo(CriarPainel):
    model = Pagamento
    form_class = PagamentoForm
    entidade = "pagamento"
    url_sucesso = "gestao:pagamentos"
    titulo = "Novo pagamento"
    modulo = Modulo.FINANCEIRO

    def aviso_de_sucesso(self) -> str:
        return f"Pagamento de {self.object.valor_pago} lancado."


class PagamentoEditar(EditarPainel):
    model = Pagamento
    form_class = PagamentoForm
    entidade = "pagamento"
    url_sucesso = "gestao:pagamentos"
    titulo = "Editar pagamento"
    modulo = Modulo.FINANCEIRO


class PagamentoBaixar(PainelMixin, View):
    """Baixa manual: marca o pagamento como pago hoje."""

    modulo = Modulo.FINANCEIRO
    nivel_minimo = "editar"

    def post(self, request, pk):
        pagamento = get_object_or_404(Pagamento.objects, pk=pk)
        pagamento.status = "pago"
        pagamento.data_pagamento = timezone.localdate()
        pagamento.save(update_fields=["status", "data_pagamento"])
        registrar("alterar", "pagamento", entidade_id=pagamento.pk,
                  descricao="Baixa manual de pagamento no painel", request=request)
        messages.success(request, f"Pagamento de {pagamento.usuario} marcado como pago.")
        return redirect("gestao:pagamentos")


class DespesasView(ListaPainel):
    model = Despesa
    modulo = Modulo.FINANCEIRO
    titulo = "Despesas"
    colunas = [("Descricao", "descricao"), ("Valor", "valor"), ("Data", "data"),
               ("Categoria", "categoria")]
    campo_busca = ("descricao", "categoria")
    url_novo = "gestao:despesa_nova"
    url_editar = "gestao:despesa_editar"


class DespesaNova(CriarPainel):
    model = Despesa
    form_class = DespesaForm
    entidade = "despesa"
    url_sucesso = "gestao:despesas"
    titulo = "Nova despesa"
    modulo = Modulo.FINANCEIRO


class DespesaEditar(EditarPainel):
    model = Despesa
    form_class = DespesaForm
    entidade = "despesa"
    url_sucesso = "gestao:despesas"
    titulo = "Editar despesa"
    modulo = Modulo.FINANCEIRO


# ------------------------------------------------------------------- ALUNOS
class AlunoNovo(CriarPainel):
    model = Usuario
    form_class = AlunoForm
    entidade = "aluno"
    url_sucesso = "gestao:alunos"
    titulo = "Novo aluno"
    modulo = Modulo.ALUNOS
    recurso_de_limite = "alunos"

    def form_valid(self, form):
        resposta = super().form_valid(form)
        if getattr(form, "senha_temporaria", ""):
            messages.info(self.request, f"Senha temporaria do acesso: {form.senha_temporaria}")
        return resposta


class AlunoEditar(EditarPainel):
    model = Usuario
    form_class = AlunoForm
    entidade = "aluno"
    url_sucesso = "gestao:alunos"
    titulo = "Editar aluno"
    modulo = Modulo.ALUNOS


class AlunoArquivar(ArquivarPainel):
    modelo = Usuario
    entidade = "aluno"
    url_voltar = "gestao:alunos"


# --------------------------------------------------------------- RELATORIOS
class RelatoriosView(PainelMixin, TemplateView):
    template_name = "gestao/relatorios.html"
    modulo = Modulo.RELATORIOS
    titulo = "Relatorios"
    subtitulo = "Exportacoes e indicadores"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        alunos = escopo_unidade(Usuario.objects.all(), self.request)
        pagamentos = escopo_unidade(Pagamento.objects.all(), self.request)
        contexto.update(
            total_alunos=alunos.count(),
            ativos=alunos.filter(status_user="Ativo").count(),
            inadimplentes=pagamentos.filter(status="pendente").values("usuario").distinct().count(),
            receita_total=pagamentos.filter(status="pago").aggregate(total=Sum("valor_pago"))[
                "total"
            ] or 0,
            vencendo_7=pagamentos.filter(
                status="pago", data_fim__gte=hoje, data_fim__lte=hoje + timedelta(days=7)
            ).count(),
            links_existentes=[
                ("Alunos (CSV)", "gestao:relatorio_alunos_csv"),
                ("Pagamentos (CSV)", "gestao:relatorio_pagamentos_csv"),
            ],
        )
        return contexto


def _csv(nome: str) -> HttpResponse:
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta.write("\ufeff")  # BOM: Excel abre com acentos
    return resposta


class RelatorioAlunosCsv(ModuloDePacoteMixin, PainelMixin, View):
    modulo = Modulo.RELATORIOS
    modulo_pacote = ModuloPacote.RELATORIOS_AVANCADOS

    def get(self, request):
        resposta = _csv("alunos.csv")
        escritor = csv.writer(resposta, delimiter=";")
        escritor.writerow(["Nome", "E-mail", "Telefone", "CPF/CNPJ", "Status", "Acesso"])
        for aluno in escopo_unidade(Usuario.objects.all(), request).select_related("user"):
            escritor.writerow([
                aluno.nome, aluno.email_user, aluno.telefone_user, aluno.cpf_cnpj_user,
                aluno.status_user, getattr(aluno.user, "username", ""),
            ])
        registrar("exportar", "aluno", descricao="Exportacao CSV de alunos", request=request)
        return resposta


class RelatorioPagamentosCsv(ModuloDePacoteMixin, PainelMixin, View):
    modulo = Modulo.RELATORIOS
    modulo_pacote = ModuloPacote.RELATORIOS_AVANCADOS

    def get(self, request):
        resposta = _csv("pagamentos.csv")
        escritor = csv.writer(resposta, delimiter=";")
        escritor.writerow(["Aluno", "Plano", "Valor", "Inicio", "Fim", "Status", "Pago em"])
        for pagamento in escopo_unidade(Pagamento.objects.all(), request).select_related(
            "usuario", "plano"
        ):
            escritor.writerow([
                getattr(pagamento.usuario, "username", ""),
                getattr(pagamento.plano, "nome", ""),
                pagamento.valor_pago,
                pagamento.data_inicio,
                pagamento.data_fim,
                pagamento.status,
                pagamento.data_pagamento,
            ])
        registrar("exportar", "pagamento", descricao="Exportacao CSV de pagamentos", request=request)
        return resposta


# ---------------------------------------------------------------- COMUNICACAO
class ComunicacaoView(PainelMixin, View):
    template_name = "gestao/comunicacao.html"
    modulo = Modulo.COMUNICACAO
    titulo = "Comunicacao"

    def contexto(self, request, form_email=None, form_whats=None):
        email = ConfiguracaoEmail.todos.filter(rede=request.rede).first()
        whats = ConfiguracaoWhatsapp.todos.filter(rede=request.rede).first()
        return {
            "painel": True, "titulo": self.titulo, "modulo": self.modulo,
            "form_email": form_email or EmailConfigForm(instance=email, prefix="email"),
            "form_whats": form_whats or WhatsappConfigForm(instance=whats, prefix="whatsapp"),
            "config_email": email, "config_whats": whats,
            "pode_editar": pode(request.user, self.modulo, "editar", rede=request.rede),
        }

    def get(self, request):
        return render(request, self.template_name, self.contexto(request))

    def post(self, request):
        email = ConfiguracaoEmail.todos.filter(rede=request.rede).first()
        whats = ConfiguracaoWhatsapp.todos.filter(rede=request.rede).first()
        form_email = EmailConfigForm(request.POST, instance=email, prefix="email")
        form_whats = WhatsappConfigForm(request.POST, instance=whats, prefix="whatsapp")
        if "email-host" in request.POST and form_email.is_valid():
            config = form_email.save(commit=False)
            config.rede = request.rede
            config.unidade = request.unidade
            config.save()
            registrar("alterar", "comunicacao", entidade_id=config.pk,
                      descricao="Configuracao de e-mail atualizada", request=request)
            messages.success(request, "Configuracao de e-mail salva.")
            return redirect("gestao:comunicacao")
        if "whatsapp-access_token" in request.POST and not modulo_disponivel(
            request.rede, ModuloPacote.WHATSAPP
        ):
            messages.error(
                request,
                "O WhatsApp nao esta incluido no seu pacote. Fale com a SafeStack para habilitar.",
            )
            return redirect("gestao:comunicacao")
        if "whatsapp-access_token" in request.POST and form_whats.is_valid():
            config = form_whats.save(commit=False)
            config.rede = request.rede
            config.unidade = request.unidade
            config.save()
            registrar("alterar", "comunicacao", entidade_id=config.pk,
                      descricao="Configuracao de WhatsApp atualizada", request=request)
            messages.success(request, "Configuracao de WhatsApp salva.")
            return redirect("gestao:comunicacao")
        messages.error(request, "Nao foi possivel salvar: confira os campos destacados.")
        return render(request, self.template_name,
                      self.contexto(request, form_email, form_whats))


class ComunicacaoTesteView(PainelMixin, View):
    """Envia um e-mail de teste usando o SMTP configurado pela academia."""

    modulo = Modulo.COMUNICACAO

    def post(self, request):
        destino = request.POST.get("destino") or getattr(request.user, "email", "")
        if not destino:
            messages.error(request, "Informe um e-mail de destino.")
            return redirect("gestao:comunicacao")
        assunto = f"Teste de envio - {request.rede.nome}"
        corpo = "Este e um e-mail de teste enviado pelo painel da academia."
        try:
            de = enviar_email(request.rede, assunto, corpo, [destino])
            registrar("enviar", "comunicacao", descricao=f"E-mail de teste para {destino}",
                      request=request)
            messages.success(request, f"E-mail de teste enviado para {destino} (remetente {de}).")
        except Exception as erro:  # noqa: BLE001
            messages.error(request, f"Falha ao enviar: {erro}")
        return redirect("gestao:comunicacao")


# ---------------------------------------------------------------- IDENTIDADE
class IdentidadeView(PainelMixin, View):
    template_name = "gestao/identidade.html"
    modulo = Modulo.IDENTIDADE
    titulo = "Identidade e dados fiscais"

    def contexto(self, request, form_config=None, form_visual=None):
        config = Configuracao.todos.filter(rede=request.rede).first()
        visual = IdentidadeVisual.todos.filter(rede=request.rede).first()
        return {
            "painel": True, "titulo": self.titulo, "modulo": self.modulo,
            "form_config": form_config or ConfiguracaoForm(instance=config, prefix="config"),
            "form_visual": form_visual or IdentidadeForm(instance=visual, prefix="visual"),
            "config": config, "visual": visual,
            "pode_editar": pode(request.user, self.modulo, "editar", rede=request.rede),
        }

    def get(self, request):
        return render(request, self.template_name, self.contexto(request))

    def post(self, request):
        config = Configuracao.todos.filter(rede=request.rede).first()
        visual = IdentidadeVisual.todos.filter(rede=request.rede).first()
        form_config = ConfiguracaoForm(request.POST, instance=config, prefix="config")
        form_visual = IdentidadeForm(request.POST, request.FILES, instance=visual, prefix="visual")
        if "config-titulo" in request.POST and form_config.is_valid():
            objeto = form_config.save(commit=False)
            objeto.rede = request.rede
            objeto.unidade = request.unidade
            objeto.save()
            registrar("alterar", "configuracao", entidade_id=objeto.pk,
                      descricao="Dados da academia atualizados", request=request)
            messages.success(request, "Dados da academia salvos.")
            return redirect("gestao:identidade")
        if "visual-logotipo" in request.POST and form_visual.is_valid():
            objeto = form_visual.save(commit=False)
            objeto.rede = request.rede
            objeto.unidade = request.unidade
            objeto.save()
            registrar("alterar", "identidade", entidade_id=objeto.pk,
                      descricao="Identidade visual atualizada", request=request)
            messages.success(request, "Identidade visual salva.")
            return redirect("gestao:identidade")
        messages.error(request, "Nao foi possivel salvar: confira os campos destacados.")
        return render(request, self.template_name, self.contexto(request, form_config, form_visual))


# ----------------------------------------------------------------- AUDITORIA
class AuditoriaView(ListaPainel):
    model = RegistroAuditoria
    modulo = Modulo.AUDITORIA
    titulo = "Auditoria"
    colunas = [("Quando", "criado_em"), ("Quem", "usuario.username"), ("Acao", "acao"),
               ("Entidade", "entidade"), ("Descricao", "descricao"), ("IP", "ip")]
    texto_vazio = "Nenhum evento registrado."
    mostrar_arquivados = False
    paginate_by = 50

    def ajustar(self, qs):
        qs = da_rede(qs, self.request)
        acao = self.request.GET.get("acao")
        entidade = self.request.GET.get("entidade")
        if acao:
            qs = qs.filter(acao=acao)
        if entidade:
            qs = qs.filter(entidade=entidade)
        return qs.select_related("usuario").order_by("-criado_em")


# -------------------------------------------------------------------- EQUIPE
class EquipeView(PainelMixin, TemplateView):
    template_name = "gestao/equipe.html"
    modulo = Modulo.EQUIPE
    titulo = "Equipe e acessos"
    subtitulo = "Quem entra no painel e com qual papel"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            vinculos=VinculoUsuario.todos.filter(rede=self.request.rede)
            .select_related("usuario", "unidade")
            .order_by("papel"),
            convites=ConviteEquipe.objects.filter(rede=self.request.rede).order_by("-criado_em")[:20],
            form=ConviteForm(unidades=unidades_do_usuario(self.request.user)),
            unidades=unidades_do_usuario(self.request.user),
        )
        return contexto


class ConviteNovo(EdicaoMixin, CreateView):
    model = ConviteEquipe
    form_class = ConviteForm
    template_name = "gestao/convite_form.html"
    modulo = Modulo.EQUIPE
    titulo = "Convidar para a equipe"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["unidades"] = unidades_do_usuario(self.request.user)
        return kwargs

    def form_valid(self, form):
        convite = form.save(commit=False)
        convite.rede = self.request.rede
        convite.token = ConviteEquipe.gerar_token()
        convite.expira_em = timezone.now() + timedelta(days=7)
        convite.criado_por = self.request.user
        convite.save()
        self.object = convite
        link = self.request.build_absolute_uri(
            reverse("gestao:convite_aceitar", args=[convite.token])
        )
        enviado = False
        try:
            enviar_email(
                self.request.rede,
                f"Convite para acessar o painel de {self.request.rede.nome}",
                f"Voce foi convidado como {convite.get_papel_display()}.\n\nAceite em: {link}"
                "\n\nO link expira em 7 dias.",
                [convite.email],
            )
            enviado = True
        except Exception as erro:  # noqa: BLE001
            messages.warning(self.request, f"Convite criado, mas o e-mail falhou: {erro}")
        registrar("criar", "convite", entidade_id=convite.pk,
                  descricao=f"Convite para {convite.email} ({convite.get_papel_display()})",
                  request=self.request)
        if enviado:
            messages.success(self.request, f"Convite enviado para {convite.email}.")
        else:
            messages.info(self.request, f"Link do convite: {link}")
        return redirect("gestao:equipe")


class ConviteCancelar(EdicaoMixin, View):
    modulo = Modulo.EQUIPE
    nivel_minimo = "editar"

    def post(self, request, pk):
        convite = get_object_or_404(ConviteEquipe.objects, pk=pk, rede=request.rede)
        convite.status = ConviteEquipe.Status.CANCELADO
        convite.save(update_fields=["status"])
        registrar("alterar", "convite", entidade_id=convite.pk,
                  descricao=f"Convite de {convite.email} cancelado", request=request)
        messages.success(request, "Convite cancelado.")
        return redirect("gestao:equipe")


class VinculoAlternar(EdicaoMixin, View):
    """Ativa/desativa o acesso de alguem da equipe."""

    modulo = Modulo.EQUIPE
    nivel_minimo = "editar"

    def post(self, request, pk):
        vinculo = get_object_or_404(VinculoUsuario.todos, pk=pk, rede=request.rede)
        if vinculo.usuario_id == request.user.pk:
            messages.error(request, "Voce nao pode desativar o proprio acesso.")
            return redirect("gestao:equipe")
        vinculo.ativo = not vinculo.ativo
        vinculo.save(update_fields=["ativo"])
        registrar("alterar", "vinculo", entidade_id=vinculo.pk,
                  descricao=f"Acesso de {vinculo.usuario} {'ativado' if vinculo.ativo else 'desativado'}",
                  request=request)
        messages.success(
            request, f"Acesso de {vinculo.usuario} {'ativado' if vinculo.ativo else 'desativado'}."
        )
        return redirect("gestao:equipe")


class SegurancaView(PainelMixin, TemplateView):
    """Seguranca da propria conta: 2FA e historico de acessos (RNF-009)."""

    template_name = "gestao/seguranca.html"
    titulo = "Segurança"
    subtitulo = "Proteção da sua conta e histórico de acessos"

    def get_context_data(self, **kwargs):
        from core.seguranca import dispositivo_do, dois_fatores_ativo
        from governanca.models import CodigoRecuperacao, TentativaDeLogin

        contexto = super().get_context_data(**kwargs)
        dispositivo = dispositivo_do(self.request.user)
        identificadores = [self.request.user.username, self.request.user.email or "-"]
        contexto.update(
            dois_fatores=dois_fatores_ativo(self.request.user),
            confirmado_em=getattr(dispositivo, "confirmado_em", None),
            ultimo_uso=getattr(dispositivo, "ultimo_uso_em", None),
            codigos_disponiveis=CodigoRecuperacao.objects.filter(
                usuario=self.request.user, usado_em__isnull=True).count(),
            tentativas=TentativaDeLogin.objects.filter(identificador__in=identificadores)[:15],
            recentes=TentativaDeLogin.objects.all()[:10],
        )
        return contexto


class PrivacidadeView(PainelMixin, TemplateView):
    """LGPD: pedidos do titular, retencao e acessos a dado sensivel."""

    template_name = "gestao/privacidade.html"
    modulo = Modulo.PRIVACIDADE
    titulo = "Privacidade e LGPD"
    subtitulo = "Pedidos, retenção de dados e acesso a dado sensível"

    def get_context_data(self, **kwargs):
        from governanca.models import AcessoDadoSensivel, RegraRetencao, SolicitacaoTitular

        contexto = super().get_context_data(**kwargs)
        abertas = SolicitacaoTitular.objects.filter(
            rede=self.request.rede, situacao=SolicitacaoTitular.Situacao.ABERTA)
        contexto.update(
            solicitacoes=SolicitacaoTitular.objects.filter(rede=self.request.rede)[:25],
            abertas=abertas.count(),
            atrasadas=[pedido for pedido in abertas if pedido.atrasada],
            regras=RegraRetencao.objects.filter(ativo=True),
            acessos=AcessoDadoSensivel.objects.filter(rede=self.request.rede)[:25],
            tipos=SolicitacaoTitular.Tipo.choices,
        )
        return contexto


class SolicitacaoTitularView(PainelMixin, View):
    """Registra um pedido de titular (acesso, exportacao, correcao, eliminacao)."""

    modulo = Modulo.PRIVACIDADE
    nivel_minimo = "editar"

    def post(self, request):
        from governanca.models import SolicitacaoTitular
        from governanca.servicos import prazo_do_pedido

        nome = (request.POST.get("titular_nome") or "").strip()
        tipo = request.POST.get("tipo") or SolicitacaoTitular.Tipo.ACESSO
        if not nome:
            messages.error(request, "Informe o nome do titular.")
            return redirect("gestao:privacidade")
        pedido = SolicitacaoTitular.objects.create(
            rede=request.rede, titular_nome=nome,
            titular_email=(request.POST.get("titular_email") or "").strip(),
            tipo=tipo, descricao=(request.POST.get("descricao") or "").strip(),
            prazo_em=prazo_do_pedido(),
        )
        registrar("criar", "solicitacao_titular", entidade_id=pedido.pk,
                  descricao=f"Pedido de {pedido.get_tipo_display()} do titular {nome}", request=request)
        messages.success(request, f"Pedido registrado. Prazo legal até {pedido.prazo_em:%d/%m/%Y}.")
        return redirect("gestao:privacidade")


class ConcluirSolicitacaoView(PainelMixin, View):
    modulo = Modulo.PRIVACIDADE
    nivel_minimo = "editar"

    def post(self, request, pk):
        from governanca.models import SolicitacaoTitular

        pedido = get_object_or_404(SolicitacaoTitular, pk=pk, rede=request.rede)
        pedido.situacao = request.POST.get("situacao") or SolicitacaoTitular.Situacao.CONCLUIDA
        pedido.resposta = (request.POST.get("resposta") or "").strip()
        pedido.concluida_em = timezone.now()
        pedido.save(update_fields=["situacao", "resposta", "concluida_em", "atualizado_em"])
        registrar("alterar", "solicitacao_titular", entidade_id=pedido.pk,
                  descricao=f"Pedido de {pedido.get_tipo_display()} -> {pedido.get_situacao_display()}",
                  request=request)
        messages.success(request, "Pedido atualizado.")
        return redirect("gestao:privacidade")


class ExportarTitularView(PainelMixin, View):
    """Entrega tudo que guardamos sobre o titular (LGPD art. 18)."""

    modulo = Modulo.PRIVACIDADE
    nivel_minimo = "ver"

    def get(self, request, pk):
        from governanca.servicos import exportar_titular_zip

        aluno = get_object_or_404(Usuario.todos, pk=pk, rede=request.rede)
        conteudo = exportar_titular_zip(request.rede, aluno)
        registrar("exportar", "titular", entidade_id=aluno.pk,
                  descricao=f"Dados do titular {aluno.nome} exportados (LGPD)", request=request)
        resposta = HttpResponse(conteudo, content_type="application/zip")
        resposta["Content-Disposition"] = f'attachment; filename="dados-titular-{aluno.pk}.zip"'
        return resposta


class AnonimizarTitularView(PainelMixin, View):
    """Anonimiza o titular preservando o que a lei manda guardar (RF-TEN-021)."""

    modulo = Modulo.PRIVACIDADE
    nivel_minimo = "admin"

    def post(self, request, pk):
        from governanca.servicos import anonimizar_titular

        aluno = get_object_or_404(Usuario.todos, pk=pk, rede=request.rede)
        if (request.POST.get("confirmacao") or "").strip().upper() != "ANONIMIZAR":
            messages.error(request, "Para confirmar, digite ANONIMIZAR no campo de confirmação.")
            return redirect("gestao:aluno_detalhe", pk=aluno.pk)
        resultado = anonimizar_titular(request.rede, aluno, usuario=request.user,
                                       motivo=(request.POST.get("motivo") or "").strip())
        messages.success(
            request,
            f"Titular anonimizado ({resultado['marcador']}). Os pagamentos foram preservados por "
            "obrigação fiscal e o pedido ficou registrado na auditoria.",
        )
        return redirect("gestao:privacidade")


class DominioView(PainelMixin, TemplateView):
    """Endereco da academia: subdominio, dominio proprio e certificado (RF-PLT-050..052)."""

    template_name = "gestao/dominio.html"
    modulo = Modulo.DOMINIO
    titulo = "Domínio e endereço"
    subtitulo = "Onde a sua academia é atendida"

    def get_context_data(self, **kwargs):
        from governanca.servicos import estado_do_provisionamento, instrucoes_de_dns, subdominio_da

        contexto = super().get_context_data(**kwargs)
        rede = self.request.rede
        contexto.update(
            estado=estado_do_provisionamento(rede),
            instrucoes=instrucoes_de_dns(rede) if rede.dominio else None,
            subdominio=subdominio_da(rede),
            dominio=getattr(rede, "dominio", ""),
        )
        return contexto


class VerificarDominioView(PainelMixin, View):
    modulo = Modulo.DOMINIO
    nivel_minimo = "admin"

    def post(self, request):
        from governanca.servicos import verificar_dominio

        rede = request.rede
        novo_dominio = (request.POST.get("dominio") or "").strip().lower()
        if novo_dominio and novo_dominio != rede.dominio:
            rede.dominio = novo_dominio
            rede.dominio_status = "pendente_dns"
            rede.save(update_fields=["dominio", "dominio_status", "atualizado_em"])
        resultado = verificar_dominio(rede, forcar=True)
        registrar("alterar", "dominio", entidade_id=rede.pk,
                  descricao=f"Verificacao de dominio {rede.dominio}: {resultado['mensagem'][:120]}",
                  request=request)
        if resultado["ok"]:
            messages.success(request, "Domínio confirmado! Agora vamos emitir o certificado.")
        else:
            messages.warning(request, resultado["mensagem"])
        return redirect("gestao:dominio")



class ConviteAceitarView(View):
    """Pagina publica de aceite: cria a conta e o vinculo."""

    template_name = "gestao/convite_aceitar.html"

    def _convite(self, token):
        return get_object_or_404(ConviteEquipe.objects, token=token)

    def get(self, request, token):
        convite = self._convite(token)
        return render(request, self.template_name, {
            "convite": convite, "valido": convite.esta_valido(),
            "form": NovaContaForm(), "logado": request.user.is_authenticated,
        })

    def post(self, request, token):
        convite = self._convite(token)
        if not convite.esta_valido():
            return render(request, self.template_name,
                          {"convite": convite, "valido": False, "form": NovaContaForm()})
        if request.user.is_authenticated:
            convite.aceitar(request.user)
            messages.success(request, "Convite aceito. Bem-vindo(a)!")
            return redirect("gestao:visao_geral")
        form = NovaContaForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name,
                          {"convite": convite, "valido": True, "form": form})
        usuario, _ = criar_ou_vincular_usuario(
            convite.email, form.cleaned_data["senha"], {}
        )
        if usuario is None:
            messages.error(request, "Nao foi possivel criar o acesso.")
            return redirect("login")
        usuario.first_name = form.cleaned_data["nome"][:150]
        usuario.save(update_fields=["first_name"])
        convite.aceitar(usuario)
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Bem-vindo(a), {usuario.first_name}!")
        return redirect("gestao:visao_geral")


# ------------------------------------------------------------------- ONBOARDING
class OnboardingView(PainelMixin, TemplateView):
    template_name = "gestao/onboarding.html"
    modulo = Modulo.VISAO_GERAL
    titulo = "Configuracao da academia"
    subtitulo = "Deixe a academia pronta para operar"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["passos"] = VisaoGeralView.passos_do_assistente(self.request)
        return contexto


# ------------------------------------------------------------------- UNIDADE
class SelecionarUnidadeView(PainelMixin, View):
    """Troca a unidade ativa da sessao (com checagem de acesso)."""

    def post(self, request):
        unidade_id = request.POST.get("unidade") or ""
        if not unidade_id:
            request.session.pop("unidade_id", None)
            messages.success(request, "Vendo todas as unidades da rede.")
            return redirect(request.POST.get("voltar") or "gestao:visao_geral")
        permitidas = unidades_do_usuario(request.user)
        if not request.user.is_superuser and not permitidas.filter(pk=unidade_id).exists():
            raise PermissionDenied("Voce nao tem acesso a esta unidade.")
        request.session["rede_id"] = request.rede.pk
        request.session["unidade_id"] = int(unidade_id)
        messages.success(request, "Unidade alterada.")
        return redirect(request.POST.get("voltar") or "gestao:visao_geral")
