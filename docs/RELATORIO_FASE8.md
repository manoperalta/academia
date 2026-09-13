# Relatorio da fase 8 — SaaS multi-tenant da academia

Fase 8 e a maior do PRD: frontend, API, integracoes e as telas de operacao. Este relatorio cobre o
que foi entregue, com que evidencia, e o que ficou aberto — sem maquiar numero.

## Blocos entregues

| Bloco | App | O que entrega |
| --- | --- | --- |
| Documentos em PDF | `documentos` | Comprovante, carteirinha, contrato, recibo, demonstrativo de repasse e extrato de comissao, em PDF gerado pelo proprio projeto |
| Midia | `midia` | Envio em partes retomavel, conferencia por hash, processamento e entrega por URL assinada |
| CRM e retencao | `relacionamento` | Funil de captacao com conversao por origem e risco de evasao explicado linha a linha |
| Busca global | `busca` | Uma caixa para alunos, unidades, pagamentos, leads, midia, risco, comunicados e professores, com recorte por rede e papel |
| Catraca e parceiros | `acesso` | Decisao de acesso registrada, check-in automatico, anti-passback e conciliacao de extrato Wellhub/TotalPass |
| Cobranca recorrente | `cobranca` | Autorizacao de debito (Pix automatico), cobranca do mes, regua, retorno do banco, resumo e tela de inadimplencia por faixa |
| Fiscal (NFS-e) | `fiscal` | Configuracao fiscal, memoria de tributos, emissao em lote, cancelamento e PDF de conferencia |
| PDV e estoque | `pdv` | Produto, estoque por movimento, venda no balcao e indicadores |
| Assinatura digital | `documentos` | Envelope com corrente de hashes, assinatura na ordem, recusa, termo em PDF e verificacao |
| Treinos e avaliacao | `treinos` | Prescricao com exercicios na ordem, execucao com carga, progresso e avaliacao fisica com evolucao |
| Painel do professor | `painel_do_professor` | Agenda, turma com chamada e ocorrencia, prescricao, alunos, avaliacoes e comissoes |
| Portal do aluno | `portal_do_aluno` | Agenda com lista de espera, pagamentos, ficha de saude e LGPD |
| Conta e suporte | `conta` | Perfil, senha, redefinicao por e-mail, sessoes ativas e chamados de suporte |
| Design system | `design` | Tokens e componentes do painel, com vitrine em `/gestao/design/` |
| Telas finais | `plataforma`, `rede` | Auditoria da plataforma (com CSV) e comparativo de unidades |

Todas as **64 telas** do inventario da secao 21.3 do PRD estao mapeadas e atendidas — o detalhe, tela
por tela com a rota, esta em `docs/INVENTARIO_TELAS.md`.

## Evidencia

- Suite completa verde, `ruff` em zero e `manage.py check` sem problemas.
- Cada bloco foi publicado em commit proprio, com a suite rodando antes do commit (nunca com `tail`
  engolindo o codigo de saida).
- Producao **intocada**: `master` continua no ultimo commit de producao; todo o trabalho esta na
  branch `feat/saas-multitenant`.

## Decisoes que valem registro

- **PDF sem dependencia externa.** Helvetica para rotulos e Courier para numeros (largura exata, o
  que permite alinhar dinheiro a direita). A primeira versao colidia a numeracao dos objetos e
  deixava pagina em branco: hoje a numeracao e explicita e ha teste de regressao.
- **Estoque como movimento, nao como numero.** Cada entrada, saida, ajuste e devolucao vira linha com
  motivo e saldo depois do lancamento.
- **Risco e conciliacao explicados.** O risco de evasao mostra os motivos com pontos; a conciliacao
  de parceiro mostra cobranca sem acesso e acesso nao faturado.
- **Dinheiro com idempotencia.** Retorno de cobranca repetido nao gera segundo pagamento; nota fiscal
  nao duplica por pagamento; cobranca do mes nao duplica por competencia.
- **Assinatura com trilha.** Cada assinatura encadeia o hash do documento e o hash anterior; a
  verificacao refaz a corrente e acusa documento trocado, assinatura adulterada ou arquivo ausente.
- **Modo simulado declarado.** Onde falta credencial (PSP, provedor fiscal, gateway), o sistema
  registra e avisa na tela, no PDF e na resposta guardada — nao inventa transacao real.
- **Manager global com escopo explicito** em catraca, portal do aluno, cobranca e painel do professor:
  essas decisoes acontecem fora do contexto de tenant do painel, e o manager escopado escondia linha.
- **Isolamento por cliente em tudo.** Cada app novo passa por escopo de rede, e os modelos com escopo
  explicito entram na lista de excecao do teste de isolamento, com justificativa.

## O que ficou aberto

- **Integracoes dependentes de terceiro:** PSP do Pix automatico, provedor de NFS-e, API do Wellhub
  (hoje por importacao de extrato), certificado ICP-Brasil e catraca fisica. O contrato e os testes do
  lado da rede ja existem.
- **Playwright:** o modulo `e2e` esta no repositorio e roda quando o navegador e as credenciais forem
  informados; hoje se pula na suite padrao.
- **Decisoes comerciais da secao 16** continuam abertas (base de calculo do repasse, visao do
  franqueado, Wellhub na fase ou add-on, app nativo ou PWA).

## Como rodar

```bash
cd /home/manoperalta/academia-saas
make subir && make migrar && make test
```
