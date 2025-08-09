from app import create_app

# Cria a aplicação
app = create_app()

# Executa localmente
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
