#!/usr/bin/env python3
"""
setup.py — Setup inicial do Job Agent v2.0.
Cria estrutura de diretórios, copia .env.example e inicializa o banco.
"""
import sys
import shutil
from pathlib import Path


def setup():
    base = Path(__file__).parent

    dirs = ["data", "logs", "output"]
    for d in dirs:
        (base / d).mkdir(exist_ok=True)
        gitkeep = base / d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
        print(f"  [OK] {d}/")

    env_example = base / ".env.example"
    env_file = base / ".env"
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print("  [OK] .env criado a partir de .env.example — configure suas variaveis")
    elif env_file.exists():
        print("  [OK] .env ja existe — mantendo configuracoes atuais")

    try:
        sys.path.insert(0, str(base))
        from core.models import init_db
        init_db()
        print("  [OK] Banco de dados inicializado")
    except Exception as e:
        print(f"  [ERRO] Falha ao inicializar banco: {e}")
        sys.exit(1)

    print("\nSetup completo. Proximos passos:")
    print("  1. Configure o .env com suas credenciais")
    print("  2. Execute: python scheduler.py")
    print("  3. Em outro terminal: python web/app.py")
    print("  4. Dashboard: http://localhost:5000")


if __name__ == "__main__":
    print("Iniciando setup do Job Agent v2.0...\n")
    setup()
