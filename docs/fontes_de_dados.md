# Fontes de dados

Data da pesquisa: 2026-10-25. Cada fonte está classificada pelo que **foi de fato verificado**.

Legenda: **Arquivo** = conferido abrindo o arquivo; **Página** = conferido na página oficial;
**Terceiros** = só vi em site que não é do responsável pela fonte; **Não verificado**.

## Em uso

| Fonte | Responsável | Verificação | O que foi confirmado | Pendências |
|---|---|---|---|---|
| TACO, 4ª ed. (2011), Excel | NEPA/Unicamp | **Arquivo** + Página | 3 abas; aba principal com 597 alimentos (ids 1 a 597, sem repetição) em 15 grupos; 26 colunas de nutrientes (a base "por 100 g" consta em fontes secundárias; não achei essa frase na legenda do arquivo); abas de ácidos graxos (423 alimentos) e aminoácidos (26). Legenda: `NA` = não aplicável, `Tr` = traço, `*` = análise em reavaliação, vazio = análise não solicitada | Termos de uso não encontrados. Defeitos: id 540 com nome `L`; célula AA424 (id 373) com texto `,0,02`; leite integral (458) e mais 3 alimentos sem energia (`*`) |

## Consulta manual (não carregar em massa)

| Fonte | Responsável | Verificação | O que foi confirmado | Pendências |
|---|---|---|---|---|
| TBCA 7.3 | USP/FoRC | **Página** | Busca online gratuita, valores por 100 g, medidas caseiras com volumes de utensílios, tipos de dado (analítico, calculado, atribuído, assumido). `NA` aqui significa "não analisado" (diferente da TACO) | A seção "Como Citar" é contraditória: incentiva divulgação sem fins comerciais, mas diz não permitir reprodução total ou parcial nem alteração. Não achei download da base principal, só PDFs de tabelas complementares. Contagem de alimentos diverge entre páginas (a oficial cita mais de 5.700 na 7.2 e uma notícia cita cerca de 1.800 in natura mais 306 preparações na 7.3). Pedir autorização por e-mail (tbca.contato@usp.br) |

## Reserva

| Fonte | Responsável | Verificação | O que foi confirmado | Pendências |
|---|---|---|---|---|
| USDA FoodData Central | USDA (EUA) | **Página** | Dados em domínio público (CC0); API exige chave gratuita (limite padrão de 1.000 requisições por hora por IP); downloads em JSON. Em inglês, alimentos americanos | Só usar para alimentos sem equivalente brasileiro |

## Candidatas para receitas

| Fonte | Verificação | O que foi confirmado | Problemas |
|---|---|---|---|
| RecipeNLG | **Terceiros** (cartão do Hugging Face e catálogo TFDS) | Cerca de 2,2 milhões de receitas, em inglês; campos de título, ingredientes, instruções, link, fonte e entidades extraídas | Quantidades em texto livre; uso descrito como pesquisa e educação não comerciais, mas outra listagem diz "licença desconhecida". Não abri o site oficial |
| Food.com Recipes and Interactions (Kaggle) | **Terceiros** | Cerca de 270 mil receitas e 1,4 milhão de interações (outra versão no Kaggle lista 522.517 receitas) | Em inglês, unidades americanas; licença não confirmada |
| afrodite.json (GitHub) | **Terceiros** | 8.183 receitas em português, obtidas por web crawler | Origem do conteúdo e licença desconhecidas: risco de direitos autorais. Não usar sem autorização clara |

Decisão (D03): receitas do chatbot virão de uma base curada pelo autor, com fonte registrada.
RecipeNLG e Food.com ficam só para a análise exploratória (CRISP-DM, Data Understanding).

## Orientação alimentar

| Fonte | Verificação | Observações |
|---|---|---|
| Guia Alimentar para a População Brasileira, 2ª ed. (2014), Ministério da Saúde | **Terceiros** (material de apoio descreve como não prescritivo) | Verificar se há versão mais recente e abrir o PDF oficial antes de citar |
| Anvisa (alérgenos e rotulagem) | **Não verificado** | Necessário antes de definir os filtros de alergia |

## Preços de alimentos

Nada utilizável encontrado. Só achei preços ao produtor (Conab e Cepea, em publicação do Ministério da
Agricultura) e índices agregados, que não permitem estimar o custo de uma compra de varejo.
Consequência: a versão 1 não terá orçamento em reais (o sistema contará itens a comprar).
