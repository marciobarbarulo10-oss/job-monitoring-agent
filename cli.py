"""
cli.py — Interface de linha de comando para o Job Agent
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from datetime import datetime

from core.models import Vaga, StatusHistory, Session, init_db
from core.agent import marcar_aplicada, ciclo_completo, gerar_resumo

console = Console()


def cmd_listar(args):
    """Lista vagas do banco com filtros opcionais."""
    db = Session()
    try:
        query = db.query(Vaga)

        if args.status:
            query = query.filter(Vaga.status == args.status)
        if args.min_score:
            query = query.filter(Vaga.score >= args.min_score)
        if args.fonte:
            query = query.filter(Vaga.fonte == args.fonte)

        vagas = query.order_by(Vaga.score.desc()).limit(args.limit).all()

        table = Table(
            title=f"Vagas ({len(vagas)} resultados)",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("ID",       style="dim", width=4)
        table.add_column("Score",    style="bold yellow", width=6)
        table.add_column("Status",   style="cyan", width=12)
        table.add_column("Titulo",   style="bold white", width=35)
        table.add_column("Empresa",  style="green", width=25)
        table.add_column("Fonte",    style="magenta", width=10)
        table.add_column("Aplicada", style="blue", width=8)

        for v in vagas:
            status_color = {
                "nova": "white", "aplicada": "blue", "em_analise": "yellow",
                "entrevista": "green", "rejeitada": "red", "encerrada": "dim",
            }.get(v.status, "white")

            table.add_row(
                str(v.id),
                f"{v.score:.1f}",
                f"[{status_color}]{v.status}[/{status_color}]",
                v.titulo[:35],
                (v.empresa or "")[:25],
                v.fonte,
                "SIM" if v.aplicada else "nao",
            )

        console.print(table)
    finally:
        db.close()


def cmd_aplicar(args):
    """Marca uma vaga como aplicada e inicia monitoramento."""
    marcar_aplicada(args.url, args.notas or "")
    console.print("[green]OK: Vaga marcada como aplicada e monitoramento ativado![/green]")


def cmd_status(args):
    """Atualiza o status de uma vaga manualmente."""
    db = Session()
    try:
        vaga = db.query(Vaga).filter_by(id=args.id).first()
        if not vaga:
            console.print(f"[red]Vaga ID {args.id} nao encontrada.[/red]")
            return

        status_old = vaga.status
        hist = StatusHistory(
            vaga_id=vaga.id,
            status_old=status_old,
            status_new=args.novo_status,
            timestamp=datetime.utcnow(),
            detalhes=args.detalhes or "",
        )
        db.add(hist)
        vaga.status = args.novo_status
        db.commit()
        console.print(f"[green]OK: Status atualizado: {status_old} -> {args.novo_status}[/green]")
    finally:
        db.close()


def cmd_resumo(args):
    """Mostra resumo geral das candidaturas."""
    stats = gerar_resumo()
    panel = Panel(
        f"""
[bold]Total de vagas no banco:[/bold]  {stats['total']}
[bold yellow]Novas (nao notificadas):[/bold yellow] {stats['novas']}
[bold blue]Aplicadas:[/bold blue]              {stats['aplicadas']}
[bold cyan]Em analise:[/bold cyan]             {stats['em_analise']}
[bold green]Entrevistas:[/bold green]           {stats['entrevistas']}
[bold red]Rejeitadas:[/bold red]            {stats['rejeitadas']}
[bold]Score >= 7.0:[/bold]            {stats['high_score']}
        """,
        title="Resumo do Job Agent",
        border_style="blue",
    )
    console.print(panel)


def cmd_rodar(args):
    """Executa um ciclo completo manualmente."""
    console.print("[bold blue]Iniciando ciclo completo...[/bold blue]")
    init_db()
    stats = ciclo_completo()
    console.print(f"[green]Ciclo concluido: {stats}[/green]")


def cmd_historico(args):
    """Mostra historico de status de uma vaga."""
    db = Session()
    try:
        vaga = db.query(Vaga).filter_by(id=args.id).first()
        if not vaga:
            console.print(f"[red]Vaga ID {args.id} nao encontrada.[/red]")
            return

        console.print(f"\n[bold]{vaga.titulo}[/bold] -- {vaga.empresa}")
        console.print(f"URL: {vaga.url}\n")

        historico = db.query(StatusHistory).filter_by(vaga_id=args.id).order_by(StatusHistory.timestamp).all()
        if not historico:
            console.print("[dim]Sem historico de status.[/dim]")
            return

        for h in historico:
            console.print(f"  {h.timestamp.strftime('%d/%m %H:%M')}  {h.status_old} -> [bold]{h.status_new}[/bold]  {h.detalhes or ''}")
    finally:
        db.close()


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Agent CLI")
    sub = parser.add_subparsers(dest="cmd")

    # listar
    p_list = sub.add_parser("listar", help="Lista vagas do banco")
    p_list.add_argument("--status", help="Filtrar por status (nova, aplicada, entrevista...)")
    p_list.add_argument("--min-score", type=float, dest="min_score", help="Score minimo")
    p_list.add_argument("--fonte", help="Filtrar por fonte (linkedin, gupy...)")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_listar)

    # aplicar
    p_aplicar = sub.add_parser("aplicar", help="Marca vaga como aplicada e inicia monitoramento")
    p_aplicar.add_argument("url", help="URL da vaga")
    p_aplicar.add_argument("--notas", help="Notas sobre a candidatura")
    p_aplicar.set_defaults(func=cmd_aplicar)

    # status
    p_status = sub.add_parser("status", help="Atualiza status de uma vaga")
    p_status.add_argument("id", type=int, help="ID da vaga")
    p_status.add_argument("novo_status", choices=["aplicada", "em_analise", "entrevista", "rejeitada", "encerrada"])
    p_status.add_argument("--detalhes", help="Detalhes da mudanca")
    p_status.set_defaults(func=cmd_status)

    # resumo
    p_resumo = sub.add_parser("resumo", help="Resumo geral das candidaturas")
    p_resumo.set_defaults(func=cmd_resumo)

    # rodar
    p_rodar = sub.add_parser("rodar", help="Executa um ciclo completo agora")
    p_rodar.set_defaults(func=cmd_rodar)

    # historico
    p_hist = sub.add_parser("historico", help="Historico de status de uma vaga")
    p_hist.add_argument("id", type=int)
    p_hist.set_defaults(func=cmd_historico)

    args = parser.parse_args()
    if args.cmd:
        args.func(args)
    else:
        parser.print_help()
