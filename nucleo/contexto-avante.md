# Projeto Avante — contexto para o assistente

Referência `advisory`: apoio para entender o vocabulário das fontes e do PO. Nunca é fonte de
regra nem de decisão — regra só existe com `source_id` + `source_entry_digest` de uma fonte do
objeto. Cite este arquivo apenas como "contexto do projeto", nunca como autoridade.

## O projeto em cinco linhas

- Migração dos dados dos sistemas legados da Ipiranga (JDE, COSWIN, ABADI, Corporativo e outros)
  para o SAP S/4HANA.
- A DB (fornecedora do projeto) extrai, saneia e disponibiliza os dados prontos para carga, no
  Databricks.
- O parceiro de implementação SAP (Accenture) carrega os dados saneados e valida com as
  ferramentas de migração (IDQ, Cockpit/MDG).
- Os Key Users (Ipiranga) definem as regras funcionais e de negócio, homologam e aceitam.
- Datas: Go-Live em 01/01/2027; SIT2 em 24/08/2026; UAT entre out/2026 e nov/2026; Deploy em
  dez/2026; Hypercare em jan/2027.

## Glossário

| Termo | O que é |
|---|---|
| Mock (1, 1.5, 2, 3) | Rodada completa de simulação de carga. Mock 1/1.5 = base de referência dos arquivos; Mock 2 = espelho da 1.5, só carrega depois da validação da 1.5 pelo Key User; Mock 3 = já sobreposta aos testes integrados/UAT. Mínimo de duas rodadas antes de UAT e Produção. |
| SIT1, SIT2 | Testes integrados (System Integration Test); não rodam em paralelo. SIT2 = Migração SAP + Migração Base MDM + De-Para dos sistemas especialistas. |
| UAT | Teste de aceite pelo usuário, depois dos testes integrados. |
| IDQ, Cockpit, MDG | Ferramentas SAP de migração e carga, do lado do parceiro SAP; geram scores de qualidade da carga. |
| Data mapping | Template do Engenheiro de Migração com o de-para campo a campo; fonte típica de regras (`role: normative`). |
| Extrator | Código (Python/PySpark, muitas vezes notebook Databricks exportado como `.py`) que gera o arquivo de carga a partir dos legados saneados; fonte `observational` para a Etapa 04: mostra onde e como olhar, nunca o que deve dar. |
| Arquivo de carga | Saída do extrator da DB, gerada por pipeline no Databricks; é o que a Etapa 04 valida. |
| Base MDM | Base centralizadora no Databricks que recebe os dados migrados (Etapa 07). |
| Cutover | Regras e sequência da virada para produção; definidas pelo Key User. |
| IPC / Jira (Azure DevOps) | Controle de bugs e work items. |
| Evidências de auditoria | Cinco templates: extração/construção, saneamento, transformação e carga, validação inicial, validação final. Coletadas em todas as etapas. |

## As oito etapas de cada objeto

| Etapa | Nome | Onde o harness entra |
|---|---|---|
| 01 | Revisão de Regras — mapeamento e aprovação das regras de transformação | **Sim**: `/importar-fonte`, `/extrair-reuniao`, `/exportar-docx` |
| 02 | Extração e Saneamento — legados → Databricks | Não |
| 03 | Preparação do Arquivo — scripts e pipelines do arquivo de carga | Não |
| 04 | Validação — testes do arquivo gerado, bugs (IPC/Jira), golden data, problemas da Mock | **Sim**: `/validar-objeto` |
| 05 | Simulação e Carga — IDQ, Cockpit/MDG, carga no SAP | Não |
| 06 | Aceite — homologação funcional e aceite pelos Key Users | Não: o aceite do harness é o do PO sobre o comprovante, distinto do aceite do Key User |
| 07 | Base MDM — envio à base centralizadora | Não |
| 08 | Consumo — sistemas especialistas | Não |

## Módulos SAP no escopo (base para sugerir `--modulo`)

| Módulo | Objetos típicos |
|---|---|
| BP | Business Partner: Cliente, Fornecedor, Transportador |
| FI / CO | Banco, Centros, Contas, Ativo Fixo |
| MM | Material, Compras, Estoque |
| SD | Ordem de Venda, Condições de Preço, Listas Técnicas, Contratos e Bonificações |
| PM / EAM | Equipamento, Local de Instalação, Planos e Listas de Tarefas de manutenção |
| PS-CO | PEP, Definição de projeto, Orçamento, Redes |
| RE-FX | Edifício, Contrato Imobiliário, Locação |

## Papéis e autoridade

| Papel | O que faz | Peso do que diz numa fonte |
|---|---|---|
| Key User / Líder Avante (Ipiranga) | Define regras funcionais, de negócio e de cutover; esclarece dúvidas; valida nos testes integrados; aceita. | Autoridade para regra de negócio (`key_user`). |
| PO | Levanta regras de transformação, é o ponto de contato com o negócio, valida o arquivo de carga, apoia os Key Users. | No harness é quem confirma, autoriza e aceita (`po`). Uma regra dita pelo PO ainda é candidata até a cerimônia. |
| Líder de POs | Apoia a gestão dos POs, remove impedimentos, aciona as áreas de negócio. | Não define regra de negócio. |
| Consultor Funcional SAP | Apoia Key Users e migração em regras e validações funcionais. | Consultado: orienta, não decide. |
| Líder Técnico/Funcional | Decisões táticas e estratégicas, impedimentos escalados, negociação com sistemas especialistas. | Aprova (accountable) a revisão de regras; o que diz vira candidato até a cerimônia. |
| Engenheiro de Dados / Tech Lead (DB) | Extração, ingestão, extratores, arquivos de carga, pipelines, evidências. | Fato técnico sobre dado e pipeline; não define regra de negócio. |
| Engenheiro de Migração (parceiro SAP) | Template de data mapping, ferramentas de carga, scores IDQ/Cockpit/MDG. | Fato técnico sobre carga e template. |

RACI resumido: revisar regras — PO executa, Líder Técnico/Funcional aprova, Migração e Consultor
consultados; validar arquivo de carga — todos executam, Líder Técnico/Funcional aprova; validar
com Key User — PO, Consultor e Líder executam; evidências — PO, Engenharia e Migração.
