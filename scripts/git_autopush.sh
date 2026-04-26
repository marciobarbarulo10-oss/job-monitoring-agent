#!/bin/bash
# Push automático para o GitHub.
# Uso: bash scripts/git_autopush.sh "mensagem opcional"

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

if [ -n "$1" ]; then
    MSG="$1"
else
    TOTAL=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    MSG="chore: auto-sync ${TIMESTAMP} (${TOTAL} arquivo(s))"
fi

echo "Git Auto-Push — Job Agent"
echo "Branch: $BRANCH"
echo "Mensagem: $MSG"
echo ""

if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "Nada para commitar — repositorio atualizado."
    exit 0
fi

git add -A
echo "Arquivos no commit:"
git diff --cached --name-status
echo ""
git commit -m "$MSG"

MAX_TRIES=3
for i in $(seq 1 $MAX_TRIES); do
    echo "Push tentativa $i/$MAX_TRIES..."
    if git push origin "$BRANCH" 2>&1; then
        echo ""
        echo "Push realizado com sucesso!"
        exit 0
    else
        echo "Falha na tentativa $i. Aguardando $((i * 10))s..."
        sleep $((i * 10))
    fi
done

echo "Push falhou apos $MAX_TRIES tentativas."
exit 1
