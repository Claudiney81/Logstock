from app import create_app

app = create_app()

# A linha abaixo é usada apenas para rodar localmente com `python run.py`.
# No Render, o servidor é executado via Gunicorn e essas linhas são ignoradas.
# Para evitar conflito ou confusão, pode deixar comentado assim:

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8000)

