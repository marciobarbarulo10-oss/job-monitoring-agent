"""
profile.py — Perfil profissional do Márcio + Sistema de Score de Aderência
"""

PERFIL = {
    "nome": "Márcio Beraldo",
    "nivel": "pleno",
    "localizacao": "São Paulo",
    "aceita_remoto": True,
    "aceita_hibrido": True,

    # Palavras-chave com PESO (1-3): quanto maior, mais importante
    "keywords": {
        # Peso 3 — Core da área
        "importação": 3,
        "importacao": 3,
        "desembaraço aduaneiro": 3,
        "desembaraco aduaneiro": 3,
        "anvisa": 3,
        "supply chain": 3,
        "comércio exterior": 3,
        "comercio exterior": 3,
        "comex": 3,
        "i-broker": 3,
        "ibroker": 3,
        "logística internacional": 3,
        "logistica internacional": 3,

        # Peso 2 — Técnico relevante
        "python": 2,
        "automação": 2,
        "automacao": 2,
        "freight forwarder": 2,
        "despacho aduaneiro": 2,
        "siscomex": 2,
        "li": 2,
        "di": 2,
        "declaração de importação": 2,
        "licença de importação": 2,
        "incoterms": 2,
        "ncm": 2,
        "compliance": 2,
        "regulatório": 2,
        "regulatorio": 2,
        "farmacêutico": 2,
        "farmaceutico": 2,
        "cold chain": 2,
        "cadeia frio": 2,
        "glp": 2,
        "excel avançado": 2,
        "excel avancado": 2,

        # Peso 1 — Desejável
        "logística": 1,
        "logistica": 1,
        "rastreamento": 1,
        "tracking": 1,
        "operações": 1,
        "operacoes": 1,
        "sla": 1,
        "transportadora": 1,
        "agente de carga": 1,
        "melhoria contínua": 1,
        "melhoria continua": 1,
        "kpi": 1,
        "receita federal": 1,
        "aduaneiro": 1,
        "embarque": 1,
        "invoice": 1,
        "packing list": 1,
        "bl": 1,
        "awb": 1,
    },

    # Títulos de vagas ideais (match parcial)
    "titulos_ideais": [
        "analista de importação",
        "analista de importacao",
        "analista supply chain",
        "analista de comex",
        "analista de comércio exterior",
        "analista operacional",
        "analista de logística",
        "analista de logistica",
        "analista de operações",
        "analista de desembaraço",
        "analista aduaneiro",
        "analista de governança",
        "analista de melhoria contínua",
    ],

    # Títulos a IGNORAR (muito abaixo ou fora da área)
    "titulos_ignorar": [
        "desenvolvedor",
        "developer",
        "engenheiro de software",
        "cientista de dados",
        "motorista",
        "auxiliar",
        "assistente administrativo",
        "vendedor",
        "representante comercial",
    ],

    # Termos de busca por plataforma
    "queries_busca": [
        "analista de importação pleno",
        "analista supply chain importação",
        "analista comex desembaraço",
        "analista logística internacional",
        "analista operações supply chain",
        "analista importação farmacêutica",
        "analista aduaneiro pleno",
    ]
}


def calcular_score(titulo: str, descricao: str, localizacao: str = "") -> float:
    """
    Calcula score de aderência (0.0 a 10.0) de uma vaga ao perfil.
    
    Critérios:
      - Match de keywords na descrição (60%)
      - Match de título ideal (25%)
      - Localização / modalidade (15%)
    """
    texto = f"{titulo} {descricao}".lower()
    titulo_lower = titulo.lower()
    local_lower = localizacao.lower()

    # ── 1. KEYWORD SCORE (0-6) ────────────────────────────────────────────────
    max_keyword_points = sum(v * 2 for v in PERFIL["keywords"].values())  # teto teórico
    keyword_points = 0
    matched_keywords = []

    for kw, peso in PERFIL["keywords"].items():
        if kw in texto:
            keyword_points += peso
            matched_keywords.append(kw)

    keyword_score = min(6.0, (keyword_points / max(max_keyword_points * 0.15, 1)) * 6)

    # ── 2. TÍTULO SCORE (0-2.5) ────────────────────────────────────────────────
    titulo_score = 0.0
    for titulo_ideal in PERFIL["titulos_ideais"]:
        if titulo_ideal in titulo_lower:
            titulo_score = 2.5
            break
        # match parcial
        palavras = titulo_ideal.split()
        matches = sum(1 for p in palavras if p in titulo_lower)
        parcial = (matches / len(palavras)) * 1.5
        titulo_score = max(titulo_score, parcial)

    # Penalidade por título ignorado
    for ignorar in PERFIL["titulos_ignorar"]:
        if ignorar in titulo_lower:
            return 0.0  # descarta direto

    # ── 3. LOCALIZAÇÃO SCORE (0-1.5) ──────────────────────────────────────────
    local_score = 0.0
    if "são paulo" in local_lower or "sp" in local_lower:
        local_score = 1.5
    elif "remoto" in local_lower or "remote" in local_lower or "home office" in local_lower:
        local_score = 1.5 if PERFIL["aceita_remoto"] else 0.0
    elif "híbrido" in local_lower or "hibrido" in local_lower:
        local_score = 1.2 if PERFIL["aceita_hibrido"] else 0.5
    elif "brasil" in local_lower:
        local_score = 1.0

    score_final = round(keyword_score + titulo_score + local_score, 1)
    return min(10.0, score_final), matched_keywords
