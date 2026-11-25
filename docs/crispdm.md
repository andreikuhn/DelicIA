# CRISP-DM: registro do que foi feito

Este documento só registra o que existe. Última atualização: 2026-10-25 (passo 4 do plano em andamento; busca e porções adiantadas, banco SQLite adiado, ver D20).

| Fase | Situação | O que foi feito de fato | Evidências | Falta |
|---|---|---|---|---|
| 1. Business Understanding | rascunho | Problema, público, escopo da v1 e critérios de sucesso definidos na especificação do projeto | `docs/decisoes.md` (D01) | Objetivos mensuráveis e riscos formalizados no relatório |
| 2. Data Understanding | em andamento | Fontes pesquisadas e classificadas por grau de verificação. Excel da TACO inspecionado: 597 alimentos, 15 grupos, 26 colunas de nutrientes, marcadores de valor ausente contados | `docs/fontes_de_dados.md`; `src/nutrimesa/taco_source.py` | EDA completa (distribuições, cobertura por grupo); amostra de RecipeNLG/Food.com; verificar termos de uso |
| 3. Data Preparation | em andamento | Vocabulário de 96 ingredientes, 188 sinônimos e mapa para a TACO (todos pesquisados no Excel: 63 alta, 28 média, 9 baixa, 3 ambíguos, 18 sem correspondência), com validação automática. Formato das receitas definido e 68 receitas-exemplo em rascunho, validadas contra o vocabulário | `data/vocab/`; `data/recipes/`; `src/nutrimesa/recipes.py`; `tests/` | Revisão das 68 receitas; densidade do leite de coco; fonte alternativa para o leite (em reavaliação na TACO) |
| 4. Modeling | em andamento | Cardápio da semana com metas de calorias e vitaminas (VDR Anvisa); nutrientes por porção (TACO); detecção de intenção (cumprimento, fora do escopo etc.); busca por ingredientes com sinônimos, correção de digitação, termos ambíguos, despensa e pontuação; calculadora de porções com avisos; conversa com LLM via tool use, com Ollama local (padrão) ou Claude (testada com clientes falsos, ainda sem conversa real) | `src/nutrimesa/search.py`; `portions.py`; `tools.py`; `chat.py`; `tests/`; `experimentar.py`; `conversar.py` | Primeira conversa real com o modelo local, filtro de alergias, nutrição |
| 5. Evaluation | não iniciada | (nada ainda) | (nada ainda) | Testes funcionais, de cálculo, de recomendação e de conversa |
| 6. Deployment | não iniciada | README e instruções de instalação iniciais | `README.md` | Interface de chat, execução reproduzível completa |

## Fatos medidos no Excel da TACO (aba principal)

- Células que não são número nos 597 alimentos: `Tr` 1.863, `NA` 907, `*` 76, espaço em branco 93, ` Tr` (com espaço) 2, um valor malformado.
- Energia sem número em 6 alimentos (4 com `*`, 2 com `NA`).
- Fibra alimentar numérica em 355 dos 597 alimentos (`NA` em 221).
