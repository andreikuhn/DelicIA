# Modo Pro (decisão D71)

Com o Modo Pro ligado, cada receita aberta (no chat e no cardápio) mostra um vídeo de alguém fazendo a
receita. Por enquanto é grátis: a pessoa liga em **Configurações > Modo Pro**. No futuro será um plano pago.

## O que já funciona sem fazer nada

- O botão do Modo Pro em Configurações.
- Na receita, o botão **Ver vídeos desta receita no YouTube**, que abre a busca do YouTube numa aba nova.

## 1. Guardar o Modo Pro na conta (Supabase)

Sem este passo, o Modo Pro fica ligado só até a pessoa sair.

1. Abra o Supabase > **SQL Editor > New query**.
2. Cole o conteúdo de `supabase/008_pro.sql` e clique em **Run**.

## 2. Vídeo dentro da receita (chave do YouTube)

Sem a chave, aparece só o botão da busca. Com ela, o vídeo toca dentro da própria receita.

1. Abra https://console.cloud.google.com e selecione o projeto `DelicIA` (o mesmo do login com o Google;
   se ainda não criou, crie um projeto com esse nome).
2. Menu (☰) > **APIs e serviços > Biblioteca**. Procure **YouTube Data API v3**, abra e clique em **Ativar**.
3. Menu > **APIs e serviços > Credenciais > Criar credenciais > Chave de API**. Copie a chave.
4. Na chave criada, clique em **Editar chave de API**:
   - **Restrições de API:** marque **Restringir chave** e escolha só **YouTube Data API v3**.
   - Clique em **Salvar**.
5. Nos **Secrets** do Streamlit (share.streamlit.io > app > ⋮ > Settings > Secrets), acrescente no fim:

```toml
YOUTUBE_API_KEY = "cole-a-chave-aqui"
```

A chave é como uma senha: não mande por chat nem coloque no GitHub.

## Limites

- A cota grátis do YouTube dá cerca de **100 buscas por dia**. O site guarda o vídeo achado para cada nome
  de receita por 7 dias, para todo mundo, então a mesma receita não gasta a cota de novo.
- Quando a cota acaba, a receita mostra o botão da busca no YouTube no lugar do vídeo, até o dia seguinte.
- As receitas são escritas pela IA: o vídeo é o mais relevante do YouTube para o **nome** da receita.
  Quantidades e passos podem ser diferentes, e a tela avisa isso embaixo do vídeo.
