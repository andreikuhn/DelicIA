# Como publicar o site da DelícIA

O site é o `app.py` (Streamlit). Ele usa três serviços com plano gratuito. As contas são suas:
o código não cria nenhuma.

| Serviço | Para quê | O que você guarda |
|---|---|---|
| Google AI Studio (Gemini) | o modelo que conversa | `GEMINI_API_KEY` |
| Supabase | login, recuperação de senha e perfis | `SUPABASE_URL` e `SUPABASE_KEY` |
| GitHub + Streamlit Community Cloud | hospedar o site | (nada; você entra com o GitHub) |

Nomes de menus podem mudar com o tempo; se algum não bater, procure pelo nome parecido.

## 1. Chave do Gemini

1. Entre no Google AI Studio com sua conta Google e crie uma chave de API.
2. Veja lá quais modelos a camada gratuita permite e quantos pedidos por dia. O padrão da
   DelícIA é `gemini-3.1-flash-lite` (os modelos "Flash-Lite" costumam ter mais pedidos
   gratuitos por dia), com dois reservas: `gemini-3.1-flash-lite-preview` e
   `gemini-3-flash-preview`. Se o Google estiver sobrecarregado (503), o limite gratuito acabar
   (429) ou a conexão travar por 30 s, o chat passa na hora para o próximo. O `3-flash-preview` é
   rápido, mas a camada gratuita dele só dá 20 pedidos por dia (2026-10-26). Se quiser outro
   modelo principal, coloque em `LLM_MODEL`.
3. Cada mensagem pode gastar 1 ou 2 pedidos (classificar a intenção e responder).
   Na camada gratuita, o Google pode usar as conversas para melhorar os modelos: isso está
   avisado no cadastro do site.

## 2. Supabase

1. Crie uma conta e um projeto (plano Free). Guarde a senha do banco, mas ela não vai no site.
2. Abra o **SQL Editor**, cole todo o conteúdo de `supabase/schema.sql` e rode. Isso cria a tabela
   `perfis`, as regras para cada pessoa só ver o próprio perfil e a função que apaga a conta.
   Depois rode também `supabase/002_perfil_corpo.sql` (campos de idade, altura, peso etc.) e
   `supabase/003_cardapio.sql` (cardápio da semana salvo na conta) e
   `supabase/004_conversas.sql` (histórico de conversas) e `supabase/005_consumo.sql` (o que a pessoa
   comeu, registrado pela maçã das receitas) e `supabase/006_preferencias.sql` ("Não gosto de" e
   orçamento no perfil).
3. Em **Project Settings > API** (ou "API Keys"), copie:
   - a **URL do projeto** -> `SUPABASE_URL`;
   - a chave **publishable** (ou **anon**) -> `SUPABASE_KEY`.
   **Nunca** use a chave secret/service_role no site.
4. Em **Authentication > Providers**, deixe o login por **Email** ligado.

### E-mails (confirmação de cadastro e "esqueci a senha")

Pelo que a documentação do Supabase diz hoje:
- o envio de e-mail padrão **só entrega para os membros da equipe do projeto** e manda poucos
  e-mails por hora; serve só para testes;
- em projetos gratuitos novos, **não dá para editar os modelos de e-mail** sem configurar um
  **SMTP próprio**.

O "esqueci a senha" da DelícIA funciona por **código de 6 dígitos** digitado no site, e para o
e-mail trazer esse código o modelo **Reset Password** precisa ser editado. Ou seja: para a
recuperação de senha funcionar para qualquer pessoa, é preciso um SMTP próprio.

Serviço escolhido: **Gmail com senha de app** (decisão D32).

**No Google** (precisa ser você, na sua conta):
1. Ative a **Verificação em duas etapas** em Conta Google > Segurança. Sem ela, a opção de
   senha de app não aparece.
2. Procure **"Senhas de app"** (em Segurança, ou pela busca da página da Conta Google), crie uma
   com o nome "DelícIA Supabase" e copie a senha de 16 letras que aparece.
   Ela é um segredo: cole só no Supabase. Nunca no código, no GitHub ou em chat. Se vazar,
   apague a senha de app e crie outra.

