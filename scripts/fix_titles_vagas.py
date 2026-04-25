"""
Migração única: corrige títulos colados de vagas.com no banco.
Uso: python scripts/fix_titles_vagas.py
"""
import re
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "job_agent.db")

CHAR_CLASSES = (
    r'([a-záéíóúãõâêîôûàèìòùç])'
    r'([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÈÌÒÙÇ])'
)

# Padrões conhecidos de cargo+preposição colados (ex: "Analistade" → "Analista de")
_CARGO_PREP = re.compile(
    r'\b(Analista|Supervisor|Gerente|Coordenador|Especialista|Assistente|Tecnico|Auxiliar)'
    r'(de|do|da|dos|das)',
    flags=re.IGNORECASE
)

_REPAIR = [
    # Artefatos da segunda execução com regex ruim
    (re.compile(r'\bPle no\b'), 'Pleno'),
    (re.compile(r'\bVen das\b'), 'Vendas'),
    (re.compile(r' d e '), ' de '),
    (re.compile(r' d e$'), ' de'),
]

def fix_title(titulo: str) -> str:
    # 1. Separa transições CamelCase (maiúscula após minúscula)
    fixed = re.sub(CHAR_CLASSES, r'\1 \2', titulo)
    # 2. Separa cargo+preposição colados: "Analistade" → "Analista de"
    fixed = _CARGO_PREP.sub(r'\1 \2', fixed)
    # 3. Repara artefatos de execuções anteriores
    for pattern, replacement in _REPAIR:
        fixed = pattern.sub(replacement, fixed)
    fixed = re.sub(r'\s+', ' ', fixed).strip()
    return fixed

def main():
    if not os.path.exists(DB_PATH):
        print(f"Banco nao encontrado: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    vagas = conn.execute(
        "SELECT id, titulo FROM vagas WHERE fonte LIKE '%vagas%'"
    ).fetchall()

    corrigidos = 0
    for job_id, titulo in vagas:
        if not titulo:
            continue
        fixed = fix_title(titulo)
        if fixed != titulo:
            conn.execute("UPDATE vagas SET titulo=? WHERE id=?", (fixed, job_id))
            print(f"  Corrigido: '{titulo}' -> '{fixed}'")
            corrigidos += 1

    conn.commit()
    conn.close()
    print(f"\nMigracao concluida: {corrigidos} titulos corrigidos de {len(vagas)} vagas.com")

if __name__ == "__main__":
    main()
