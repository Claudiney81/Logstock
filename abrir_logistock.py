"""Inicia o Start e abre o navegador quando o servidor estiver pronto."""

import threading
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen


URL = "http://127.0.0.1:8000/nota/historico"


def servidor_disponivel():
    try:
        with urlopen(URL, timeout=1) as resposta:
            return resposta.status == 200
    except (URLError, OSError):
        return False


def abrir_quando_pronto(encerrado):
    for _ in range(120):
        if encerrado.is_set():
            return
        if servidor_disponivel():
            webbrowser.open(URL)
            return
        if encerrado.wait(0.5):
            return
    print(f"O servidor ainda esta iniciando. Acesse {URL} quando estiver pronto.")


def main():
    if servidor_disponivel():
        webbrowser.open(URL)
        return

    from run import app

    encerrado = threading.Event()
    threading.Thread(target=abrir_quando_pronto, args=(encerrado,), daemon=True).start()
    try:
        app.run(host="127.0.0.1", port=8000, use_reloader=False)
    finally:
        encerrado.set()


if __name__ == "__main__":
    main()
