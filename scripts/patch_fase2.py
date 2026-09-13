#!/usr/bin/env python3
"""Fase 2: liga o painel ao projeto (idempotente).

- adiciona ConviteEquipe em core/models.py (com os imports necessarios)
- registra o app "gestao" em app/settings_env/base.py
- registra o context processor do menu do painel
- adiciona a rota /gestao/ em app/urls.py
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MODELO_CONVITE = '''

class ConviteEquipe(models.Model):
    """Convite para alguem entrar na equipe de uma rede (opcionalmente de uma unidade)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ACEITO = "aceito", "Aceito"
        EXPIRADO = "expirado", "Expirado"
        CANCELADO = "cancelado", "Cancelado"

    rede = models.ForeignKey(
        "core.Rede", on_delete=models.CASCADE, related_name="convites", verbose_name="rede"
    )
    unidade = models.ForeignKey(
        "core.Unidade", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="convites", verbose_name="unidade",
    )
    email = models.EmailField("e-mail")
    papel = models.CharField("papel", max_length=32, choices=Papel.choices)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDENTE, db_index=True
    )
    expira_em = models.DateTimeField("expira em")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="convites_criados", verbose_name="criado por",
    )
    criado_em = models.DateTimeField(default=timezone.now)
    aceito_em = models.DateTimeField(null=True, blank=True)
    aceito_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="convites_aceitos", verbose_name="aceito por",
    )

    class Meta:
        verbose_name = "convite de equipe"
        verbose_name_plural = "convites de equipe"
        ordering = ("-criado_em",)

    def __str__(self) -> str:
        return f"{self.email} ({self.get_papel_display()})"

    @staticmethod
    def gerar_token() -> str:
        return secrets.token_urlsafe(32)

    @property
    def expirado(self) -> bool:
        return bool(self.expira_em and self.expira_em < timezone.now())

    def esta_valido(self) -> bool:
        return self.status == self.Status.PENDENTE and not self.expirado

    def aceitar(self, usuario):
        """Cria (ou ajusta) o vinculo do usuario e marca o convite como aceito."""
        vinculo, _ = VinculoUsuario.objects.get_or_create(
            usuario=usuario, rede=self.rede, unidade=self.unidade,
            defaults={"papel": self.papel, "ativo": True},
        )
        if vinculo.papel != self.papel or not vinculo.ativo:
            vinculo.papel = self.papel
            vinculo.ativo = True
            vinculo.save(update_fields=["papel", "ativo"])
        self.status = self.Status.ACEITO
        self.aceito_em = timezone.now()
        self.aceito_por = usuario
        self.save(update_fields=["status", "aceito_em", "aceito_por"])
        return vinculo
