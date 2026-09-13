# Relatorio da fase 8 — SaaS multi-tenant da academia

Fase 8 e a maior do PRD. Este relatorio cobre o que foi entregue, com que evidencia, e o que ficou
aberto — sem maquiar numero.

## Blocos entregues

| Bloco | App | O que entrega | Testes |
| --- | --- | --- | --- |
| Documentos em PDF | `documentos` | Comprovante, carteirinha, contrato, recibo, demonstrativo de repasse e extrato de comissao, em PDF gerado pelo proprio projeto | 16 |
| Midia | `midia` | Envio em partes retomavel, conferencia por hash, processamento e entrega por URL assinada | 23 |
| CRM e retencao | `relacionamento` | Funil de captacao com conversao por origem e risco de evasao explicado linha a linha | 22 |
| Busca global | `busca` | Uma caixa para alunos, unidades, pagamentos, leads, midia, risco, comunicados e professores, com recorte por rede e papel | 10 |
| Catraca e parceiros | `acesso` | Decisao de acesso registrada, check-in automatico, anti-passback e conciliacao de extrato Wellhub/TotalPass | 27 |
| Cobranca recorrente | `cobranca` | Autorizacao de debito (Pix automatico), cobranca do mes, regua, retorno do banco e resumo | 26 |
| Fiscal (NFS-e) | `fiscal` | Configuracao fiscal, memoria de tributos, emissao em lote, cancelamento e PDF de conferencia | 22 |
| PDV e estoque | `pdv` | Produto, estoque por movimento, venda no balcao e indicadores | 18 |
| Assinatura digital | `documentos` | Envelope com corrente de hashes, assinatura na ordem, recusa, termo em PDF e verificacao | 14 |
| Design system | `design` | Tokens e componentes do painel, com vitrine em `/gestao/design/` | 8 |

Somando o bloco anterior (comissoes, gamificacao, NPS e PWA do aluno), a fase 8 chega a
**663 testes** na suite padrao, com `ruff` em zero e `manage.py check` sem problemas.

## Decisoes que valem registro

- **PDF sem dependencia externa.** Helvetica para rotulos e Courier para numeros (largura exata, o
  que permite alinhar dinheiro a direita). A primeira versao colidia a numeracao dos objetos e
  deixava pagina em branco: hoje a numeracao e explicita e ha teste de regressao.
- **Estoque como movimento, nao como numero.** Cada entrada, saida, ajuste e devolucao vira linha com
  motivo e saldo depois do lancamento.
- **Risco e conciliacao explicados.** Tanto o risco de evasao quanto a conciliacao de parceiro
  mostram a conta: motivos com pontos, cobranca sem acesso e acesso nao faturado.
- **Dinheiro com idempotencia.** Retorno de cobranca repetido nao gera segundo pagamento; nota
  fiscal nao duplica por pagamento; cobranca do mes nao duplica por competencia.
- **Assinatura com trilha.** Cada assinatura encadeia o hash do documento e o hash anterior; a
  verificacao refaz a corrente e acusa documento trocado, assinatura adulterada ou arquivo ausente.
- **Modo simulado declarado.** Gateway, provedor fiscal, PSP e emissao de nota: onde falta credencial,
  o sistema registra e avisa na tela, no PDF e na resposta guardada — nao inventa transacao real.
- **Isolamento por cliente em tudo.** Cada app novo passa por escopo de rede, e os modelos com escopo
  explicito entram na lista de excecao do teste de isolamento, com justificativa.

## O que ficou aberto

- **As telas do inventario §21.3.** A fundacao do design system esta pronta (tokens, componentes e
  vitrine) e as telas da fase 8 ja seguem esse padrao, mas as telas que ainda nao existem no painel
  continuam pendentes — e trabalho de frontend extenso, com o padrao ja definido.
- **Integracoes que dependem de terceiro:** PSP do Pix automatico, provedor de NFS-e, API do Wellhub
  (hoje por importacao de extrato), certificado ICP-Brasil para assinatura qualificada e catraca
  fisica (o endpoint e o contrato ja existem e estao testados).
- **Playwright:** o modulo `e2e` esta no repositorio e roda quando o navegador e as credenciais forem
  informados; hoje se pula na suite padrao.
- **Decisoes comerciais do §16** continuam abertas (base de calculo do repasse, visao do franqueado,
  Wellhub na fase ou add-on, app nativo ou PWA).

## Como rodar

```bash
cd /home/manoperalta/academia-saas
make subir && make migrar && make test
```

Producao segue intocada (`master` em `1f881ea`); todo o trabalho esta na branch
`feat/saas-multitenant`.
