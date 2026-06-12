# Sistema de Controle de Materiais

## Sobre o Sistema

Este é um sistema web responsivo para controle de materiais desenvolvido em Python com Flask. O sistema permite gerenciar estoque, cadastrar itens, técnicos e empresas/parceiros, além de registrar transferências internas e externas de materiais.

## Funcionalidades Principais

- Cadastro de itens, técnicos e empresas/parceiros
- Controle de estoque com alerta de saldo mínimo (30% do saldo atual)
- Transferências internas (entre técnicos/setores) e externas (para empresas/parceiros)
- Importação e exportação de itens via arquivos Excel
- Consulta de saldo de estoque e busca de itens por código ou descrição
- Histórico de transferências com opção de impressão

## Requisitos

- Python 3.8 ou superior
- Dependências listadas em requirements.txt

## Instalação

1. Extraia o arquivo ZIP em um diretório de sua preferência
2. Ative o ambiente virtual:
   ```
   source venv/bin/activate  # No Linux/Mac
   venv\Scripts\activate     # No Windows
   ```
3. Instale as dependências (caso necessário):
   ```
   pip install -r requirements.txt
   ```

## Execução

1. Com o ambiente virtual ativado, execute:

   ```

   ```

   python run.py

2. Acesse o sistema no navegador: http://localhost:5000

## Primeiro Acesso

Na primeira execução, será necessário criar um usuário técnico para acessar o sistema. Execute o seguinte comando:

```
python src/create_admin.py
```

## Estrutura do Projeto

- `src/main.py`: Arquivo principal do sistema
- `src/models/`: Modelos de dados (Item, Estoque, Técnico, Empresa, Transferência)
- `src/routes/`: Rotas da API e páginas web
- `src/static/`: Arquivos estáticos (CSS, JavaScript, imagens)
- `src/templates/`: Templates HTML das páginas
- `venv/`: Ambiente virtual Python

## Contato

Para suporte ou dúvidas, entre em contato com o desenvolvedor.

gerar banco
python create_db.py

# LogiStock atualizado

## Variáveis de ambiente no Render

Configure no painel do Render antes de publicar:

- `SECRET_KEY`: chave secreta fixa da aplicação.
- `DATABASE_URL`: opcional se usar PostgreSQL; sem ela o sistema usa `/var/data/logistock.db`.
- `MAIL_USERNAME`, `MAIL_PASSWORD` e `MAIL_DEFAULT_SENDER`: envio SMTP.
- `BREVO_API_KEY`: envio de redefinição de senha pela API Brevo.
- `GOOGLE_DRIVE_CREDENTIALS_FILE` e `GOOGLE_DRIVE_FOLDER_ID`: backup no Google Drive.
- `ADMIN_BOOTSTRAP_TOKEN`, `ADMIN_BOOTSTRAP_EMAIL` e `ADMIN_BOOTSTRAP_PASSWORD`: criação manual de admin pela rota temporária `/_bootstrap_admin`.
- `LOGISTOCK_ADMIN_EMAIL` e `LOGISTOCK_ADMIN_PASSWORD`: criação automática de admin na inicialização, se realmente precisar.

Não versionar arquivos `.db`, `.env`, tokens do Google Drive nem backups.