'''


def _garantir_imports(texto: str) -> str:
    """Garante import secrets / timezone / Papel no topo de core/models.py."""
    faltando = []
    if "import secrets" not in texto:
        faltando.append("import secrets")
    if "from django.utils import timezone" not in texto:
        faltando.append("from django.utils import timezone")
    if "from core.papeis import Papel" not in texto and "from .papeis import Papel" not in texto:
        faltando.append("from core.papeis import Papel")
    if not faltando:
        return texto
    linhas = texto.splitlines(keepends=True)
    ultimo = 0
    for i, linha in enumerate(linhas[:60]):
        if re.match(r"^(import |from )", linha):
            ultimo = i
    novo = "".join(faltando) + "\n"
    linhas.insert(ultimo + 1, novo)
    return "".join(linhas)


def patch_modelos() -> None:
    caminho = RAIZ / "core" / "models.py"
    texto = caminho.read_text(encoding="utf-8")
    if "class ConviteEquipe" in texto:
        print("core/models.py: ConviteEquipe ja existe")
        return
    texto = _garantir_imports(texto)
    if not texto.endswith("\n"):
        texto += "\n"
    caminho.write_text(texto + MODELO_CONVITE, encoding="utf-8")
    print("core/models.py: ConviteEquipe adicionado")


def patch_settings() -> None:
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    if '"gestao",' not in texto:
        texto = re.sub(r'(LOCAIS = \[\s*\n\s*"core",)', r'\1\n    "gestao",', texto, count=1)
        print("settings: app gestao registrado")
    else:
        print("settings: gestao ja registrado")
    if "gestao.context_processors.menu_do_painel" not in texto:
        texto = texto.replace(
            '"core.context_processors.contexto_rede",',
            '"core.context_processors.contexto_rede",\n                "gestao.context_processors.menu_do_painel",',
            1,
        )
        print("settings: context processor do menu registrado")
    caminho.write_text(texto, encoding="utf-8")


def patch_urls() -> None:
    """Insere a rota /gestao/ logo depois do admin (aceita aspas simples ou duplas)."""
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "gestao.urls" in texto:
        print("urls: rota /gestao/ ja existe")
        return
    padrao = re.compile(
        r"^(?P<indent>\s*)path\(\s*[\'\"]admin/[\'\"]\s*,\s*admin\.site\.urls\s*\),\s*$",
        re.MULTILINE,
    )
    novo_texto, trocas = padrao.subn(
        lambda m: (
            f'{m.group("indent")}path("admin/", admin.site.urls),\n'
            f'{m.group("indent")}path("gestao/", include("gestao.urls")),'
        ),
        texto,
        count=1,
    )
    if trocas == 0:
        raise SystemExit("ERRO: linha do admin nao encontrada em app/urls.py")
    if "gestao.urls" not in novo_texto:
        raise SystemExit("ERRO: patch de urls nao aplicou (verificacao falhou)")
    caminho.write_text(novo_texto, encoding="utf-8")
    print("urls: rota /gestao/ adicionada e verificada")


def patch_resolver() -> None:
    """Papeis de rede passam a enxergar TODAS as unidades por padrao (a unidade entra pela sessao)."""
    caminho = RAIZ / "core" / "tenancy.py"
    texto = caminho.read_text(encoding="utf-8")
    if "from core.papeis import" not in texto or "PAPEIS_DA_REDE," not in texto:
        linhas = texto.splitlines(keepends=True)
        ultimo = 0
        for indice, linha in enumerate(linhas[:60]):
            if linha.startswith("import ") or linha.startswith("from "):
                ultimo = indice
        linhas.insert(ultimo + 1, "from core.papeis import PAPEIS_DA_REDE\n")
        texto = "".join(linhas)
        print("tenancy: import de PAPEIS_DA_REDE adicionado")
    if "papeis_de_rede_do_usuario" in texto:
        caminho.write_text(texto, encoding="utf-8")
        print("tenancy: resolvedor ja ajustado")
        return
    antigo = (
        "        rede = rede_do_usuario(usuario)\n"
        "        if rede:\n"
        "            vinculo = (\n"
        "                VinculoUsuario.todos.filter(usuario=usuario, rede=rede, ativo=True)\n"
        '                .select_related("unidade")\n'
        "                .first()\n"
        "            )\n"
        "            return rede, (vinculo.unidade if vinculo else None)\n"
    )
    novo = (
        "        rede = rede_do_usuario(usuario)\n"
        "        if rede:\n"
        "            vinculos = VinculoUsuario.todos.filter(usuario=usuario, rede=rede, ativo=True)\n"
        '            papeis_de_rede_do_usuario = set(vinculos.values_list("papel", flat=True))\n'
        "            # Papeis de rede veem todas as unidades; a unidade entra pela sessao.\n"
        "            if usuario.is_superuser or (papeis_de_rede_do_usuario & PAPEIS_DA_REDE):\n"
        "                return rede, None\n"
        '            vinculo = vinculos.select_related("unidade").first()\n'
        "            return rede, (vinculo.unidade if vinculo else None)\n"
    )
    if antigo not in texto:
        raise SystemExit("ERRO: trecho do resolvedor nao encontrado em core/tenancy.py")
    caminho.write_text(texto.replace(antigo, novo, 1), encoding="utf-8")
    print("tenancy: papeis de rede agora veem todas as unidades")


def patch_middleware() -> None:
    """Em dev/teste, erro ao resolver o contexto de rede estoura (nao silencia a falha)."""
    caminho = RAIZ / "core" / "middleware.py"
    texto = caminho.read_text(encoding="utf-8")
    if "def ambiente_de_desenvolvimento" in texto:
        print("middleware: ja ajustado")
        return

    bloco_antigo = (
        "        except Exception:  # pragma: no cover - nunca derruba a requisicao por contexto\n"
        '            logger.exception("Falha ao resolver o contexto de rede")\n'
        "            limpar_contexto()\n"
        "            return self.get_response(request)\n"
    )
    bloco_novo = (
        "        except Exception:\n"
        '            logger.exception("Falha ao resolver o contexto de rede")\n'
        "            limpar_contexto()\n"
        "            if ambiente_de_desenvolvimento():\n"
        "                # Em dev/teste queremos ver o erro, nao um usuario deslogado em silencio.\n"
        "                raise\n"
        "            return self.get_response(request)\n"
    )
    if bloco_antigo in texto:
        texto = texto.replace(bloco_antigo, bloco_novo, 1)
        print("middleware: except trocado")
    elif "if ambiente_de_desenvolvimento():" not in texto:
        raise SystemExit("ERRO: bloco de except do middleware nao reconhecido")

    if "import os" not in texto:
        texto = texto.replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\nimport os\n",
            1,
        )

    definicao = (
        "\n\ndef ambiente_de_desenvolvimento() -> bool:\n"
        '    """True em dev/teste, onde falha de contexto de rede deve ser visivel."""\n'
        '    return os.environ.get("DJANGO_ENV", "") in {"dev", "test"}\n'
    )
    if "def ambiente_de_desenvolvimento" not in texto:
        texto = texto.rstrip("\n") + "\n" + definicao

    faltando = [
        item
        for item, presente in [
            ("import os", "import os" in texto),
            ("chamada", "if ambiente_de_desenvolvimento():" in texto),
            ("definicao", "def ambiente_de_desenvolvimento" in texto),
        ]
        if not presente
    ]
    if faltando:
        raise SystemExit(f"ERRO: patch do middleware incompleto: {faltando}")
    caminho.write_text(texto, encoding="utf-8")
    print("middleware: falha de contexto agora visivel em dev/teste (verificado)")


def patch_settings_teste() -> None:
    """Marca DJANGO_ENV=test nas configuracoes de teste."""
    caminho = RAIZ / "app" / "settings_env" / "test.py"
    texto = caminho.read_text(encoding="utf-8")
    if "DJANGO_ENV" in texto:
        print("settings de teste: ja marcado")
        return
    texto = 'import os\n\nos.environ.setdefault("DJANGO_ENV", "test")\n\n' + texto
    caminho.write_text(texto, encoding="utf-8")
    print("settings de teste: DJANGO_ENV=test marcado")


def patch_pyproject() -> None:
    """Inclui o app gestao na coleta de testes do pytest."""
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if "testpaths" not in texto:
        print("pyproject: sem testpaths (nada a fazer)")
        return
    if '"gestao"' in texto:
        print("pyproject: gestao ja citado")
        return
    novo, trocas = re.subn(
        r"(testpaths\s*=\s*\[)([^\]]*)(\])",
        lambda m: f'{m.group(1)}{m.group(2)}, "gestao"{m.group(3)}',
        texto,
        count=1,
    )
    if trocas == 0:
        print("pyproject: testpaths em formato inesperado")
        return
    caminho.write_text(novo, encoding="utf-8")
    print("pyproject: gestao adicionado aos testpaths")


if __name__ == "__main__":
    patch_modelos()
    patch_settings()
    patch_urls()
    patch_resolver()
    patch_middleware()
    patch_settings_teste()
    patch_pyproject()
    print("patch concluido")
