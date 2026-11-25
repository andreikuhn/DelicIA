"""Converse com a DelícIA no terminal. Uso:  python conversar.py

Padrão: modelo local pelo Ollama (gratuito). Antes, instale o Ollama e baixe o modelo:
    ollama pull qwen2.5:7b
Para usar o Gemini: LLM_PROVIDER=gemini e GEMINI_API_KEY no .env.
Digite "sair" para encerrar.
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.chat import create_chat, load_env, provider  # noqa: E402
from nutrimesa.restrictions import load_restrictions  # noqa: E402
from nutrimesa.vocabulary import load_vocabulary  # noqa: E402


def _tratar_erro(erro: Exception, modelo: str) -> bool:
    """Mostra uma mensagem clara. Retorna True se dá para continuar a conversa."""
    if isinstance(erro, ConnectionError):  # o Ollama não está aberto
        print("Não consegui falar com o Ollama. Abra o programa Ollama (ou rode 'ollama serve' "
              "em outro terminal) e tente de novo.")
        return False
    nome = type(erro).__name__
    status = getattr(erro, "status_code", None)
    if nome == "ResponseError" and status == 404:
        print(f"O modelo '{modelo}' ainda não foi baixado. Rode:  ollama pull {modelo}")
        return False
    if nome in {"ClientError", "ServerError", "APIError"} and getattr(erro, "code", None) == 429:  # Gemini
        print("Limite gratuito do Gemini atingido. Espere um pouco (ou até amanhã) e tente de novo.\n")
        return True
    if nome in {"ClientError", "ServerError", "APIError"}:
        print(f"Erro do Gemini ({getattr(erro, 'code', '?')}): {erro}\n")
        return True
    if status is not None:
        print(f"Erro do modelo ({status}): {erro}\n")
        return True
    raise erro


def main() -> int:
    load_env(RAIZ / ".env")
    try:
        nome_provedor = provider()
    except ValueError as erro:
        print(erro)
        return 1
    if nome_provedor == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        print("Não encontrei GEMINI_API_KEY no .env. Crie a chave no Google AI Studio e cole depois do =")
        return 1
    try:
        chat = create_chat(load_vocabulary(), load_restrictions())
    except ImportError as erro:
        print(f"Falta instalar uma biblioteca ({erro.name}). Rode:  pip install -r requirements.txt")
        return 1

    print(f"DelícIA ({nome_provedor}, modelo {chat.modelo}). Diga o que você tem em casa. "
          "\"sair\" encerra.\n")
    while True:
        try:
            texto = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if texto.lower() in {"sair", "exit", "quit"}:
            return 0
        if not texto:
            continue
        if nome_provedor == "ollama":
            print("(pensando...)")
        try:
            print(f"\nDelícIA: {chat.send(texto)}\n")
        except Exception as erro:  # noqa: BLE001 - cada caso conhecido vira mensagem clara
            if not _tratar_erro(erro, chat.modelo):
                return 1


if __name__ == "__main__":
    sys.exit(main())
