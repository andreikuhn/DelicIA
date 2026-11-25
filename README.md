# DelícIA

*Antes chamado NutriMesa (decisão D43). A pasta e o pacote Python continuam com o nome antigo
(`nutrimesa`), para não quebrar importações.*

Assistente de cozinha em português que ajuda a descobrir o que cozinhar com os ingredientes que a
pessoa já tem, cria receitas do tamanho certo, explica o preparo e monta o cardápio da semana na
medida da dieta dela. Projeto acadêmico individual de Andrei Jhulian Tabalipa Kuhn, da disciplina
*LLM Projects*.

O Gemini cria as receitas, as quantidades, a estimativa de nutrientes e o cardápio (D56). O código
decide a intenção da mensagem, confere cada resposta contra as restrições do perfil, calcula IMC,
metas de calorias, proteína e água, valida o JSON do cardápio e guarda tudo no banco.

**Planejamento:** [`docs/relatorio_planejamento.pdf`](docs/relatorio_planejamento.pdf) ·
**Decisões de projeto (D01 a D77):** [`docs/decisoes.md`](docs/decisoes.md)

## Como executar (versão da entrega final)

Requer Python 3.12 ou 3.13 e uma chave gratuita do Gemini (Google AI Studio).

1. Instale as dependências (uma vez):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copie `.env.example` para `.env` e preencha `LLM_PROVIDER=gemini` e `GEMINI_API_KEY`.
   O `.env` não vai para o Git.

3. Abra o site:

   - **Windows:** dois cliques em `iniciar_local.bat`;
   - **qualquer sistema:** `python -m streamlit run app.py --server.port 8505`.

   Abra **http://localhost:8505**. A primeira abertura leva de 20 a 30 segundos.

Por padrão o site usa o **banco local** (`BANCO=local`, D76): contas, perfis, conversas, cardápios e
o que a pessoa comeu ficam em `data/delicia_local.sqlite`, criado sozinho na primeira vez (fora do
Git). As senhas são guardadas com hash PBKDF2. Sem servidor de e-mail, o código de recuperação de
senha aparece na janela do terminal que roda o site.

Para voltar ao Supabase (versão publicada antes), ponha `BANCO=supabase`, `SUPABASE_URL` e
`SUPABASE_KEY` no `.env`; o passo a passo está em `docs/publicar_site.md`.

## O que o site faz

- **Conta:** criar, entrar, sair, continuar conectado ao atualizar a página (F5) e apagar a conta
  com todos os dados (LGPD).
- **Perfil:** objetivo, restrições (alérgenos da Anvisa, lactose, glúten, vegetariano, vegano),
  dados do corpo, "Não gosto de" e orçamento; IMC, meta de calorias (Mifflin-St Jeor), proteína,
  água e metas do nutricionista.
- **Chat:** "tenho frango, batata e cebola" vira de 3 a 6 sugestões com o que falta comprar; cada
  uma abre o modo de preparo; receita pelo nome para N pessoas, com nutrientes estimados por porção.
  Filtros numa caixa só (Doce, Sopa, Japonesa, só vegano, só bebidas). Histórico de conversas.
- **Intenções:** cumprimento, agradecimento, despedida e assunto fora de cozinha recebem resposta
  pronta; quando as regras não decidem, o LLM classifica a mensagem em JSON.
- **Cardápio da semana:** vários por conta, refeições editáveis, trocar ou escolher o prato, abrir a
  receita na porção indicada.
- **Registro do que comeu** (a maçã de cada receita) e da água, com somas do dia, 7 e 30 dias.
- **Modo Pro:** vídeo da receita no YouTube (com `YOUTUBE_API_KEY`; sem ela, o link da busca).
- **Robustez:** resposta em tempo real e troca automática para 2 modelos reserva do Gemini.

## Estrutura

```
NutriMesa/
├── app.py                # site (Streamlit)
├── iniciar_local.bat     # abre o site no Windows (localhost:8505)
├── rodar_testes.bat      # roda os testes no Windows e salva resultado_testes.txt
├── conversar.py          # chat no terminal (Ollama ou Gemini)
├── supabase/             # schema e atualizações do banco da versão publicada
├── .streamlit/config.toml  # cores do site nos modos claro e escuro
├── data/vocab/           # ingredientes, sinônimos e restrições (conferência das respostas)
├── docs/                 # relatório, decisões, CRISP-DM, fontes e guias
├── src/nutrimesa/
│   ├── chat.py           # conversa com o LLM (Gemini ou Ollama) e modelos reserva
│   ├── intents.py        # intenção da mensagem: cumprimento, cozinha, fora do escopo...
│   ├── search.py         # entende os ingredientes citados (tolera erros de digitação)
│   ├── restrictions.py   # alergias, intolerâncias e dieta; confere o texto do modelo
│   ├── vocabulary.py     # carrega, normaliza e valida o vocabulário
│   ├── accounts.py       # contas, perfis, cardápios, conversas e consumo
│   ├── banco_local.py    # banco local em SQLite, no lugar do Supabase (D76)
│   ├── energy.py         # IMC, metas de calorias, proteína e água
│   ├── consumo.py        # o que a pessoa comeu: nutrientes da porção e somas por período
│   ├── planner.py        # cardápio da semana (gerado pelo Gemini, validado pelo código)
│   ├── videos.py         # vídeo da receita no Modo Pro (YouTube)
│   └── visual.py         # ilustrações (SVG) e estilo do site
└── tests/
```

## Testes

```bash
python -m pytest
```

No Windows, dois cliques em `rodar_testes.bat`. Em 23/11/2026: **150 testes passando** (Python
3.13, pytest 9.1). Os testes do chat usam um cliente falso do Gemini, então não gastam a cota nem
medem a qualidade das respostas do modelo real.

## Chat no terminal

Por padrão, `python conversar.py` usa um modelo local e gratuito pelo Ollama (D24): instale o Ollama
(ollama.com), rode `ollama pull qwen2.5:7b` e depois `python conversar.py`. Com
`LLM_PROVIDER=gemini` no `.env`, usa o Gemini.

## Limitações conhecidas

- Receitas e nutrientes são estimativas da IA (D56): podem errar e não substituem nutricionista nem
  a leitura dos rótulos; o site avisa.
- A conferência das restrições reconhece os 96 ingredientes do vocabulário (188 sinônimos); um
  ingrediente fora dele passa sem aviso.
- Depende de internet e da cota gratuita do Gemini, que tem limite diário por chave.
- No banco local os dados ficam só no computador que roda o site, sem envio de e-mail e sem
  "Entrar com o Google" (que depende do Supabase).
- Não há avaliação quantitativa das respostas do modelo real (prevista no planejamento, não feita).

## Fontes

Fontes avaliadas e seu grau de verificação: `docs/fontes_de_dados.md`.
