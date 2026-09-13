#!/usr/bin/env python3
"""Fase 8f: PoliticaDaRedeForm passa a declarar fields explicitos (DJ006)."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMPOS = ['trava_planos_e_precos', 'trava_politica_de_desconto', 'teto_de_desconto', 'trava_regua_de_cobranca', 'trava_contratos', 'trava_cancelamento', 'trava_templates_de_mensagem', 'permitir_sobrescrita_branding', 'dia_de_fechamento']
ALVO = '        exclude = ["rede", "atualizado_em"]'
NOVO = ("        fields = [" + chr(10)
        + "".join('            "' + nome + '",' + chr(10) for nome in CAMPOS)
        + "        ]")

caminho = RAIZ / "rede" / "forms.py"
texto = caminho.read_text(encoding="utf-8")
if ALVO in texto:
    if texto.count(ALVO) != 1:
        raise SystemExit("ERRO: mais de um exclude igual em rede/forms.py")
    caminho.write_text(texto.replace(ALVO, NOVO, 1), encoding="utf-8")
    print("rede/forms.py: fields explicitos com " + str(len(CAMPOS)) + " campo(s)")
else:
    print("rede/forms.py: nada a corrigir")
if ALVO in caminho.read_text(encoding="utf-8"):
    raise SystemExit("ERRO: exclude continua no arquivo")
print("patch fase 8f concluido")
