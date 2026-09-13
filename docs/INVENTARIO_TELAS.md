# Inventario de telas do PRD (secao 21.3) — cobertura

As 64 telas do inventario, cada uma com a rota que a atende hoje no sistema. Status:
**pronta** (funcionando, com teste), **parcial** (existe, com alguma parte pendente).

## Autenticacao e conta (7)

| Tela | Rota | Status |
| --- | --- | --- |
| Login | `login` (accounts) | pronta |
| Definir/alterar senha | `conta:senha` | pronta |
| Recuperar senha | `conta:senha_redefinir` (+ confirmar/redefinida) | pronta |
| Selecionar rede/unidade | `gestao:selecionar_unidade`, `gestao:vinculo_alternar` | pronta |
| Meu perfil | `conta:perfil` | pronta |
| 2FA | `governanca:dois_fatores`, `dois_fatores_cadastrar`, `dois_fatores_codigos` | pronta |
| Sessoes ativas | `conta:sessoes` (+ sair dos outros aparelhos) | pronta |

## Painel da plataforma — SafeStack (9)

| Tela | Rota | Status |
| --- | --- | --- |
| Visao geral (MRR/ARR/churn) | `plataforma:metricas` | pronta |
| Redes (lista/filtro) | `plataforma:tenants` | pronta |
| Rede (detalhe) | `plataforma:tenant_ficha` | pronta |
| Rede (formulario) | `plataforma:tenant_novo`, `tenant_editar`, `tenant_acao` | pronta |
| Pacotes | `plataforma:pacotes`, `pacote_novo`, `pacote_editar` | pronta |
| Faturas da plataforma | `plataforma:faturas`, `fatura_baixar/cobrar/cancelar/simular_pagamento` | pronta |
| Cobranca e inadimplencia | `plataforma:regua`, `tenant_faturar` | pronta |
| Impersonation | `plataforma:impersonar`, `sair_impersonacao` | pronta |
| Auditoria da plataforma | `plataforma:auditoria` (+ CSV) | pronta |

## Painel da rede (10)

| Tela | Rota | Status |
| --- | --- | --- |
| Dashboard da rede | `rede:painel` | pronta |
| Unidades (lista/form/detalhe) | `rede:unidades`, `unidade_criar/editar/encerrar` | pronta |
| Comparativo de unidades | `rede:comparativo` | pronta |
| Metas | `rede:metas`, `meta_criar`, `gestao:metas` | pronta |
| Repasses/royalties | `rede:repasses`, `repasse_detalhe`, `repasse_csv`, `repasse_acao` | pronta |
| Governanca | `rede:governanca`, `rede:regras`, `regra_criar/editar` | pronta |
| Catalogo central | `rede:catalogo` | pronta |
| Comunicados | `rede:comunicados`, `comunicado_criar`, `comunicado_ler` | pronta |
| Onboarding de unidade | `gestao:onboarding`, `rede:unidade_template`, `gestao:unidade_template` | pronta |
| Migracao de rede | `rede:importar`, `gestao:transferencias`, `rede:transferencias` | pronta |

## Painel da unidade — operacao (24)

