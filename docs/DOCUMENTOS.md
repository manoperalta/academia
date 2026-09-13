# Documentos de negocio em PDF (fase 8)

## Por que um gerador proprio

O projeto nao tem dependencia de PDF (`requirements.txt` traz Django, pillow e requests), e adicionar
uma biblioteca traria peso e um ponto de falha a mais na instalacao. O gerador em
`documentos/pdf.py` escreve o PDF direto, em Python puro:

- **Helvetica** para rotulos e **Courier** para numeros. Em Courier cada caractere mede exatamente
  `0,6 x tamanho`, o que permite alinhar dinheiro a direita com precisao, sem carregar a tabela de
  metricas do Helvetica.
- Texto em **WinAnsi (latin-1)**, com normalizacao de tipografia: travessao, aspas curvas e
  reticencias viram equivalente ASCII, e o que nao cabe em latin-1 vira `?` em vez de derrubar o
  documento.
- **Sem compressao**: o arquivo fica maior, mas e legivel e conferivel — util quando o documento vai
  para auditoria ou quando o cliente quer inspecionar a memoria de calculo.
- Quebra de pagina automatica, cabecalho repetido e rodape numerado (`pagina N de M`).

## Armadilha que vale registrar

A primeira versao numerava os objetos de conteudo num segundo passo e a numeracao **colidia com a das
paginas**: a pagina 2 saia vazia e a 1 recebia todo o texto. A montagem hoje e explicita — pagina
`3 + 2*i`, conteudo `4 + 2*i`, fontes no fim — com uma verificacao que falha se faltar numero na
sequencia. O teste `test_pdf_multi_pagina_desenha_o_conteudo_da_segunda_pagina` existe para isso nao
voltar, e `test_xref_aponta_para_os_objetos_declarados` confere cada deslocamento do indice.

## Documentos

| Documento | Rota | Conteudo |
| --- | --- | --- |
| Comprovante de matricula | `gestao/documentos/matricula/<pk>/` | aluno, situacao, unidade, plano vigente e vigencia |
| Carteirinha | `gestao/documentos/carteirinha/<pk>/` | identidade da rede, matricula, unidade, validade |
| Contrato de adesao | `gestao/documentos/contrato/<pk>/` | partes, objeto, condicoes, LGPD e linhas de assinatura |
| Recibo de pagamento | `gestao/documentos/recibo/<pk>/` | valor, data, periodo coberto, forma |
| Demonstrativo de repasse | `gestao/documentos/repasse/<pk>/` | memoria de calculo do royalty e do fundo, com o hash |
| Extrato de comissao | `gestao/documentos/comissao/<pk>/` | linhas da apuracao, total, saldo e hash |
| Minha carteirinha (PWA) | `aluno/carteirinha/` | o proprio aluno baixa a dele |

O contrato sai marcado como **minuta**: e modelo para revisao juridica, nao peca assinada.

## Seguranca

Todo download passa por tres crivos: sessao (mixin do painel), **modulo permitido** (o mesmo da tela
equivalente — financeiro para recibo, repasses para o demonstrativo, comissoes para o extrato) e
**escopo da rede**: objeto de outra rede responde **404**, nunca um PDF de outro cliente.

## Verificacao

- 16 testes do app, incluindo isolamento entre redes, 403 por papel, 404 para visitante, o conteudo
  real de cada documento (valores, datas, hash) e a estrutura do PDF (catalogo, xref, paginas).
- Validacao externa: os PDFs foram abertos e renderizados com **pypdfium2** (biblioteca independente),
  que extraiu o texto exatamente como esperado e desenhou as paginas sem sobreposicao ou corte.
- Demonstracao com dados reais: os seis documentos foram gerados a partir de uma rede de
  demonstracao (aluno, plano, pagamento e apuracao de comissao de verdade) e a rede foi removida no
  fim.

## Pendente

- Assinatura digital do contrato (depende de certificado e decisao comercial).
- Marca dagua com o logo da rede: exige embutir imagem no PDF (o gerador ainda nao desenha imagem).
- Codigo de barras/QR para catraca: entra junto com a integracao de catraca (secao 16).
