"""
cli.py — Interface de linha de comando para o Job Agent v2.0
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


# ── COMANDOS EXISTENTES ───────────────────────────────────────────────────────

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
        if args.grade:
            query = query.filter(Vaga.score_grade == args.grade.upper())

        vagas = query.order_by(Vaga.score.desc()).limit(args.limit).all()

        table = Table(
            title=f"Vagas ({len(vagas)} resultados)",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("ID",      style="dim", width=4)
        table.add_column("Score",   style="bold yellow", width=6)
        table.add_column("Grade",   style="bold", width=5)
        table.add_column("Status",  style="cyan", width=12)
        table.add_column("Titulo",  style="bold white", width=35)
        table.add_column("Empresa", style="green", width=22)
        table.add_column("Fonte",   style="magenta", width=10)
        table.add_column("Janela",  style="red", width=7)

        for v in vagas:
            status_color = {
                "nova": "white", "aplicada": "blue", "em_analise": "yellow",
                "entrevista": "green", "rejeitada": "red", "encerrada": "dim",
                "suspeita": "red", "proposta": "bright_green", "cv_gerado": "cyan",
            }.get(v.status, "white")

            grade_color = {
                "A": "bright_green", "B": "green", "C": "yellow",
                "D": "orange3", "F": "red",
            }.get(v.score_grade or "", "white")

            table.add_row(
                str(v.id),
                f"{v.score:.1f}",
                f"[{grade_color}]{v.score_grade or '-'}[/{grade_color}]",
                f"[{status_color}]{v.status}[/{status_color}]",
                (v.titulo or "")[:35],
                (v.empresa or "")[:22],
                v.fonte or "",
                "SIM" if v.is_early_applicant else "",
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
        title="Resumo do Job Agent v2.0",
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
            console.print(
                f"  {h.timestamp.strftime('%d/%m %H:%M')}  "
                f"{h.status_old} -> [bold]{h.status_new}[/bold]  {h.detalhes or ''}"
            )
    finally:
        db.close()


# ── NOVOS COMANDOS v2.0 ───────────────────────────────────────────────────────

def cmd_cv(args):
    """Gera CV customizado para uma vaga específica."""
    db = Session()
    try:
        vaga = db.query(Vaga).filter_by(id=args.job_id).first()
        if not vaga:
            console.print(f"[red]Vaga ID {args.job_id} nao encontrada.[/red]")
            return

        console.print(f"[bold blue]Gerando CV para: {vaga.titulo} — {vaga.empresa}[/bold blue]")

        from core.cv_generator import CVGenerator
        cg = CVGenerator()
        vaga_dict = {
            "id": vaga.id, "titulo": vaga.titulo, "empresa": vaga.empresa,
            "localizacao": vaga.localizacao, "descricao": vaga.descricao,
            "url": vaga.url, "score": vaga.score, "grade": vaga.score_grade,
        }
        caminho = cg.generate(vaga_dict)

        if caminho:
            console.print(f"[green]CV gerado: {caminho}[/green]")
        else:
            console.print("[red]Falha ao gerar CV. Verifique os logs.[/red]")
    finally:
        db.close()


def cmd_feedback(args):
    """Registra o outcome de uma candidatura."""
    from core.feedback_engine import FeedbackEngine, VALID_OUTCOMES

    outcome = args.outcome.lower().strip()
    if outcome not in VALID_OUTCOMES:
        console.print(f"[red]Outcome invalido: '{outcome}'[/red]")
        console.print(f"Opcoes validas: {', '.join(sorted(VALID_OUTCOMES))}")
        return

    fe = FeedbackEngine()
    ok = fe.register_outcome(args.job_id, outcome, args.notas or "")

    if ok:
        console.print(f"[green]OK: Feedback '{outcome}' registrado para vaga ID {args.job_id}[/green]")
    else:
        console.print(f"[red]Falha ao registrar feedback. Verifique os logs.[/red]")


def cmd_mercado(args):
    """Gera e exibe relatório de tendências de mercado."""
    console.print("[bold blue]Gerando relatorio de mercado...[/bold blue]")
    from core.market_intelligence import MarketIntelligence

    mi = MarketIntelligence()
    report = mi.weekly_report()

    if not report:
        console.print("[red]Nao foi possivel gerar o relatorio.[/red]")
        return

    panel = Panel(
        f"""
[bold]Semana:[/bold]           {report.get('semana', '—')}
[bold]Total vagas:[/bold]      {report.get('total_vagas', 0)}
[bold]Score medio:[/bold]      {report.get('score_medio', 0)}/10
[bold]Variacao:[/bold]         {report.get('variacao_semana_pct', 0)}% vs semana anterior

[bold yellow]Top Keywords:[/bold yellow]
  {', '.join(k['keyword'] for k in report.get('top_keywords', [])[:8])}

[bold green]Top Empresas:[/bold green]
  {', '.join(e['empresa'] for e in report.get('top_empresas', [])[:5])}

[bold cyan]Modalidade:[/bold cyan]
  Remoto: {report.get('modalidade', {}).get('remoto', 0)} |
  Hibrido: {report.get('modalidade', {}).get('hibrido', 0)} |
  Presencial: {report.get('modalidade', {}).get('presencial', 0)}
        """,
        title="Relatorio de Mercado",
        border_style="blue",
    )
    console.print(panel)


def cmd_manutencao(args):
    """Executa manutenção do pipeline (dedup + normalize + health check)."""
    console.print("[bold blue]Executando manutencao do pipeline...[/bold blue]")
    from core.pipeline_integrity import PipelineIntegrity

    pi = PipelineIntegrity()
    rel = pi.run_maintenance()

    saude = rel.get("saude", {})
    panel = Panel(
        f"""
