# Usa imagem base do Python
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . /app

# Instala dependências
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Expõe a porta que o Fly.io usa
EXPOSE 8080

# Comando para rodar o app com Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "run:create_app"]
