"""Paginas publicas: home, planos, cadastro self-service, ajuda e contato."""

from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from plataforma.models import ConfiguracaoPlataforma, ModuloPacote, Pacote
from plataforma.servicos import CadastroError, cadastrar_tenant_publico, slug_disponivel
from plataforma.validadores import sugerir_slug, validar_cnpj
from vitrine.forms import CadastroPublicoForm, ContatoForm

CHAVE_CADASTRO = "cadastro_publico"


def pacotes_publicos():
    return Pacote.objects.filter(ativo=True, visivel_no_site=True)


class BasePublica(TemplateView):
    def get_context_data(self, **kwargs):
        from plataforma.servicos import compra_de_pacote_liberada

        contexto = super().get_context_data(**kwargs)
        contexto.setdefault("modulos_pacote", list(ModuloPacote.choices))
        contexto.setdefault("configuracao", ConfiguracaoPlataforma.obter())
        contexto["compra_liberada"] = compra_de_pacote_liberada()
        return contexto


class HomeView(BasePublica):
    template_name = "vitrine/home.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["pacotes"] = pacotes_publicos()
        return contexto


class PlanosView(BasePublica):
    template_name = "vitrine/planos.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["pacotes"] = pacotes_publicos()
        return contexto


class AjudaView(BasePublica):
    template_name = "vitrine/ajuda.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["topicos"] = [
            {
                "titulo": "Primeiros passos",
                "itens": [
                    "Criar a conta e definir a senha pelo link recebido por e-mail",
                    "Preencher os dados da academia e enviar o logo",
                    "Cadastrar professores e planos",
                    "Importar alunos por planilha CSV",
                ],
            },
            {
                "titulo": "Alunos e agenda",
                "itens": [
                    "Ficha do aluno com historico de pagamentos e presenca",
                    "Aulas em video e paineis de treino",
                    "Check-in na recepcao",
                ],
            },
            {
                "titulo": "Financeiro",
                "itens": [
                    "Planos e valores",
                    "Lancar pagamento e dar baixa",
                    "Relatorios e exportacao CSV",
                ],
            },
            {
                "titulo": "Plano e cobranca",
                "itens": [
                    "Ver uso e limites em Meu plano",
                    "Trocar de pacote a qualquer momento",
                    "Faturas e Pix copia e cola",
                ],
            },
            {
                "titulo": "Equipe e acessos",
                "itens": [
                    "Convidar recepcao, professores e financeiro",
                    "Cada pessoa ve apenas o que o papel dela permite",
                ],
            },
        ]
        return contexto


class ContatoView(BasePublica):
    template_name = "vitrine/contato.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.setdefault("form", ContatoForm())
        return contexto

    def post(self, request):
        from plataforma.emails import enviar_email_plataforma

        form = ContatoForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    **self.get_context_data(),
                    "form": form,
                },
            )
        dados = form.cleaned_data
        configuracao = ConfiguracaoPlataforma.obter()
        destino = configuracao.email_financeiro or configuracao.nome_emitente
        enviar_email_plataforma(
            f"Contato pelo site: {dados['nome']}",
            "\n".join(
                [
                    f"Nome: {dados['nome']}",
                    f"E-mail: {dados['email']}",
                    f"Telefone: {dados.get('telefone') or '-'}",
                    f"Academia: {dados.get('academia') or '-'}",
                    "",
                    dados["mensagem"],
                ]
            ),
            [destino] if "@" in str(destino) else [],
        )
        return render(
            request,
            self.template_name,
            {
                **self.get_context_data(),
                "enviado": True,
            },
        )


class CadastroView(BasePublica):
    template_name = "vitrine/cadastro.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        plano = self.request.GET.get("plano", "")
        pacote = pacotes_publicos().filter(codigo=plano).first()
        contexto["pacotes"] = pacotes_publicos()
        contexto["pacote_escolhido"] = pacote
        contexto.setdefault("form", CadastroPublicoForm(pacote=pacote))
        contexto["slug_sugerido"] = sugerir_slug(self.request.GET.get("nome", ""))
        return contexto

    def get(self, request):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request):
        codigo = request.POST.get("pacote") or request.GET.get("plano", "")
        pacote = pacotes_publicos().filter(codigo=codigo).first()
        form = CadastroPublicoForm(request.POST, pacote=pacote)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    **self.get_context_data(),
                    "form": form,
                    "pacote_escolhido": pacote,
                },
            )
        dados = form.cleaned_data
        try:
            resultado = cadastrar_tenant_publico(
                nome=dados["nome"],
                slug=dados["slug"],
                cnpj=dados.get("cnpj", ""),
                responsavel=dados.get("responsavel", ""),
                email=dados["email"],
                telefone=dados.get("telefone", ""),
                pacote=pacote,
                modalidade=dados["modalidade"],
                request=request,
            )
        except CadastroError as erro:
            form.add_error(None, str(erro))
            return render(
                request,
                self.template_name,
                {
                    **self.get_context_data(),
                    "form": form,
                    "pacote_escolhido": pacote,
                },
            )
        request.session[CHAVE_CADASTRO] = {
            "rede": resultado["rede"].pk,
            "fatura": getattr(resultado["fatura"], "pk", None),
            "email_enviado": resultado["email_enviado"],
            "trial": dados["modalidade"] == "trial",
            "link": resultado["link_primeiro_acesso"],
        }
        return redirect("vitrine:cadastro_concluido")


class CadastroConcluidoView(BasePublica):
    template_name = "vitrine/cadastro_concluido.html"

    def get_context_data(self, **kwargs):
        from plataforma.models import Fatura

        contexto = super().get_context_data(**kwargs)
        dados = self.request.session.get(CHAVE_CADASTRO) or {}
        contexto["rede"] = None
        if dados.get("rede"):
            from core.models import Rede

            contexto["rede"] = Rede.todos.filter(pk=dados["rede"]).first()
        contexto["fatura"] = (
            Fatura.objects.filter(pk=dados["fatura"]).first() if dados.get("fatura") else None
        )
        contexto["email_enviado"] = dados.get("email_enviado", False)
        contexto["link"] = dados.get("link", "")
        contexto["trial"] = dados.get("trial", False)
        return contexto


class VerificarSlugView(View):
    """Checagem ao vivo do identificador (usada no formulario de cadastro)."""

    def get(self, request):
        slug = (request.GET.get("slug") or "").strip().lower()
        if not slug:
            return JsonResponse({"disponivel": False, "mensagem": "Informe um identificador."})
        liberado, mensagem = slug_disponivel(slug)
        return JsonResponse({"disponivel": liberado, "mensagem": mensagem})


class VerificarCnpjView(View):
    def get(self, request):
        cnpj = (request.GET.get("cnpj") or "").strip()
        if not cnpj:
            return JsonResponse({"valido": False, "mensagem": "Informe o CNPJ."})
        if not validar_cnpj(cnpj):
            return JsonResponse({"valido": False, "mensagem": "CNPJ invalido."})
        from plataforma.servicos import cnpj_em_uso

        if cnpj_em_uso(cnpj):
            return JsonResponse({"valido": False, "mensagem": "CNPJ ja cadastrado."})
        return JsonResponse({"valido": True, "mensagem": "CNPJ ok."})
