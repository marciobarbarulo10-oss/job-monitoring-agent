"""
Agente Git — faz push automático das mudanças para o GitHub.

Responsabilidades:
- Detectar arquivos modificados (código, configs)
- Gerar mensagem de commit semântica
- Push com retry automático (3 tentativas + backoff)
- Notificar Telegram sobre cada push

Nunca commita: .env, data/, logs/, __pycache__
"""
import subprocess
import time
import logging
from datetime import datetime
from agents import BaseAgent

logger = logging.getLogger(__name__)


class GitAgent(BaseAgent):

    def __init__(self):
        super().__init__("git")
        self.branch = self._get_branch()
        self.remote = "origin"

    def _get_branch(self) -> str:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout.strip() or "main"
        except Exception:
            return "main"

    def _git(self, args: list, timeout: int = 30) -> tuple:
        try:
            r = subprocess.run(
                ["git"] + args, capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except Exception as e:
            return False, str(e)

    def has_changes(self) -> bool:
        ok, out = self._git(["status", "--porcelain"])
        return ok and bool(out.strip())

    def changed_files(self) -> list:
        ok, out = self._git(["status", "--porcelain"])
        if not ok or not out:
            return []
        result = []
        for line in out.strip().split("\n"):
            if line.strip():
                result.append({"status": line[:2].strip(), "file": line[3:].strip()})
        return result

    def remote_url(self) -> str:
        ok, url = self._git(["remote", "get-url", self.remote])
        if ok:
            return url.replace("git@github.com:", "https://github.com/").strip()
        return ""

    def _commit_message(self, files: list, custom: str = None) -> str:
        if custom:
            return custom
        if not files:
            return f"chore: auto-sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        names = [f["file"] for f in files]
        parts = []
        if any("agents/" in f for f in names):
            parts.append("agents")
        if any("api/" in f for f in names):
            parts.append("api")
        if any("frontend/" in f for f in names):
            parts.append("frontend")
        if any("intelligence/" in f for f in names):
            parts.append("intelligence")
        if any("scripts/" in f for f in names):
            parts.append("scripts")
        if any("core/" in f or "scrapers/" in f for f in names):
            parts.append("core")

        scope = f"({', '.join(parts)})" if parts else ""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        n = len(files)
        if n == 1:
            fname = names[0].split("/")[-1]
            return f"chore{scope}: update {fname} — {ts}"
        return f"chore{scope}: auto-sync {n} files — {ts}"

    def push(self, max_retries: int = 3) -> tuple:
        for attempt in range(1, max_retries + 1):
            self.logger.info(f"Push tentativa {attempt}/{max_retries}...")
            ok, out = self._git(["push", self.remote, self.branch], timeout=60)
            if ok:
                return True, out
            self.logger.warning(f"Push falhou ({attempt}): {out[:100]}")
            if attempt < max_retries:
                time.sleep(10 * attempt)
        return False, f"falhou apos {max_retries} tentativas"

    def run(self, context: dict = None) -> dict:
        ctx = context or {}
        custom_msg = ctx.get("message")
        force = ctx.get("force", False)
        notify = ctx.get("notify", True)

        start = time.time()
        files = self.changed_files()

        if not files and not force:
            self.logger.info("Git: sem mudancas para commitar.")
            return {
                "pushed": False,
                "changed_files": 0,
                "branch": self.branch,
                "remote_url": self.remote_url(),
                "note": "nada para commitar",
            }

        ok, out = self._git(["add", "-A"])
        if not ok:
            return {"pushed": False, "error": f"git add: {out}"}

        message = self._commit_message(files, custom_msg)
        ok, out = self._git(["commit", "-m", message])
        if not ok:
            if "nothing to commit" in out.lower():
                return {"pushed": False, "changed_files": 0, "note": "nada para commitar"}
            return {"pushed": False, "error": f"git commit: {out}"}

        self.logger.info(f"Commit: {message}")

        ok, out = self.push()
        duration = round(time.time() - start, 1)
        url = self.remote_url()

        result = {
            "pushed": ok,
            "commit_message": message,
            "changed_files": len(files),
            "branch": self.branch,
            "remote_url": url,
            "duration_seconds": duration,
            "error": None if ok else out,
        }

        self.log_action("git_push", "success" if ok else "error", result, int(duration * 1000))

        if notify:
            self._notify(result)

        return result

    def _notify(self, result: dict):
        try:
            from notifiers.notifier_telegram import enviar_telegram

            if result["pushed"]:
                msg = (
                    f"*GitHub Push — Job Agent*\n"
                    f"Push realizado\n"
                    f"Branch: `{result['branch']}`\n"
                    f"Arquivos: {result['changed_files']} alterado(s)\n"
                    f"Commit: _{result['commit_message']}_"
                )
            else:
                msg = (
                    f"*GitHub Push FALHOU — Job Agent*\n"
                    f"Branch: `{result['branch']}`\n"
                    f"Erro: `{str(result.get('error', ''))[:100]}`"
                )
            enviar_telegram(msg)
        except Exception as e:
            self.logger.warning(f"Falha ao notificar push: {e}")
