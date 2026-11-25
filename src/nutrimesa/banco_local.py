"""Banco local (SQLite) no lugar do Supabase: contas, perfis, cardápios, conversas e consumo no próprio PC.

Imita só a parte do cliente do Supabase que o accounts.py usa (auth.* e table(...).select/insert/upsert/
update/delete com eq, gte, order e limit). Assim o resto do site não muda: o app escolhe este cliente
quando BANCO=local (o padrão) e o do Supabase quando BANCO=supabase.

Tudo fica em data/delicia_local.sqlite (fora do Git, pelo *.sqlite do .gitignore). As senhas são
guardadas com hash PBKDF2 e sal, nunca em texto. Sem servidor de e-mail: o código de recuperação de
senha aparece na janela do terminal que roda o site.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / "data" / "delicia_local.sqlite"
_ITERACOES = 200_000


class AuthApiError(Exception):
    """Mesmo nome do erro do Supabase: o accounts.py reconhece pelo nome e pelo `code`."""

    def __init__(self, mensagem: str, code: str | None = None):
        super().__init__(mensagem)
        self.code = code


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(senha: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), _ITERACOES).hex()


class _Banco:
    def __init__(self, arquivo: Path):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                    sal TEXT NOT NULL, senha TEXT NOT NULL, metadados TEXT NOT NULL, criado_em TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessoes (token TEXT PRIMARY KEY, usuario_id TEXT NOT NULL,
                    criado_em TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS codigos (email TEXT PRIMARY KEY, codigo TEXT NOT NULL,
                    criado_em TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS linhas (tabela TEXT NOT NULL, id TEXT NOT NULL, dados TEXT NOT NULL,
                    PRIMARY KEY (tabela, id));
            """)

    def conectar(self) -> sqlite3.Connection:
        # uma conexão por operação: o Streamlit roda cada sessão numa thread diferente
        return sqlite3.connect(self.arquivo, timeout=10)


# ---------------------------------------------------------------- autenticação

class _Auth:
    def __init__(self, cliente: "ClienteLocal"):
        self._c = cliente

    @property
    def _banco(self) -> _Banco:
        return self._c._banco

    def _usuario(self, linha) -> SimpleNamespace:
        return SimpleNamespace(id=linha[0], email=linha[1], user_metadata=json.loads(linha[2]))

    def _abrir_sessao(self, usuario_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._banco.conectar() as con:
            con.execute("INSERT INTO sessoes VALUES (?, ?, ?)", (token, usuario_id, _agora()))
        self._c._usuario_id, self._c._token = usuario_id, token
        return token

    def _resposta(self, usuario_id: str, token: str):
        with self._banco.conectar() as con:
            linha = con.execute("SELECT id, email, metadados FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        usuario = self._usuario(linha)
        return SimpleNamespace(user=usuario, session=SimpleNamespace(refresh_token=token, user=usuario))

    def sign_up(self, dados: dict):
        email = (dados.get("email") or "").strip().lower()
        senha = dados.get("password") or ""
        if "@" not in email or "." not in email.split("@")[-1]:
            raise AuthApiError("e-mail inválido", "email_address_invalid")
        sal = secrets.token_hex(16)
        usuario_id = str(uuid.uuid4())
        metadados = json.dumps((dados.get("options") or {}).get("data") or {}, ensure_ascii=False)
        try:
            with self._banco.conectar() as con:
                con.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, ?)",
                            (usuario_id, email, sal, _hash(senha, sal), metadados, _agora()))
        except sqlite3.IntegrityError as erro:
            raise AuthApiError("e-mail já cadastrado", "user_already_exists") from erro
        return self._resposta(usuario_id, self._abrir_sessao(usuario_id))

    def sign_in_with_password(self, dados: dict):
        email = (dados.get("email") or "").strip().lower()
        with self._banco.conectar() as con:
            linha = con.execute("SELECT id, sal, senha FROM usuarios WHERE email = ?", (email,)).fetchone()
        if not linha or not secrets.compare_digest(_hash(dados.get("password") or "", linha[1]), linha[2]):
            raise AuthApiError("credenciais inválidas", "invalid_credentials")
        return self._resposta(linha[0], self._abrir_sessao(linha[0]))

    def refresh_session(self, token: str):
        with self._banco.conectar() as con:
            linha = con.execute("SELECT usuario_id FROM sessoes WHERE token = ?", (token,)).fetchone()
        if not linha:
            raise AuthApiError("sessão inválida", "session_not_found")
        self._c._usuario_id, self._c._token = linha[0], token
        return self._resposta(linha[0], token)

    def get_session(self):
        return SimpleNamespace(refresh_token=self._c._token) if self._c._token else None

    def sign_out(self):
        if self._c._token:
            with self._banco.conectar() as con:
                con.execute("DELETE FROM sessoes WHERE token = ?", (self._c._token,))
        self._c._usuario_id = self._c._token = None

    def reset_password_for_email(self, email: str):
        email = email.strip().lower()
        with self._banco.conectar() as con:
            existe = con.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,)).fetchone()
            if existe:
                codigo = f"{secrets.randbelow(10**6):06d}"
                con.execute("INSERT OR REPLACE INTO codigos VALUES (?, ?, ?)", (email, codigo, _agora()))
                # sem servidor de e-mail no modo local: o código aparece na janela do site
                print(f"[banco local] código de recuperação para {email}: {codigo}", file=sys.stderr, flush=True)

    def verify_otp(self, dados: dict):
        email = (dados.get("email") or "").strip().lower()
        with self._banco.conectar() as con:
            linha = con.execute("SELECT codigo FROM codigos WHERE email = ?", (email,)).fetchone()
            if not linha or not secrets.compare_digest(linha[0], (dados.get("token") or "").strip()):
                raise AuthApiError("código inválido", "otp_expired")
            con.execute("DELETE FROM codigos WHERE email = ?", (email,))
            usuario_id = con.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()[0]
        return self._resposta(usuario_id, self._abrir_sessao(usuario_id))

    def update_user(self, dados: dict):
        if not self._c._usuario_id:
            raise AuthApiError("sem sessão", "session_not_found")
        if "password" in dados:
            sal = secrets.token_hex(16)
            with self._banco.conectar() as con:
                con.execute("UPDATE usuarios SET sal = ?, senha = ? WHERE id = ?",
                            (sal, _hash(dados["password"], sal), self._c._usuario_id))
        return self._resposta(self._c._usuario_id, self._c._token)

    def sign_in_with_oauth(self, *_args, **_kwargs):
        raise AuthApiError("Entrar com o Google não funciona no modo local", "oauth_local")

    def exchange_code_for_session(self, *_args, **_kwargs):
        raise AuthApiError("Entrar com o Google não funciona no modo local", "oauth_local")


