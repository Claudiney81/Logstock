import sqlite3

# Caminho para o banco de dados
caminho_db = 'instance/logistock.db'

# Conexão com o banco
conn = sqlite3.connect(caminho_db)
cursor = conn.cursor()

# Verifica se a coluna já existe
cursor.execute("PRAGMA table_info(transferencias_externas)")
colunas = [col[1] for col in cursor.fetchall()]
if 'tipo_servico_id' not in colunas:
    # Adiciona a nova coluna
    cursor.execute("ALTER TABLE transferencias_externas ADD COLUMN tipo_servico_id INTEGER")
    print("Coluna 'tipo_servico_id' adicionada com sucesso!")
else:
    print("A coluna 'tipo_servico_id' já existe.")

# Salva e fecha
conn.commit()
conn.close()

