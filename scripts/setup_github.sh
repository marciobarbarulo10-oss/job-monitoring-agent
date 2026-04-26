#!/bin/bash
# Configura autenticação GitHub para push automático.
# Execute ANTES de usar o GitAgent ou o push automático.

echo "Configurando GitHub para push automatico..."
echo ""

# Testa SSH primeiro
echo "Testando SSH..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "SSH funcionando."
    CURRENT_REMOTE=$(git remote get-url origin)
    if echo "$CURRENT_REMOTE" | grep -q "https://"; then
        REPO=$(echo "$CURRENT_REMOTE" | sed 's|https://github.com/||')
        git remote set-url origin "git@github.com:$REPO"
        echo "Remote atualizado para SSH: git@github.com:$REPO"
    fi
    exit 0
fi

# Usa token pessoal (PAT)
echo "SSH nao configurado. Usando GitHub Personal Access Token (PAT)..."
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Informe seu GitHub Personal Access Token:"
    echo "(Gere em: github.com/settings/tokens — escopo: repo)"
    read -s GITHUB_TOKEN
    echo ""
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Token nao informado."
    exit 1
fi

REMOTE_URL=$(git remote get-url origin)

if echo "$REMOTE_URL" | grep -q "https://"; then
    REPO_PATH=$(echo "$REMOTE_URL" | sed 's|https://github.com/||' | sed 's|\.git||')
else
    REPO_PATH=$(echo "$REMOTE_URL" | sed 's|git@github.com:||' | sed 's|\.git||')
fi

git remote set-url origin "https://${GITHUB_TOKEN}@github.com/${REPO_PATH}"
git config --global credential.helper store

# Salva no .env
if [ -f ".env" ]; then
    if grep -q "GITHUB_TOKEN" .env; then
        sed -i "s|GITHUB_TOKEN=.*|GITHUB_TOKEN=${GITHUB_TOKEN}|" .env
    else
        echo "GITHUB_TOKEN=${GITHUB_TOKEN}" >> .env
    fi
    echo "Token salvo no .env"
fi

echo ""
echo "Testando conexao com GitHub..."
if git ls-remote origin HEAD > /dev/null 2>&1; then
    echo "Autenticacao funcionando!"
    echo "Push automatico habilitado para: https://github.com/${REPO_PATH}"
else
    echo "Falha na autenticacao. Verifique o token."
    exit 1
fi

echo ""
echo "GitHub configurado! Teste manual: bash scripts/git_autopush.sh"