# ---------------------------------------------------------------- tabelas

class _Consulta:
    def __init__(self, cliente: "ClienteLocal", tabela: str):
        self._c, self._tabela = cliente, tabela
        self._acao, self._valor, self._colunas = "select", None, "*"
        self._filtros: list = []
        self._ordem: tuple[str, bool] | None = None
        self._limite: int | None = None

    # o que fazer
    def select(self, colunas: str = "*"):
        self._acao, self._colunas = "select", colunas
        return self

    def insert(self, linha: dict):
        self._acao, self._valor = "insert", linha
        return self

    def upsert(self, linha: dict):
        self._acao, self._valor = "upsert", linha
        return self

    def update(self, dados: dict):
        self._acao, self._valor = "update", dados
        return self

    def delete(self):
        self._acao = "delete"
        return self

    # filtros
    def eq(self, coluna: str, valor):
        self._filtros.append(lambda d: d.get(coluna) == valor)
        return self

    def gte(self, coluna: str, valor):
        self._filtros.append(lambda d: d.get(coluna) is not None and d.get(coluna) >= valor)
        return self

    def order(self, coluna: str, desc: bool = False):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n: int):
        self._limite = n
        return self

    def _todas(self, con) -> list[dict]:
        return [json.loads(d) for (d,) in con.execute("SELECT dados FROM linhas WHERE tabela = ?", (self._tabela,))]

    def _gravar(self, con, linha: dict) -> None:
        con.execute("INSERT OR REPLACE INTO linhas VALUES (?, ?, ?)",
                    (self._tabela, str(linha["id"]), json.dumps(linha, ensure_ascii=False)))

    def execute(self):
        with self._c._banco.conectar() as con:
            if self._acao in ("insert", "upsert"):
                linha = {"criado_em": _agora(), **self._valor}
                linha.setdefault("id", str(uuid.uuid4()))
                existe = con.execute("SELECT dados FROM linhas WHERE tabela = ? AND id = ?",
                                     (self._tabela, str(linha["id"]))).fetchone()
                if existe and self._acao == "insert":
                    raise AuthApiError("registro já existe", "23505")
                if existe:  # upsert mantém o que não veio (como o Postgres faria com as outras colunas)
                    linha = {**json.loads(existe[0]), **self._valor}
                self._gravar(con, linha)
                return SimpleNamespace(data=[linha])
            achadas = [d for d in self._todas(con) if all(f(d) for f in self._filtros)]
            if self._acao == "update":
                for d in achadas:
                    d.update(self._valor)
                    self._gravar(con, d)
                return SimpleNamespace(data=achadas)
            if self._acao == "delete":
                for d in achadas:
                    con.execute("DELETE FROM linhas WHERE tabela = ? AND id = ?", (self._tabela, str(d["id"])))
                return SimpleNamespace(data=achadas)
        if self._ordem:
            coluna, desc = self._ordem
            achadas.sort(key=lambda d: str(d.get(coluna) or ""), reverse=desc)
        if self._limite is not None:
            achadas = achadas[: self._limite]
        if self._colunas.strip() != "*":
            nomes = [c.strip() for c in self._colunas.split(",")]
            achadas = [{n: d.get(n) for n in nomes} for d in achadas]
        return SimpleNamespace(data=achadas)


class ClienteLocal:
    """Um por sessão do navegador, como o cliente do Supabase: guarda quem está logado."""

    def __init__(self, arquivo: Path | str = ARQUIVO_PADRAO):
        self._banco = _Banco(Path(arquivo))
        self._usuario_id: str | None = None
        self._token: str | None = None
        self.auth = _Auth(self)

    def table(self, nome: str) -> _Consulta:
        return _Consulta(self, nome)

    def rpc(self, nome: str, _parametros: dict | None = None):
        """Só a função do banco que o site usa: apagar_minha_conta (LGPD), que apaga a conta logada,
        as sessões dela e todas as linhas dela (perfil, cardápio, conversas e consumo)."""
        if nome != "apagar_minha_conta":
            raise AuthApiError(f"função desconhecida: {nome}", "function_not_found")
        usuario_id = self._usuario_id
        if not usuario_id:
            raise AuthApiError("sem sessão", "session_not_found")

        def apagar():
            with self._banco.conectar() as con:
                for tabela, id_linha, dados in con.execute("SELECT tabela, id, dados FROM linhas").fetchall():
                    d = json.loads(dados)
                    if d.get("id") == usuario_id or d.get("usuario_id") == usuario_id:
                        con.execute("DELETE FROM linhas WHERE tabela = ? AND id = ?", (tabela, id_linha))
                con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
                con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
            self._usuario_id = self._token = None
            return SimpleNamespace(data=None)

        return SimpleNamespace(execute=apagar)
