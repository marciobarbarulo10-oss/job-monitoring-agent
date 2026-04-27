"""
Agente de Marketing — ciclo autônomo de growth.

Responsabilidades:
- Gerar posts para Twitter, LinkedIn e Reddit com dados reais do sistema
- Enviar newsletter semanal via MailerLite para usuários cadastrados
- Atualizar README com métricas ao vivo (vagas, score médio, candidaturas)
- Salvar posts prontos para publicação manual
- Notificar via Telegram com resumo e posts para copiar
- Push automático das mudanças para o GitHub

Não tem dependências externas além das já usadas no projeto.
Twitter/Dev.to são opcionais (controlados por env vars).
MailerLite é opcional — modo lite se API key ausente.
"""
import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from agents import BaseAgent

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")
GITHUB_URL = "https://github.com/marciobarbarulo10-oss/job-monitoring-agent"
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5173")


class MarketerAgent(BaseAgent):

    def __init__(self):
        super().__init__("marketer")
        from intelligence.llm_client import LLMClient
        self.llm = LLMClient()
        self.twitter_token = os.getenv("TWITTER_BEARER_TOKEN", "").strip()
        self.devto_key = os.getenv("DEVTO_API_KEY", "").strip()

    # ─────────────────────────────────────────────
    # DADOS REAIS DO SISTEMA
    # ─────────────────────────────────────────────
    def _get_real_stats(self) -> dict:
        """Coleta métricas reais do banco para usar no conteúdo."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            c = conn.cursor()

            c.execute("SELECT COUNT(*) FROM vagas")
            total_jobs = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM vagas WHERE aplicada=1")
            applied = c.fetchone()[0]

            c.execute("SELECT AVG(score) FROM vagas WHERE score > 0")
            avg_score = round(c.fetchone()[0] or 0, 1)

            c.execute("SELECT COUNT(*) FROM vagas WHERE status='entrevista'")
            interviews = c.fetchone()[0]

            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            c.execute("SELECT COUNT(*) FROM vagas WHERE data_encontrada >= ?", (cutoff,))
            new_24h = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM vagas WHERE score >= 7")
            high_score = c.fetchone()[0]

            c.execute("SELECT COUNT(DISTINCT fonte) FROM vagas")
            sources = c.fetchone()[0]

            conn.close()
            return {
                "total_jobs": total_jobs,
                "applied": applied,
                "avg_score": avg_score,
                "interviews": interviews,
                "new_24h": new_24h,
                "high_score": high_score,
                "sources": sources,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "week": datetime.now().strftime("Semana %U de %Y"),
            }
        except Exception as e:
            self.logger.error(f"Erro ao obter stats: {e}")
            return {
                "total_jobs": 0, "applied": 0, "avg_score": 0.0,
                "interviews": 0, "new_24h": 0, "high_score": 0,
                "sources": 0, "date": datetime.now().strftime("%Y-%m-%d"),
                "week": datetime.now().strftime("Semana %U de %Y"),
            }

    # ─────────────────────────────────────────────
    # GERAÇÃO DE CONTEÚDO
    # ─────────────────────────────────────────────
    def generate_twitter_post(self, stats: dict) -> str:
        if self.llm.available:
            prompt = (
                f"Crie um tweet em português sobre o Job Agent (ferramenta open source de busca de vagas).\n"
                f"Dados desta semana: {stats['total_jobs']} vagas monitoradas, "
                f"score médio {stats['avg_score']}/10, {stats['new_24h']} novas hoje.\n"
                f"Tom: direto, profissional, sem hashtags excessivas. Máximo 280 caracteres.\n"
                f"GitHub: {GITHUB_URL}\n"
                f"Responda APENAS com o texto do tweet."
            )
            result = self.llm.complete(prompt, max_tokens=100)
            if result:
                return result.strip()[:280]

        return (
            f"Job Agent monitorou {stats['total_jobs']} vagas esta semana. "
            f"Score médio: {stats['avg_score']}/10. "
            f"{stats['new_24h']} novas hoje. "
            f"Open source: {GITHUB_URL}"
        )

    def generate_linkedin_post(self, stats: dict) -> str:
        if self.llm.available:
            prompt = (
                f"Crie um post profissional para LinkedIn sobre o Job Agent.\n"
                f"Dados: {stats['total_jobs']} vagas monitoradas automaticamente, "
                f"{stats['applied']} candidaturas ativas, "
                f"{stats['interviews']} entrevistas geradas, "
                f"score médio de match {stats['avg_score']}/10.\n"
                f"Tom: profissional, inspirador. Inclua chamada para contribuir no GitHub: {GITHUB_URL}\n"
                f"Máximo 1000 caracteres. Responda APENAS com o texto do post."
            )
            result = self.llm.complete(prompt, max_tokens=300)
            if result:
                return result.strip()

        return (
            f"Automatizei minha busca de vagas com IA.\n\n"
            f"Esta semana: {stats['total_jobs']} vagas monitoradas em {stats['sources']} plataformas, "
            f"score médio de {stats['avg_score']}/10, "
            f"{stats['applied']} candidaturas ativas e {stats['interviews']} entrevistas.\n\n"
            f"Tudo 100% automático com Python + Claude AI.\n\n"
            f"Projeto open source: {GITHUB_URL}"
        )

    def generate_reddit_post(self, stats: dict) -> str:
        if self.llm.available:
            prompt = (
                f"Crie um post para r/brdev sobre o Job Agent (Python + IA para busca de vagas).\n"
                f"Tom: técnico, humilde, sem marketing excessivo.\n"
                f"Inclua: o que faz, como funciona, stats reais ({stats['total_jobs']} vagas, "
                f"{stats['avg_score']}/10 score médio), link GitHub: {GITHUB_URL}\n"
                f"Máximo 800 caracteres. Responda APENAS com o texto do post."
            )
            result = self.llm.complete(prompt, max_tokens=250)
            if result:
                return result.strip()

        return (
            f"Criei um agente Python que monitora {stats['total_jobs']} vagas automaticamente "
            f"e calcula score de match com IA (Claude). "
            f"Esta semana: score médio {stats['avg_score']}/10, {stats['applied']} candidaturas.\n\n"
            f"Open source: {GITHUB_URL}"
        )

    def generate_newsletter_html(self, stats: dict) -> str:
        """Gera HTML da newsletter semanal com dados reais."""
        if self.llm.available:
            prompt = (
                f"Gere HTML completo de newsletter semanal do Job Agent. "
                f"Use inline CSS. Max 600px largura. Tom profissional.\n"
                f"Dados reais: {stats['total_jobs']} vagas, {stats['applied']} candidaturas, "
                f"score médio {stats['avg_score']}/10, {stats['interviews']} entrevistas.\n"
                f"Inclua: header com emoji 🤖 e titulo 'Job Agent — {stats['week']}', "
                f"4 cards de métricas, botão 'Ver vagas' → {DASHBOARD_URL}/jobs, "
                f"rodapé com link GitHub {GITHUB_URL}.\n"
                f"Responda APENAS com o HTML, sem markdown."
            )
            html = self.llm.complete(prompt, max_tokens=1500)
            if html:
                return html.strip()

        return f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h1 style="color:#1D9E75">&#x1F916; Job Agent — {stats['week']}</h1>
  <table width="100%" cellpadding="10" style="border-collapse:separate;border-spacing:8px">
    <tr>
      <td style="background:#f0faf6;border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:bold;color:#1D9E75">{stats['total_jobs']}</div>
        <div style="color:#666;font-size:13px">Vagas monitoradas</div>
      </td>
      <td style="background:#f0faf6;border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:bold;color:#1D9E75">{stats['applied']}</div>
        <div style="color:#666;font-size:13px">Candidaturas</div>
      </td>
      <td style="background:#f0faf6;border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:bold;color:#1D9E75">{stats['avg_score']}/10</div>
        <div style="color:#666;font-size:13px">Score medio</div>
      </td>
      <td style="background:#f0faf6;border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:bold;color:#1D9E75">{stats['interviews']}</div>
        <div style="color:#666;font-size:13px">Entrevistas</div>
      </td>
    </tr>
  </table>
  <div style="text-align:center;margin:24px 0">
    <a href="{DASHBOARD_URL}/jobs"
       style="background:#1D9E75;color:white;padding:12px 28px;border-radius:8px;
              text-decoration:none;font-weight:bold">
      Ver vagas de hoje
    </a>
  </div>
  <hr style="border:none;border-top:1px solid #eee">
  <p style="color:#999;font-size:12px;text-align:center">
    Job Agent e 100% open source.
    <a href="{GITHUB_URL}" style="color:#1D9E75">Dar estrela no GitHub</a>
  </p>
</div>
""".strip()

    # ─────────────────────────────────────────────
    # PUBLICAÇÃO
    # ─────────────────────────────────────────────
    def save_posts_for_manual_publish(self, posts: dict) -> str:
        """Salva posts gerados em arquivo para publicação manual."""
        out_dir = Path(_BASE_DIR) / "logs" / "marketing"
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        path = out_dir / f"posts_{ts}.json"

        data = {
            "generated_at": datetime.now().isoformat(),
            "posts": posts,
            "instructions": {
                "twitter": "Cole o texto no Twitter/X",
                "linkedin": "Cole no LinkedIn como novo post",
                "reddit": "Poste em r/brdev ou r/devops_br",
            }
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.logger.info(f"Posts salvos em {path}")
        return str(path)

    def post_to_twitter(self, text: str) -> bool:
        """Publica tweet via Twitter API v2 (requer TWITTER_BEARER_TOKEN)."""
        if not self.twitter_token:
            return False
        try:
            import requests
            r = requests.post(
                "https://api.twitter.com/2/tweets",
                headers={"Authorization": f"Bearer {self.twitter_token}",
                         "Content-Type": "application/json"},
                json={"text": text},
                timeout=10,
            )
            if r.status_code in (200, 201):
                self.logger.info("Tweet publicado")
                return True
            self.logger.warning(f"Twitter: {r.status_code} {r.text[:100]}")
        except Exception as e:
            self.logger.error(f"Twitter error: {e}")
        return False

    def post_to_devto(self, title: str, body_markdown: str, tags: list) -> bool:
        """Publica artigo no Dev.to (requer DEVTO_API_KEY)."""
        if not self.devto_key:
            return False
        try:
            import requests
            r = requests.post(
                "https://dev.to/api/articles",
                headers={"api-key": self.devto_key, "Content-Type": "application/json"},
                json={"article": {"title": title, "body_markdown": body_markdown,
                                  "tags": tags, "published": True}},
                timeout=10,
            )
            if r.status_code in (200, 201):
                self.logger.info(f"Dev.to artigo publicado: {r.json().get('url')}")
                return True
            self.logger.warning(f"Dev.to: {r.status_code} {r.text[:100]}")
        except Exception as e:
            self.logger.error(f"Dev.to error: {e}")
        return False

    def update_readme_with_stats(self, stats: dict) -> bool:
        """
        Atualiza a seção de métricas ao vivo no README.md.
        Insere/substitui o bloco entre markers <!-- STATS-START --> e <!-- STATS-END -->.
        """
        readme_path = Path(_BASE_DIR) / "README.md"
        if not readme_path.exists():
            return False

        stats_block = (
            f"<!-- STATS-START -->\n"
            f"## Métricas ao Vivo\n\n"
            f"| Métrica | Valor |\n"
            f"|---------|-------|\n"
            f"| Vagas monitoradas | **{stats['total_jobs']}** |\n"
            f"| Candidaturas ativas | **{stats['applied']}** |\n"
            f"| Score médio de match | **{stats['avg_score']}/10** |\n"
            f"| Entrevistas geradas | **{stats['interviews']}** |\n"
            f"| Novas vagas (24h) | **{stats['new_24h']}** |\n"
            f"| Vagas com score ≥ 7 | **{stats['high_score']}** |\n\n"
            f"_Atualizado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n"
            f"<!-- STATS-END -->"
        )

        content = readme_path.read_text(encoding="utf-8")

        if "<!-- STATS-START -->" in content and "<!-- STATS-END -->" in content:
            start = content.index("<!-- STATS-START -->")
            end = content.index("<!-- STATS-END -->") + len("<!-- STATS-END -->")
            new_content = content[:start] + stats_block + content[end:]
        else:
            new_content = content + "\n\n" + stats_block + "\n"

        readme_path.write_text(new_content, encoding="utf-8")
        self.logger.info("README.md atualizado com métricas ao vivo")
        return True

    def _notify_telegram(self, posts: dict, stats: dict, published: list, posts_path: str):
        """Envia resumo do ciclo de marketing via Telegram."""
        try:
            from notifiers.notifier_telegram import enviar_telegram

            lines = [
                "*Job Agent — Ciclo de Marketing*",
                f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                "",
                f"Vagas: {stats['total_jobs']} | Score: {stats['avg_score']}/10 | "
                f"Candidaturas: {stats['applied']}",
                "",
                "Posts gerados e salvos em logs/marketing/",
            ]

            if published:
                lines.append(f"Publicados automaticamente: {', '.join(published)}")
            else:
                lines.append("Publicacao manual necessaria (Twitter/LinkedIn/Reddit)")

            lines.extend([
                "",
                "_Twitter:_",
                f"`{posts.get('twitter', '')[:200]}`",
            ])

            enviar_telegram("\n".join(lines))
        except Exception as e:
            self.logger.warning(f"Falha ao notificar marketing: {e}")

    # ─────────────────────────────────────────────
    # CICLO PRINCIPAL
    # ─────────────────────────────────────────────
    def run(self, context: dict = None) -> dict:
        """
        Ciclo completo de marketing autônomo:
        1. Coleta stats reais do banco
        2. Gera posts para Twitter, LinkedIn e Reddit
        3. Envia newsletter semanal via MailerLite (se configurado)
        4. Atualiza README com métricas ao vivo
        5. Salva posts para publicação manual
        6. Publica onde API está configurada (Twitter, Dev.to)
        7. Notifica Telegram com resumo + posts prontos para copiar
        8. Push automático para GitHub
        """
        self.logger.info("=== MarketerAgent — ciclo de marketing iniciado ===")
        stats = self._get_real_stats()

        from intelligence.mailerlite_client import get_mailerlite_client
        ml = get_mailerlite_client()

        results: dict = {"stats": stats, "newsletter_sent": False,
                         "readme_updated": False, "posts_saved": False,
                         "published": [], "git_pushed": False}

        # 1. Newsletter via MailerLite
        try:
            if ml.available:
                html = self.generate_newsletter_html(stats)
                week = datetime.now().strftime("%Y — Semana %U")
                sent = ml.send_weekly_newsletter(
                    subject=f"Job Agent — Resumo {week}",
                    html_content=html,
                )
                results["newsletter_sent"] = sent
                if sent:
                    self.logger.info("Newsletter semanal enviada via MailerLite")
            else:
                self.logger.info("MailerLite nao configurado — newsletter pulada")
        except Exception as e:
            self.logger.error(f"Newsletter error: {e}")

        # 2. Posts para redes sociais
        posts: dict = {}
        try:
            posts = {
                "twitter": self.generate_twitter_post(stats),
                "linkedin": self.generate_linkedin_post(stats),
                "reddit": self.generate_reddit_post(stats),
            }
            results["posts_path"] = self.save_posts_for_manual_publish(posts)
            results["posts_saved"] = True
        except Exception as e:
            self.logger.error(f"Posts generation error: {e}")

        # 3. Publicação automática onde API disponível
        if self.twitter_token:
            if self.post_to_twitter(posts.get("twitter", "")):
                results["published"].append("twitter")
        if self.devto_key:
            title = f"Job Agent — {stats['total_jobs']} vagas monitoradas automaticamente"
            if self.post_to_devto(title, posts.get("linkedin", ""),
                                  ["python", "opensource", "automation"]):
                results["published"].append("devto")

        # 4. Atualiza README
        results["readme_updated"] = self.update_readme_with_stats(stats)

        # 5. Notifica Telegram
        self._notify_telegram(posts, stats, results["published"],
                              results.get("posts_path", "logs/marketing/"))

        # 6. Push automático
        try:
            from agents.agent_git import GitAgent
            git = GitAgent()
            git_result = git.run({
                "message": f"chore: marketing update {datetime.now().strftime('%Y-%m-%d')}",
                "notify": False,
            })
            results["git_pushed"] = git_result.get("pushed", False)
        except Exception as e:
            self.logger.error(f"Git push error: {e}")

        self.log_action("marketing_cycle", "success", {
            "newsletter_sent": results["newsletter_sent"],
            "readme_updated": results["readme_updated"],
            "published": results["published"],
            "git_pushed": results["git_pushed"],
        })

        return results