| Tela | Rota | Status |
| --- | --- | --- |
| Home da unidade | `gestao:visao_geral`, `gestao:painel` | pronta |
| Alunos (lista) | `gestao:alunos` (+ acoes em massa) | pronta |
| Aluno (detalhe) | `gestao:aluno_detalhe` | pronta |
| Aluno (formulario) | `gestao:aluno_novo`, `aluno_editar`, `aluno_arquivar` | pronta |
| Ficha de saude | `gestao:ficha_saude_detail`, `alunos-ficha-saude` | pronta |
| Avaliacao fisica | `professor:avaliacoes`, `professor:registrar_avaliacao`, `treinos:minha_evolucao` | pronta |
| Treinos do aluno | `professor:treinos`, `professor:treino`, `professor:prescrever`, `treinos:meus_treinos` | pronta |
| Importar alunos | `gestao:importar`, `gestao:importar_modelo` | pronta |
| Exportar alunos | `gestao:relatorio_alunos_csv`, `gestao:relatorio_pagamentos_csv` | pronta |
| Professores (lista/form/detalhe) | `gestao:professores`, `professor_novo/editar/arquivar` | pronta |
| Equipe e permissoes | `gestao:equipe`, `convite_novo`, `convite_cancelar`, `convite_aceitar` | pronta |
| Aulas (biblioteca) | `gestao:aulas`, `aula_nova/editar/arquivar` | pronta |
| Aula (formulario) | `gestao:aula_nova`, `midia:enviar` (video em partes) | pronta |
| Midia | `midia:lista`, `midia:player` | pronta |
| Turmas/Paineis (lista/form) | `gestao:painel`, `painel_novo/editar`, `turmas-list` (API) | pronta |
| Agenda | `gestao:agenda`, `agenda_list` | pronta |
| Agendamentos | `agendamentos-list` (API), `portal:agenda` (aluno) | pronta |
| Check-in | `gestao:agendamento_checkin`, `acesso:painel`, `aluno:checkin` | pronta |
| Planos | `gestao:planos`, `plano_novo/editar/arquivar/mudar` | pronta |
| Matriculas/Contratos | `matriculas-list` (API), `documentos:contrato`, `documentos:envelope`, `documentos:assinar` | pronta |
| Cobrancas | `financeiro`, `pagamento_novo`, `cobranca:gerar`, `cobranca:autorizacoes` | pronta |
| Pagamentos e conciliacao | `gestao:pagamentos`, `pagamento_baixar`, `gestao:repasses` | pronta |
| Inadimplencia | `cobranca:inadimplencia`, `api:inadimplencia` | pronta |
| Relatorios (9+) | `gestao:relatorios`, `relatorio_geral/financeiro/aluno/professor/usuarios/extrato` | pronta |
| Comunicacao | `gestao:comunicacao`, `comunicacao_teste`, `comunicados-list` (API) | pronta |
| Notificacoes automaticas | `criar_notificacao`, `enviar_notificacao_atraso`, `conta:fila_suporte` | pronta |
| Configuracoes da unidade | `gestao:identidade`, `gestao:dominio`, `plataforma:config` | pronta |
| Meu plano (pacote) | `gestao:plano`, `gestao:plano_mudar` | pronta |
| Auditoria | `gestao:auditoria`, `plataforma:auditoria` | pronta |
| LGPD | `gestao:privacidade`, `privacidade_exportar/anonimizar/solicitar`, `api:lgpd` | pronta |
| Suporte | `conta:chamados`, `conta:chamado`, `conta:fila_suporte` | pronta |

## Portal do aluno (8) e app do professor (6)

| Tela | Rota | Status |
| --- | --- | --- |
| Aluno — Home | `aluno:inicio` | pronta |
| Aluno — Meus treinos | `treinos:meus_treinos`, `treinos:meu_treino`, `treinos:registrar_execucao` | pronta |
| Aluno — Agenda | `portal:agenda`, `portal:agendar`, `portal:espera`, `portal:cancelar_agendamento` | pronta |
| Aluno — Meus pagamentos | `portal:pagamentos`, `documentos:recibo` | pronta |
| Aluno — Minha ficha de saude | `portal:ficha` | pronta |
| Aluno — Minha evolucao | `treinos:minha_evolucao` | pronta |
| Aluno — Perfil/notificacoes | `portal:perfil`, `portal:meus_dados` | pronta |
| Aluno — Gamificacao | `aluno:pontos`, `gamificacao:ranking`, `gamificacao:conquistas` | pronta |
| Professor — Minha agenda | `professor:agenda` | pronta |
| Professor — Minha turma | `professor:turma`, `professor:chamada`, `professor:ocorrencia` | pronta |
| Professor — Prescricao | `professor:treinos`, `professor:treino`, `professor:prescrever` | pronta |
| Professor — Meus alunos | `professor:alunos`, `professor:aluno` | pronta |
| Professor — Avaliacoes | `professor:avaliacoes`, `professor:registrar_avaliacao` | pronta |
| Professor — Comissoes | `professor:comissoes`, `remuneracao:extrato` | pronta |

## O que depende de terceiro (nao da para fechar so com codigo)

- **Pix automatico real**: o fluxo, o retorno e a conciliacao estao prontos e testados; falta o PSP.
- **NFS-e real**: calculo, memoria, emissao em lote, cancelamento e PDF prontos; falta o provedor.
- **Wellhub/TotalPass por API**: hoje a conciliacao e por extrato importado (funciona e aponta divergencia).
- **Assinatura com certificado ICP-Brasil**: a assinatura eletronica com trilha verificavel esta pronta.
- **Catraca fisica**: o endpoint, o token e a decisao registrada estao prontos e testados.
- **Playwright**: o modulo `e2e` roda quando o navegador e as credenciais forem informados.

## Decisoes comerciais ainda abertas (secao 16 do PRD)

Base de calculo do repasse (bruto ou liquido), o que o franqueado ve do consolidado da rede,
Wellhub/TotalPass na fase ou como add-on pago, e app nativo contra PWA.
