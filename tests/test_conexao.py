import socket
import pytest
from nutrimesa import accounts

class ConnectError(Exception):
    pass

class Cliente:
    class auth:
        @staticmethod
        def sign_up(dados):
            try:
                raise socket.gaierror(11001, "getaddrinfo failed")
            except socket.gaierror as e:
                raise ConnectError("[Errno 11001] getaddrinfo failed") from e

def test_cadastro_sem_conexao_explica_a_causa(capsys):
    with pytest.raises(accounts.AccountError) as erro:
        accounts.sign_up(Cliente, "a@b.com", "senha12345", "Ana", True)
    assert str(erro.value) == accounts.SEM_CONEXAO
    assert "ConnectError" in capsys.readouterr().err
