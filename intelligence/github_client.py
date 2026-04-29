"""
Cliente GitHub — dados reais do repositório via API REST.
Substitui a dependência do Windsor.ai com chamada direta.
Custo zero — API gratuita com token pessoal (5000 req/hora).
"""
import os
import re
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

REPO = "marciobarbarulo10-oss/job-monitoring-agent"
GITHUB_API = "https://api.github.com"


class GitHubClient:

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "JobAgent/1.0",
        })
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def get_repo_stats(self) -> dict:
        """Stars, forks, watchers, issues, linguagem e metadados do repositório."""
        try:
            r = self.session.get(f"{GITHUB_API}/repos/{REPO}", timeout=10)
            r.raise_for_status()
            data = r.json()
            return {
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "watchers": data.get("watchers_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "language": data.get("language", "Python"),
                "size_kb": data.get("size", 0),
                "description": data.get("description", ""),
                "topics": data.get("topics", []),
                "created_at": data.get("created_at", ""),
                "pushed_at": data.get("pushed_at", ""),
                "html_url": data.get("html_url", f"https://github.com/{REPO}"),
                "default_branch": data.get("default_branch", "main"),
            }
        except Exception as e:
            logger.error(f"GitHub API error (repo stats): {e}")
            return {
                "stars": 0, "forks": 0, "watchers": 0,
                "open_issues": 0, "language": "Python",
                "html_url": f"https://github.com/{REPO}",
            }

    def get_commit_count(self) -> int:
        """Total de commits via paginação no header Link."""
        try:
            r = self.session.get(
                f"{GITHUB_API}/repos/{REPO}/commits",
                params={"per_page": 1},
                timeout=10,
            )
            link = r.headers.get("Link", "")
            if 'rel="last"' in link:
                match = re.search(r'page=(\d+)>; rel="last"', link)
                if match:
                    return int(match.group(1))
            return len(r.json()) if r.status_code == 200 else 0
        except Exception as e:
            logger.error(f"GitHub API error (commit count): {e}")
            return 0

    def get_recent_commits(self, limit: int = 5) -> list:
        """Commits recentes para o relatório."""
        try:
            r = self.session.get(
                f"{GITHUB_API}/repos/{REPO}/commits",
                params={"per_page": limit},
                timeout=10,
            )
            r.raise_for_status()
            commits = []
            for c in r.json():
                commits.append({
                    "sha": c["sha"][:7],
                    "message": c["commit"]["message"].split("\n")[0][:60],
                    "date": c["commit"]["author"]["date"][:10],
                    "author": c["commit"]["author"]["name"],
                })
            return commits
        except Exception as e:
            logger.error(f"GitHub API error (recent commits): {e}")
            return []

    def get_full_stats(self) -> dict:
        """Stats completos para posts, dashboard e README."""
        repo = self.get_repo_stats()
        commits = self.get_commit_count()
        recent = self.get_recent_commits(3)
        return {
            **repo,
            "total_commits": commits,
            "recent_commits": recent,
            "github_url": f"https://github.com/{REPO}",
            "fetched_at": datetime.now().isoformat(),
        }


_client: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    global _client
    if _client is None:
        _client = GitHubClient()
    return _client
