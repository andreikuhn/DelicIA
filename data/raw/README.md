# data/raw — dados originais (não versionados)

O conteúdo desta pasta é ignorado pelo Git (veja `.gitignore`), exceto este arquivo e o `.gitkeep`.

## Excel da TACO

- Fonte: NEPA/Unicamp, *Tabela Brasileira de Composição de Alimentos (TACO)*, 4ª edição revisada e ampliada (2011).
- Página oficial: https://nepa.unicamp.br/tabela-brasileira-de-composicao-de-alimentos-4a-edicao/
- Link do Excel nessa página: https://www.nepa.unicamp.br/arquivo/uploads/taco-4a-edicao/taco-4a-edicao-2/
  (em 2026-10-25 ele redirecionava para um arquivo `Taco-4a-Edicao.xlsx` no mesmo site)
- Salve como: `data/raw/Taco-4a-Edicao.xlsx`

### Arquivo usado na conferência do vocabulário (2026-10-25)

| Item | Valor |
|---|---|
| Nome | `Taco-4a-Edicao.xlsx` |
| Tamanho | 322.270 bytes |
| SHA-256 | `a66b8ec528daeabc63bc2b015fc9bd8c6d76b941c2fc0ed93a4311d449302d14` |

Se você baixar de novo e o SHA-256 for diferente, o teste de consistência avisa (não falha).
Os links do NEPA podem mudar: uma notícia da Unicamp de junho de 2026 informa a aprovação de um novo centro
que reúne Cepagri, NEPA e Nepam. Guarde uma cópia local do arquivo e a data do download.

## Complemento da TBCA (leite integral, decisão D47)

`tbca_complementos.csv` completa o que a TACO não informa. Hoje só o leite integral (TACO 458, "em
reavaliação"). Crie o arquivo à mão, copiando os números da página da TBCA:

- Fonte: TBCA - Tabela Brasileira de Composição de Alimentos, USP/FoRC, versão 7.3, 2025 (www.tbca.net.br).
- Item: BRC0043G, "Leite, vaca, integral, fluído, pasteurizado, Brasil (média de diferentes amostras)",
  consultado em 2026-10-26.
- Colunas: `taco_id,tbca_codigo,tbca_nome,energia,proteina,lipideos,carboidrato,vitamina_a`, com os
  valores por 100 g (energia em kcal, vitamina A em mcg RAE), ponto como separador decimal.

Sem esse arquivo o projeto continua funcionando: o leite volta a deixar a energia "parcial". A TBCA
proíbe reprodução total ou parcial, por isso os números não vão para o Git; o site publica só os
totais por receita (`data/nutrientes_receitas.csv`), que citam a fonte.

### Por que o arquivo não vai para o Git

Os termos de uso da TACO ainda não foram confirmados (nenhuma licença aparece na página do NEPA nem no
arquivo). Até confirmar, o repositório traz só as instruções de download e o que foi derivado delas
(`data/vocab/`, que não contém valores nutricionais).