[bold]Duplicatas removidas:[/bold]  {rel.get('duplicatas_removidas', 0)}
[bold]Status normalizados:[/bold]   {rel.get('status_normalizados', 0)}
[bold]Total no banco:[/bold]        {saude.get('total_jobs', 0)}
[bold]Sem score:[/bold]             {saude.get('jobs_sem_score', 0)}
[bold]CVs orfaos:[/bold]            {saude.get('cvs_orfaos', 0)}
[bold]Taxa conversao:[/bold]        {saude.get('taxa_conversao', 0)}%
[bold green]Saude:[/bold green]                 {saude.get('status', '—')}
        """,
        title="Manutencao do Pipeline",
        border_style="green",
    )
    console.print(panel)


def cmd_calibrar(args):
    """Recalibra o scoring baseado nos feedbacks registrados."""
    console.print("[bold blue]Recalibrando scoring...[/bold blue]")
    from core.feedback_engine import FeedbackEngine

    fe = FeedbackEngine()
    resultado = fe.recalibrate(min_samples=args.min_samples)

    status = resultado.get("status")
    if status == "amostras_insuficientes":
        console.print(
            f"[yellow]Amostras insuficientes: {resultado.get('amostras', 0)} / "
            f"{resultado.get('minimo', 5)} necessarias[/yellow]"
        )
    elif status == "calibrado":
        console.print(f"[green]Calibracao concluida com {resultado.get('amostras', 0)} amostras[/green]")
        console.print(f"[cyan]Insight: {resultado.get('insight', '—')}[/cyan]")

        table = Table(title="Calibracao por Faixa de Score", box=box.ROUNDED)
        table.add_column("Faixa Score")
        table.add_column("Taxa Entrevista %")
        table.add_column("Amostras")
        for faixa, data in resultado.get("calibration", {}).items():
            table.add_row(
                faixa,
                f"{data.get('taxa_conversao_pct', 0)}%",
                str(data.get("amostras", 0)),
            )
        console.print(table)
    else:
        console.print(f"[red]Erro: {resultado.get('erro', status)}[/red]")


def cmd_cvs(args):
    """Lista CVs gerados."""
    from core.cv_generator import CVGenerator

    cg = CVGenerator()
    exports = cg.list_exports()

    if not exports:
        console.print("[dim]Nenhum CV gerado ainda.[/dim]")
        return

    table = Table(title=f"CVs Gerados ({len(exports)})", box=box.ROUNDED)
    table.add_column("ID", width=4)
    table.add_column("Vaga", width=30)
    table.add_column("Empresa", width=20)
    table.add_column("Score", width=6)
    table.add_column("Gerado em", width=16)
    table.add_column("Arquivo", width=8)

    for e in exports:
        existe = "[green]OK[/green]" if e["exists"] else "[red]AUSENTE[/red]"
        table.add_row(
            str(e["id"]),
            (e["titulo"] or "")[:30],
            (e["empresa"] or "")[:20],
            f"{e['score']:.1f}",
            (e["created_at"] or "")[:16],
            existe,
        )
    console.print(table)


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Agent CLI v2.0")
    sub = parser.add_subparsers(dest="cmd")

    # listar
    p_list = sub.add_parser("listar", help="Lista vagas do banco")
    p_list.add_argument("--status", help="Filtrar por status")
    p_list.add_argument("--min-score", type=float, dest="min_score")
    p_list.add_argument("--fonte", help="Filtrar por fonte")
    p_list.add_argument("--grade", help="Filtrar por grade (A/B/C/D/F)")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_listar)

    # aplicar
    p_aplicar = sub.add_parser("aplicar", help="Marca vaga como aplicada")
    p_aplicar.add_argument("url")
    p_aplicar.add_argument("--notas")
    p_aplicar.set_defaults(func=cmd_aplicar)

    # status
    p_status = sub.add_parser("status", help="Atualiza status de uma vaga")
    p_status.add_argument("id", type=int)
    p_status.add_argument(
        "novo_status",
        choices=["aplicada", "em_analise", "entrevista", "rejeitada", "encerrada", "proposta"],
    )
    p_status.add_argument("--detalhes")
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

    # cv
    p_cv = sub.add_parser("cv", help="Gera CV customizado para uma vaga")
    p_cv.add_argument("job_id", type=int, help="ID da vaga")
    p_cv.set_defaults(func=cmd_cv)

    # feedback
    p_fb = sub.add_parser("feedback", help="Registra outcome de uma candidatura")
    p_fb.add_argument("job_id", type=int, help="ID da vaga")
    p_fb.add_argument(
        "outcome",
        choices=["entrevista", "rejeicao", "sem_resposta", "proposta"],
        help="Resultado da candidatura",
    )
    p_fb.add_argument("--notas", help="Observacoes adicionais")
    p_fb.set_defaults(func=cmd_feedback)

    # mercado
    p_mercado = sub.add_parser("mercado", help="Gera relatorio de tendencias de mercado")
    p_mercado.set_defaults(func=cmd_mercado)

    # manutencao
    p_man = sub.add_parser("manutencao", help="Executa manutencao do pipeline")
    p_man.set_defaults(func=cmd_manutencao)

    # calibrar
    p_cal = sub.add_parser("calibrar", help="Recalibra pesos de scoring com base nos feedbacks")
    p_cal.add_argument("--min-samples", type=int, default=5, dest="min_samples")
    p_cal.set_defaults(func=cmd_calibrar)

    # cvs
    p_cvs = sub.add_parser("cvs", help="Lista CVs gerados")
    p_cvs.set_defaults(func=cmd_cvs)

    args = parser.parse_args()
    if args.cmd:
        args.func(args)
    else:
        parser.print_help()
