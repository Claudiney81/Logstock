#!/usr/bin/env python3
"""
Gera uma cópia sanitizada do projeto para uso em treino/QA.
Cria a pasta `logistock-qa` no mesmo diretório deste script.
Exclui arquivos e pastas sensíveis (tokens, venv, backups, .git, instance etc.).
"""

from pathlib import Path
import shutil
import os
import fnmatch

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "logistock-qa"

# Padrões e nomes a ignorar/remover
IGNORE_DIR_NAMES = {
    'venv', '.venv', '.git', '.vscode', 'backups', 'instance', 'node_modules', 'tmp_chrome_pdf', 'tmp_auditoria_bancos_somente_analise'
}
IGNORE_FILE_PATTERNS = [
    'token_drive.json', 'google_drive_oauth.json', '*.sqlite', '*.db', '*.db-journal', '*.log', '*.pem', '*.key', '*.env', 'secret_*.json'
]

def should_skip_path(path: Path):
    # Skip if any path part matches an ignored dir
    for part in path.parts:
        if part in IGNORE_DIR_NAMES:
            return True
    # Skip files matching ignore patterns
    name = path.name
    for pat in IGNORE_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def make_dest_clean():
    if DEST.exists():
        print(f"Removendo destino existente {DEST}")
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)


def copy_project():
    for root, dirs, files in os.walk(ROOT):
        root_path = Path(root)
        # don't recurse into dest itself
        if DEST in root_path.parents or root_path == DEST:
            continue
        # skip ignored dirs at this level
        dirs[:] = [d for d in dirs if not should_skip_path(root_path / d)]
        rel = root_path.relative_to(ROOT)
        target_dir = DEST / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            src_file = root_path / f
            if should_skip_path(src_file):
                continue
            # copy file
            dest_file = target_dir / f
            try:
                shutil.copy2(src_file, dest_file)
            except Exception as e:
                print(f"Falha ao copiar {src_file} -> {dest_file}: {e}")
    print("Cópia inicial concluída.")


def remove_sensitive_files():
    # remove specific known sensitive files if present
    for pat in ['token_drive.json', 'google_drive_oauth.json']:
        for p in DEST.rglob(pat):
            try:
                p.unlink()
                print(f"Removido {p}")
            except Exception as e:
                print(f"Falha ao remover {p}: {e}")


def write_env_example():
    content = (
        "# Exemplo de variáveis de ambiente para execução do projeto (QA)\n"
        "# Preencha conforme necessário antes de rodar.\n\n"
        "SECRET_KEY=troque_por_uma_chave_segura\n"
        "DATABASE_URL=sqlite:///db.sqlite3\n"
        "DRIVE_CREDENTIALS_FILE=google_drive_oauth.json  # se necessário, use variáveis/serviço mock\n"
        "SEND_EMAIL=false\n"
    )
    (DEST / '.env.example').write_text(content)
    print("Escrito .env.example")


def write_gitignore():
    content = (
        "venv/\n"
        "*.pyc\n"
        "__pycache__/\n"
        "instance/\n"
        "token_drive.json\n"
        "google_drive_oauth.json\n"
        "*.sqlite3\n"
        "backups/\n"
        "logs/\n"
    )
    (DEST / '.gitignore').write_text(content)
    print("Escrito .gitignore")


def write_readme():
    content = (
        "LOGISTOCK - QA EXPORT\n\n"
        "Esta cópia foi gerada para treino de casos de teste (QA).\n"
        "- Arquivos sensíveis foram removidos ou ignorados.\n"
        "- Verifique e preencha `.env.example` antes de rodar.\n\n"
        "Para gerar esta cópia a partir da raiz do projeto, rode:\n"
        "python prepare_qa_export.py\n\n"
        "Após gerar a pasta `logistock-qa`, inicialize um novo repositório git, crie um remoto (GitHub) e faça push.\n"
    )
    (DEST / 'README_QA.md').write_text(content)
    print("Escrito README_QA.md")


def main():
    print(f"Exportando projeto de {ROOT} para {DEST}")
    make_dest_clean()
    copy_project()
    remove_sensitive_files()
    write_env_example()
    write_gitignore()
    write_readme()
    print('\nPróximos passos:')
    print(f"  1) cd {DEST}")
    print("  2) crie um virtualenv e instale dependências: pip install -r requirements.txt")
    print("  3) revise .env.example e crie .env com valores de teste")
    print("  4) inicialize git: git init && git add . && git commit -m \"Initial QA export\"")
    print("  5) crie repositório remoto (GitHub) e faça push: git remote add origin <URL> && git push -u origin main")

if __name__ == '__main__':
    main()
