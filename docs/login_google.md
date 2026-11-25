# Entrar com o Google (decisão D70)

O botão "Entrar com o Google" já está no código, mas só aparece depois destes 4 passos. Faça na ordem.
Leva uns 15 minutos. Tudo é feito nas suas contas: o Google e o Supabase pedem a sua senha.

Endereços desta conta (copie e cole exatamente):

- Endereço de retorno do Supabase: `https://sqrdatinxehudgncrjin.supabase.co/auth/v1/callback`
- Site: `https://delicia.streamlit.app`

## 1. Google Cloud: tela de permissão

1. Abra https://console.cloud.google.com e entre com a sua conta Google.
2. No alto da página, clique no seletor de projeto > **Novo projeto**. Nome: `DelicIA`. Clique em **Criar** e
   depois selecione o projeto novo no mesmo seletor.
3. No menu (☰), vá em **APIs e serviços > Tela de permissão OAuth** (pode aparecer como **Google Auth Platform**).
   Clique em **Começar**.
4. Preencha:
   - **Nome do app:** `DelícIA`
   - **E-mail de suporte do usuário:** o seu e-mail
   - **Público:** **Externo**
   - **Dados de contato:** o seu e-mail
   - Aceite a política e clique em **Criar**.
5. Em **Público** (Audience), clique em **Publicar app** (Publish app) e confirme. Sem isso, só as contas
   adicionadas como "usuários de teste" conseguem entrar.
   - O Google não pede revisão: o site só usa nome, e-mail e foto (permissões básicas).

## 2. Google Cloud: ID do cliente

1. Ainda em **APIs e serviços**, vá em **Credenciais > Criar credenciais > ID do cliente OAuth**
   (ou **Clientes > Criar cliente**, no Google Auth Platform).
2. **Tipo de aplicativo:** **Aplicativo da Web**. **Nome:** `DelícIA site`.
3. Em **Origens JavaScript autorizadas**, clique em **Adicionar URI** e cole: `https://delicia.streamlit.app`
4. Em **URIs de redirecionamento autorizados**, clique em **Adicionar URI** e cole:
   `https://sqrdatinxehudgncrjin.supabase.co/auth/v1/callback`
5. Clique em **Criar**. Aparecem o **ID do cliente** e a **Chave secreta do cliente**. Deixe essa janela
   aberta (ou baixe o JSON): você cola os dois no passo 3.
   - A chave secreta é como uma senha: não mande por chat nem coloque no GitHub.

## 3. Supabase: ligar o Google

1. Abra https://supabase.com/dashboard e entre no projeto da DelícIA.
2. Menu da esquerda: **Authentication > Sign In / Providers** (em versões antigas: **Providers**).
3. Clique em **Google**, ligue **Enable Sign in with Google** e cole:
   - **Client IDs:** o ID do cliente do passo 2
   - **Client Secret (for OAuth):** a chave secreta do passo 2
4. Confira que o **Callback URL** mostrado ali é o mesmo do passo 2.4. Clique em **Save**.
5. Ainda em **Authentication**, vá em **URL Configuration**:
   - **Site URL:** `https://delicia.streamlit.app`
   - Em **Redirect URLs**, clique em **Add URL** e cole: `https://delicia.streamlit.app/**`
     (os dois asteriscos deixam o site voltar com o código do Google no endereço). Clique em **Save**.

## 4. Streamlit: mostrar o botão

1. Abra https://share.streamlit.io, no app `delicia`, clique em **⋮ > Settings > Secrets**.
2. Acrescente estas duas linhas no fim (sem apagar as outras) e clique em **Save**:

```toml
LOGIN_GOOGLE = "sim"
SITE_URL = "https://delicia.streamlit.app"
```

3. O site reinicia sozinho em alguns segundos. Abra o site sem estar logado: o botão
   **Entrar com o Google** aparece no cartão de login, acima do e-mail.

## Como funciona

- O botão leva para a página do Google na janela inteira. Depois de escolher a conta, o Google devolve para
  o site, que já entra.
- **Primeira vez com o Google:** antes de criar o perfil, aparece o texto "Como a DelícIA usa seus dados" com
  **Concordo e quero entrar** e **Não concordo** (LGPD). Depois do aceite, abre o cadastro do perfil.
- **Já tinha conta com e-mail e senha no mesmo e-mail:** o Supabase liga as duas e os dados continuam os
  mesmos.
- Para esconder o botão de novo, troque `LOGIN_GOOGLE = "sim"` por `LOGIN_GOOGLE = "nao"` nos Secrets.

## Se der errado

- **"Não deu para entrar com o Google (o pedido venceu)"**: passaram mais de 15 minutos na página do
  Google, ou o site reiniciou nesse meio-tempo. Clique no botão de novo.
- **Página do Google diz "redirect_uri_mismatch"**: o endereço do passo 2.4 não está igual ao do Supabase
  (passo 3.4). Copie de novo, sem espaço no fim.
- **Volta para o site sem entrar, com `?error=` no endereço**: falta o passo 3.5 (Redirect URLs).
- **Só você consegue entrar, outras pessoas não**: falta publicar o app (passo 1.5).