**No Supabase**, ligue o SMTP próprio (Authentication > SMTP Settings, ou "Emails > SMTP"):

| Campo | Valor |
|---|---|
| Sender email | o mesmo Gmail da senha de app |
| Sender name | DelícIA |
| Host | `smtp.gmail.com` |
| Port | `587` |
| Username | o mesmo Gmail |
| Password | a senha de app de 16 letras (sem espaços) |

Depois:
1. Confira o limite de e-mails por hora na página **Rate Limits** da autenticação (com SMTP
   próprio dá para ajustar). O próprio Gmail também limita os envios diários de contas gratuitas.
2. Em **Authentication > Email Templates > Reset Password**, troque o texto por algo como:
   `Seu código para trocar a senha da DelícIA é: {{ .Token }}`
   (o código tem 6 dígitos no padrão do Supabase; se mudar o tamanho em "Email OTP length",
   o site continua funcionando, só o texto "6 dígitos" da tela fica diferente).
3. Em **Authentication > URL Configuration**, ponha em **Site URL** o endereço do site publicado
   (o link de confirmação de cadastro leva para lá).
4. Teste: crie uma conta com um e-mail seu que não seja da equipe do projeto, confirme pelo
   e-mail e depois use "Esqueci a senha". Se não chegar nada, olhe o spam e os **Logs** de
   autenticação do Supabase.

Enquanto não houver SMTP próprio, para testar sozinho você pode desligar a confirmação de e-mail
do cadastro (opção "Confirm email" do provedor Email). Aí a pessoa entra logo depois de criar a
conta, mas a recuperação de senha continua sem funcionar para quem não é da equipe.

## 3. Rodar no seu computador antes de publicar

```bash
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Preencha o `.streamlit/secrets.toml` (ele não vai para o Git) e rode:

```bash
python -m streamlit run app.py
```

(Use `python -m streamlit`: no Windows, o comando `streamlit` sozinho pode não ser encontrado.)

## 4. Publicar

1. No GitHub, crie um repositório **vazio** (sem README, sem .gitignore), por exemplo `delicia`.
2. Envie o projeto (o repositório local já existe; o `.gitignore` deixa de fora `.env`,
   `.streamlit/secrets.toml`, `.claude/` e o Excel da TACO):
   ```bash
   git remote add origin https://github.com/Kuhnzinho/delicia.git
   git push -u origin main
   ```
   Na primeira vez, o Git abre o navegador para você autorizar o acesso ao GitHub.
4. Entre em **share.streamlit.io** com a conta do GitHub e clique em **Create app** (ou "New app"):
   repositório `Kuhnzinho/delicia`, branch `main`, arquivo `app.py`. Em **Advanced settings**,
   escolha Python 3.12 e cole em **Secrets** o conteúdo do seu `secrets.toml` preenchido
   (`LLM_PROVIDER`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`). Escolha o endereço do site.
5. Depois de publicado, copie o endereço do site para o **Site URL** do Supabase (passo 2).
6. Para atualizar o site depois: `git add -A`, `git commit -m "o que mudou"` e `git push`. O
   Streamlit Cloud publica a nova versão sozinho. O Cloud às vezes pega o `app.py` novo mas fica
   com partes antigas de `src/` na memória (`ImportError`); o `app.py` percebe e recarrega sozinho.
   Se mesmo assim aparecer erro: **Manage app** (canto de baixo, à direita) > **⋮** > **Reboot app**.

## O que o site guarda

- No Supabase: nome, e-mail, senha (o Supabase guarda só uma versão protegida), objetivo,
  restrições, dados do corpo (se preenchidos), a data do consentimento e o último cardápio da
  semana montado (só as receitas e porções).
- O histórico do chat fica só na memória da sessão do navegador e some ao sair.
- Mensagens e restrições vão para o Gemini para gerar as respostas.
- O botão "Apagar minha conta" apaga a conta e o perfil no Supabase (função `apagar_minha_conta`).
