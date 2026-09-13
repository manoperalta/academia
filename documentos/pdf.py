"""Gerador de PDF em Python puro — sem dependencia externa.

Escolhas que importam:

* **Helvetica** para rotulos e **Courier** para numeros. Em Courier a largura de cada
  caractere e exatamente ``0,6 x tamanho``, o que permite alinhar dinheiro a direita com
  precisao, sem carregar a tabela de metricas do Helvetica.
* Texto em **WinAnsi** (latin-1), com escape de ``\\``, ``(`` e ``)``.
* Sem compressao: o arquivo fica maior, mas e legivel e conferivel a olho (util quando o
  documento vai para auditoria ou para um cliente que quer ver a memoria de calculo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

LARGURA_A4 = 595.28
ALTURA_A4 = 841.89
MARGEM = 42.0

FONTE_ATUAL: dict[str, str] = {"regular": "F1", "negrito": "F2", "mono": "F3", "mono_negrito": "F4"}
LARGURA_COURIER = 0.6
LARGURA_HELVETICA = 0.52


def escapar(texto: str) -> str:
    """Escapa o que o PDF trata como sintaxe dentro de uma string."""
    return limpar_para_pdf(texto).replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


#: Tipografia que nao cabe em WinAnsi e vira "?" no meio do documento do cliente.
_TIPOGRAFIA = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00a0": " ",
    "\u2022": "-",
}


def limpar_para_pdf(texto: str) -> str:
    """Normaliza tipografia e descarta o que WinAnsi (latin-1) nao representa."""
    for origem, destino in _TIPOGRAFIA.items():
        texto = texto.replace(origem, destino)
    return "".join(caractere if ord(caractere) <= 0xFF else "?" for caractere in texto)


def como_texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sim" if valor else "nao"
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return limpar_para_pdf(str(valor))


def moeda(valor: object) -> str:
    """Numero em Real, no padrao brasileiro."""
    numero = Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    inteiro, _, centavos = f"{abs(numero):.2f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    sinal = "-" if numero < 0 else ""
    return f"{sinal}R$ {'.'.join(grupos)},{centavos}"


def numero(valor: object, casas: int = 2) -> str:
    """Numero com virgula decimal (para percentuais e quantidades)."""
    quantizado = Decimal(str(valor or 0)).quantize(Decimal(1).scaleb(-casas))
    return f"{quantizado:.{casas}f}".replace(".", ",")


@dataclass
class DocumentoPDF:
    """Documento A4 com cabecalho, tabelas e rodape numerado."""

    titulo: str
    subtitulo: str = ""
    rodape: str = ""
    largura: float = LARGURA_A4
    altura: float = ALTURA_A4
    margem: float = MARGEM
    _paginas: list[list[str]] = field(default_factory=list, repr=False)
    _y: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self._paginas = [[]]
        self._y = self.altura - self.margem
        self.cabecalho()

    # ---------------------------------------------------------------- infraestrutura
    @property
    def pagina(self) -> int:
        return len(self._paginas)

    @property
    def largura_util(self) -> float:
        return self.largura - 2 * self.margem

    def _cmd(self, comando: str) -> None:
        self._paginas[-1].append(comando)

    def _largura(self, texto: str, tamanho: float, mono: bool) -> float:
        fator = LARGURA_COURIER if mono else LARGURA_HELVETICA
        return fator * tamanho * len(texto)

    def _garantir(self, altura: float) -> None:
        if self._y - altura < self.margem + 26:
            self.quebra_de_pagina()

    def _emitir_texto(
        self,
        texto: str,
        x: float,
        y: float,
        tamanho: float,
        fonte: str,
        cor: tuple[float, float, float],
    ) -> None:
        r, g, b = cor
        self._cmd(
            f"BT {r} {g} {b} rg /{FONTE_ATUAL[fonte]} {tamanho} Tf "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({escapar(texto)}) Tj ET"
        )

    # ---------------------------------------------------------------- elementos
    def cabecalho(self) -> None:
        self.texto(self.titulo, tamanho=17, fonte="negrito")
        if self.subtitulo:
            self.texto(self.subtitulo, tamanho=9.5, cor=(0.35, 0.35, 0.35))
        self.espaco(4)
        self.linha(espessura=1.1, cor=(0.15, 0.15, 0.15))
        self.espaco(10)

    def texto(
        self,
        conteudo: object,
        tamanho: float = 10,
        fonte: str = "regular",
        x: float | None = None,
        alinhamento: str = "esquerda",
        cor: tuple[float, float, float] = (0, 0, 0),
        recuo: float = 0.0,
    ) -> "DocumentoPDF":
        linha_texto = como_texto(conteudo)
        mono = fonte.startswith("mono")
        largura = self._largura(linha_texto, tamanho, mono)
        base = self.margem + recuo
        if alinhamento == "direita":
            posicao = base + self.largura_util - recuo - largura
        elif alinhamento == "centro":
            posicao = self.largura / 2 - largura / 2
        else:
            posicao = x if x is not None else base
        self._garantir(tamanho + 3)
        self._emitir_texto(linha_texto, posicao, self._y - tamanho, tamanho, fonte, cor)
        self._y -= tamanho + 4.5
        return self

    def par(self, rotulo: str, valor: object, tamanho: float = 10) -> "DocumentoPDF":
        """Uma linha rotulo/valor, com o valor em Courier (alinhavel)."""
        self._garantir(tamanho + 3)
        self._emitir_texto(
            como_texto(rotulo),
            self.margem,
            self._y - tamanho,
            tamanho,
            "regular",
            (0.28, 0.28, 0.28),
        )
        texto_valor = como_texto(valor)
        largura = self._largura(texto_valor, tamanho, mono=True)
        self._emitir_texto(
            texto_valor,
            self.margem + self.largura_util - largura,
            self._y - tamanho,
            tamanho,
            "mono",
            (0, 0, 0),
        )
        self._y -= tamanho + 5
        return self

    def secao(self, titulo: str) -> "DocumentoPDF":
        self.espaco(6)
        self.texto(titulo.upper(), tamanho=9, fonte="negrito", cor=(0.25, 0.25, 0.25))
        self.linha(espessura=0.5, cor=(0.75, 0.75, 0.75))
        self.espaco(4)
        return self

    def moldura(
        self,
        altura: float,
        cor: tuple[float, float, float] = (0.72, 0.74, 0.78),
        espessura: float = 0.8,
    ) -> None:
        """Retangulo vazado (borda) com a altura pedida, a partir do ponto atual."""
        r, g, b = cor
        self._cmd(
            f"{r} {g} {b} RG {espessura} w {self.margem:.2f} {self._y - altura:.2f} "
            f"{self.largura_util:.2f} {altura:.2f} re S"
        )

    def espaco(self, pontos: float = 6) -> "DocumentoPDF":
        self._y -= pontos
        return self

    def linha(
        self,
        espessura: float = 0.5,
        cor: tuple[float, float, float] = (0.6, 0.6, 0.6),
        largura: float | None = None,
        x: float | None = None,
    ) -> "DocumentoPDF":
        r, g, b = cor
        x1 = self.margem if x is None else x
        x2 = x1 + (self.largura_util if largura is None else largura)
        self._cmd(
            f"{r} {g} {b} RG {espessura} w {x1:.2f} {self._y:.2f} m {x2:.2f} {self._y:.2f} l S"
        )
        return self

    def caixa(self, altura: float, cor: tuple[float, float, float] = (0.95, 0.96, 0.98)) -> None:
        r, g, b = cor
        self._garantir(altura + 6)
        self._cmd(
            f"{r} {g} {b} rg {self.margem:.2f} {self._y - altura:.2f} {self.largura_util:.2f} "
            f"{altura:.2f} re f"
        )

    def tabela(
        self, colunas: list[tuple[str, float, str]], linhas: list[list[object]], tamanho: float = 9
    ) -> "DocumentoPDF":
        """Tabela com colunas ``(titulo, fracao da largura, alinhamento)``."""
        soma = sum(fracao for _, fracao, _ in colunas)
        larguras = [self.largura_util * fracao / soma for _, fracao, _ in colunas]
        self._garantir(tamanho * 2 + 12)
        self.texto(
            "  ".join(titulo for titulo, _, _ in colunas),
            tamanho=tamanho - 0.5,
            fonte="negrito",
            cor=(0.3, 0.3, 0.3),
        )
        self.linha(espessura=0.6, cor=(0.55, 0.55, 0.55))
        for linha_dados in linhas:
            self._garantir(tamanho + 6)
            x = self.margem
            for posicao, celula in enumerate(linha_dados):
                if posicao >= len(colunas):
                    break
                _titulo, _fracao, alinhamento = colunas[posicao]
                conteudo = como_texto(celula)
                fonte = "mono" if posicao else "regular"
                largura_celula = self._largura(conteudo, tamanho, fonte.startswith("mono"))
                if alinhamento == "direita":
                    x_celula = x + larguras[posicao] - largura_celula
                elif alinhamento == "centro":
                    x_celula = x + (larguras[posicao] - largura_celula) / 2
                else:
                    x_celula = x
                self._emitir_texto(conteudo, x_celula, self._y - tamanho, tamanho, fonte, (0, 0, 0))
                x += larguras[posicao]
            self._y -= tamanho + 5
        self.linha(espessura=0.5, cor=(0.75, 0.75, 0.75))
        self.espaco(4)
        return self

    def quebra_de_pagina(self) -> "DocumentoPDF":
        self._paginas.append([])
        self._y = self.altura - self.margem
        self.cabecalho()
        return self

    # ---------------------------------------------------------------- saida
    def _conteudo_da_pagina(self, comandos: list[str], numero: int, total: int) -> bytes:
        partes = list(comandos)
        rodape = self.rodape or self.titulo
        r, g, b = 0.45, 0.45, 0.45
        partes.append(
            f"{r} {g} {b} RG 0.5 w {self.margem:.2f} {self.margem - 12:.2f} m "
            f"{self.largura - self.margem:.2f} {self.margem - 12:.2f} l S"
        )
        partes.append(
            f"BT {r} {g} {b} rg /F1 8 Tf 1 0 0 1 {self.margem:.2f} {self.margem - 24:.2f} Tm "
            f"({escapar(rodape)}) Tj ET"
        )
        etiqueta = f"p\u00e1gina {numero} de {total}"
        largura = self._largura(etiqueta, 8, mono=False)
        partes.append(
            f"BT {r} {g} {b} rg /F1 8 Tf 1 0 0 1 {self.largura - self.margem - largura:.2f} "
            f"{self.margem - 24:.2f} Tm ({escapar(etiqueta)}) Tj ET"
        )
        return "\n".join(partes).encode("latin-1", "replace")

    def salvar(self) -> bytes:
        """Monta o arquivo: catalogo, arvore de paginas, cada pagina com seu conteudo e as fontes.

        A numeracao e fixa e contigua, para o xref sair na ordem e a pagina apontar sempre para
        o proprio fluxo de conteudo: pagina ``3 + 2*i``, conteudo ``4 + 2*i``.
        """
        total = len(self._paginas)
        objetos: dict[int, bytes] = {}
        filhos = []
        for indice, comandos in enumerate(self._paginas):
            numero_pagina = 3 + 2 * indice
            numero_conteudo = numero_pagina + 1
            conteudo = self._conteudo_da_pagina(comandos, indice + 1, total)
            base_fontes = 3 + 2 * total
            objetos[numero_pagina] = (
                f"{numero_pagina} 0 obj\n<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {self.largura:.2f} {self.altura:.2f}] "
                f"/Resources << /Font << /F1 {base_fontes} 0 R /F2 {base_fontes + 1} 0 R "
                f"/F3 {base_fontes + 2} 0 R /F4 {base_fontes + 3} 0 R >> >> "
                f"/Contents {numero_conteudo} 0 R >>\nendobj\n"
            ).encode("latin-1")
            objetos[numero_conteudo] = (
                f"{numero_conteudo} 0 obj\n<< /Length {len(conteudo)} >>\nstream\n".encode(
                    "latin-1"
                )
                + conteudo
                + b"\nendstream\nendobj\n"
            )
            filhos.append(f"{numero_pagina} 0 R")

        base_fontes = 3 + 2 * total
        objetos[1] = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        objetos[2] = (
            f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(filhos)}] /Count {total} >>\nendobj\n"
        ).encode("latin-1")
        for posicao, base in enumerate(("Helvetica", "Helvetica-Bold", "Courier", "Courier-Bold")):
            numero_fonte = base_fontes + posicao
            objetos[numero_fonte] = (
                f"{numero_fonte} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /{base} "
                f"/Encoding /WinAnsiEncoding >>\nendobj\n"
            ).encode("latin-1")

        maior = max(objetos)
        faltando = [numero for numero in range(1, maior + 1) if numero not in objetos]
        if faltando:
            raise ValueError(f"numeracao de objetos incompleta no PDF: faltam {faltando}")

        saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        deslocamentos: dict[int, int] = {}
        for numero in range(1, maior + 1):
            deslocamentos[numero] = len(saida)
            saida.extend(objetos[numero])

        inicio_xref = len(saida)
        saida.extend(f"xref\n0 {maior + 1}\n".encode("latin-1"))
        saida.extend(b"0000000000 65535 f \n")
        for numero in range(1, maior + 1):
            saida.extend(f"{deslocamentos[numero]:010d} 00000 n \n".encode("latin-1"))
        saida.extend(
            f"trailer\n<< /Size {maior + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode(
                "latin-1"
            )
        )
        return bytes(saida)
