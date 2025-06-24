# Usa imagem oficial Python
FROM python:3.10-slim

# Define diretório de trabalho
WORKDIR /app

# Copia tudo
COPY . .

# Instala dependências
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expõe porta usada pelo Gunicorn
EXPOSE 8080

# Comando de inicialização
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8080"]
