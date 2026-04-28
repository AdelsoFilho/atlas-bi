"""
portfolio_demo.py — Atlas BI Risk Engine
Relatório executivo completo de carteira cooperativa.

Execução:
    python -m risk_engine.portfolio_demo

Saída:
  1. Painel de qualidade da carteira
  2. Distribuição de PCLD por nível BCB
  3. Stress tests (Selic, Agro, Garantia)
  4. Sumário para o Conselho de Administração
  5. DataFrame exportado em CSV (opcional)
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 no Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
from datetime import date

import pandas as pd

from .portfolio_mock import gerar_carteira_mock
from .portfolio_engine import RiskEngine, RelatorioExecutivo, ResultadoStress
from .portfolio_models import NivelRiscoBCB, PCLD_PERCENTUAIS

# ─── Formatadores ─────────────────────────────────────────────────────────────

def _brl(v: float) -> str:
    return f"R$ {v:>16,.2f}"

def _pct(v: float) -> str:
    return f"{v:>6.2f}%"

def _bar(pct: float, width: int = 30) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)

SEP  = "─" * 76
SEP2 = "═" * 76


# ─── Impressão do Relatório ──────────────────────────────────────────────────

def _print_cabecalho(rel: RelatorioExecutivo) -> None:
    print(f"\n{SEP2}")
    print("  ATLAS BI — GESTÃO DE CARTEIRA DE CRÉDITO COOPERATIVO")
    print(f"  Posição: {rel.data_posicao}  |  Modelo: RiskEngine v1.0  |  DRO 5050 S3")
    print(SEP2)


def _print_visao_geral(rel: RelatorioExecutivo) -> None:
    print(f"\n{'  VISÃO GERAL DA CARTEIRA':^76}")
    print(SEP)
    print(f"  {'Saldo Total da Carteira':<40} {_brl(rel.saldo_carteira_brl)}")
    print(f"  {'Total de Operações':<40} {rel.total_operacoes:>20}")
    print(f"  {'Total de Associados':<40} {rel.total_associados:>20}")
    print(f"  {'Score Médio Cooperativo':<40} {rel.score_medio_cooperativo:>19.1f}")
    print(f"  {'Carteira AA/A/B (boa qualidade)':<40} {_pct(rel.pct_carteira_aa_b):>20}")
    print(SEP)
    print(f"  {'QUALIDADE — INDICADORES DE RISCO':^76}")
    print(SEP)

    # Semáforo de inadimplência
    def _semaforo_inadi(v: float) -> str:
        if v < 3:   return f"[VERDE ] {_pct(v)}"
        if v < 7:   return f"[AMARELO] {_pct(v)}"
        return            f"[VERMELHO] {_pct(v)}"

    print(f"  {'Inadimplência D-H (NPL BCB)':<40} {_semaforo_inadi(rel.inadimplencia_d_h_pct):>20}")
    print(f"  {'Inadimplência >90 dias (critério BIS)':<40} {_semaforo_inadi(rel.inadimplencia_90d_pct):>20}")
    print(f"  {'Operações Renegociadas / Total':<40} {_pct(rel.operacoes_renegociadas_pct):>20}")
    print(SEP)
    print(f"  {'CONCENTRAÇÃO DE CARTEIRA':^76}")
    print(SEP)
    print(f"  {'Top-10 devedores / Saldo Total':<40} {_pct(rel.concentracao_top10_pct):>20}  {'[ALERTA] Limite prudencial: 25%' if rel.concentracao_top10_pct > 25 else '[OK]':>10}")
    print(f"  {'Agro (Custeio + Investimento)':<40} {_pct(rel.concentracao_agro_pct):>20}")
    print(f"  {'Comércio / Varejo':<40} {_pct(rel.concentracao_varejo_pct):>20}")
    print(f"  {'Imobiliário / Indústria':<40} {_pct(rel.concentracao_imob_pct):>20}")


def _print_pcld(rel: RelatorioExecutivo, carteira_result) -> None:
    from .portfolio_engine import ResultadoPCLD
    # Recalcula para exibição — já calculado dentro de generate_executive_report
    print(f"\n{SEP}")
    print(f"  {'PCLD — PROVISÃO PARA CRÉDITOS DE LIQUIDAÇÃO DUVIDOSA':^76}")
    print(f"  {'Res. CMN 2.682/99 | Base: Saldo Devedor por Nível de Risco':^76}")
    print(SEP)
    print(f"  {'Nível':<6} {'Provisão%':>10} {'Qtd Ops':>8} {'Saldo':>18} {'PCLD':>16}  Barra")
    print(SEP)

    for nivel in NivelRiscoBCB:
        dados = carteira_result.por_nivel[nivel.value]
        qtd   = dados["qtd_ops"]
        saldo = dados["saldo_brl"]
        pcld  = dados["pcld_brl"]
        pct   = dados["pcld_percentual"]

        if qtd == 0:
            continue

        icone = {
            "AA": "✅", "A": "✅", "B": "⚠️ ", "C": "⚠️ ",
            "D": "🔴", "E": "🔴", "F": "🔴", "G": "🔴", "H": "🔴",
        }.get(nivel.value, " ")

        bar_pct = saldo / max(carteira_result.saldo_total_carteira_brl, 1) * 100
        bar = _bar(bar_pct, 12)
        print(f"  {icone}{nivel.value:<4}  {pct:>9.1f}%  {qtd:>7}  {_brl(saldo)}  {_brl(pcld)}  {bar}")

    print(SEP)
    print(f"  {'Provisão Específica (B–H)':<50} {_brl(carteira_result.pcld_especifica_brl)}")
    print(f"  {'Provisão Coletiva (AA/A — risco latente)':<50} {_brl(carteira_result.pcld_coletiva_brl)}")
    print(f"  {'─' * 68}")
    print(f"  {'PCLD TOTAL NECESSÁRIA':<50} {_brl(carteira_result.pcld_total_brl)}")
    print(f"  {'Índice PCLD / Carteira':<50} {_pct(carteira_result.indice_cobertura_pct)}")


def _print_stress(cenario: ResultadoStress, titulo: str) -> None:
    print(f"\n{SEP}")
    print(f"  STRESS TEST: {titulo}")
    print(f"  {cenario.descricao}")
    print(SEP)
    print(f"  {'Saldo Afetado':<45} {_brl(cenario.saldo_afetado_brl)}")
    print(f"  {'Operações Migradas de Nível':<45} {cenario.ops_migradas:>20}")
    if cenario.ops_sem_cobertura:
        print(f"  {'Ops sem Cobertura de Garantia Suficiente':<45} {cenario.ops_sem_cobertura:>20} ⚠️")
    print(f"  {'Inadimplência ANTES':<45} {_pct(cenario.inadimplencia_antes_pct):>20}")
    print(f"  {'Inadimplência DEPOIS':<45} {_pct(cenario.inadimplencia_depois_pct):>20}")
    print(f"  {'Delta Inadimplência':<45} {'▲ ' + str(cenario.delta_inadimplencia_pp) + 'pp':>20}")
    print(f"  {'PCLD Adicional Necessária':<45} {_brl(cenario.pcld_adicional_brl)}")

    if cenario.detalhe_migracoes:
        print(f"\n  Top migrações ({min(5, len(cenario.detalhe_migracoes))} primeiras):")
        for m in cenario.detalhe_migracoes[:5]:
            linha = f"    [{m['op_id']}]  {m['de']} → {m['para']}"
            if "novo_pmt" in m:
                linha += f"  | Novo PMT: R$ {m['novo_pmt']:,.2f}  | Comprometimento: {m.get('comprometimento_pct', 0):.1f}%"
            elif "ltv_depois" in m:
                linha += f"  | LTV novo: {m['ltv_depois']:.3f}"
            print(linha)


def _print_conselho(rel: RelatorioExecutivo) -> None:
    print(f"\n{SEP2}")
    print(f"  {'SUMÁRIO EXECUTIVO PARA O CONSELHO DE ADMINISTRAÇÃO':^76}")
    print(f"  {'Data-base: ' + rel.data_posicao:^76}")
    print(SEP2)

    pcld_impacto = (
        rel.pcld_necessaria_brl
        + rel.stress_selic.pcld_adicional_brl
        + rel.stress_agro.pcld_adicional_brl
        + rel.stress_garantia.pcld_adicional_brl
    )

    print(f"""
  1. POSIÇÃO DA CARTEIRA
     A cooperativa encerra a posição de {rel.data_posicao} com saldo devedor de
     {_brl(rel.saldo_carteira_brl).strip()} em {rel.total_operacoes} operações ativas de
     {rel.total_associados} associados. O score médio cooperativo da carteira é
     {rel.score_medio_cooperativo:.0f}/1000, com {rel.pct_carteira_aa_b:.1f}% do saldo em
     operações de boa qualidade (AA/A/B).

  2. QUALIDADE E INADIMPLÊNCIA
     O NPL (Nível D–H) está em {_pct(rel.inadimplencia_d_h_pct).strip()}, com
     {_pct(rel.inadimplencia_90d_pct).strip()} acima de 90 dias (critério BIS).
     {"[ALERTA] Inadimplência acima de 5% — adotar medidas preventivas." if rel.inadimplencia_d_h_pct > 5 else "[OK] Inadimplência dentro do parâmetro histórico SNCC (<5%)."}

  3. PROVISÃO REQUERIDA (PCLD)
     A provisão mínima calculada para a carteira atual é de
     {_brl(rel.pcld_necessaria_brl).strip()}, representando {_pct(rel.pcld_sobre_carteira_pct).strip()}
     do saldo total. Valor deve ser registrado como despesa antes do
     fechamento do balanço trimestral (Res. CMN 2.682/99).

  4. CENÁRIOS DE ESTRESSE
     Em caso de estresse simultâneo (Selic +{2:.0f}pp, Agro +{10:.0f}%, Garantias -{15:.0f}%),
     a provisão adicional necessária seria de:
     {_brl(rel.stress_selic.pcld_adicional_brl).strip()} (Selic)
     + {_brl(rel.stress_agro.pcld_adicional_brl).strip()} (Agro)
     + {_brl(rel.stress_garantia.pcld_adicional_brl).strip()} (Garantias)
     ─────────────────────────────────────────
     = {_brl(pcld_impacto).strip()} PCLD total no cenário adverso

  5. CONCENTRAÇÕES A MONITORAR
     Top-10 devedores representam {rel.concentracao_top10_pct:.1f}% da carteira.
     {'[ALERTA] Limite prudencial de 25% ultrapassado — diversificar.' if rel.concentracao_top10_pct > 25 else '[OK] Concentração dentro do limite prudencial.'}
     Exposição ao Agronegócio: {rel.concentracao_agro_pct:.1f}%
     {'[ATENÇÃO] Alta concentração setorial — monitorar safra e clima.' if rel.concentracao_agro_pct > 40 else ''}

  6. CONFORMIDADE DRO 5050 S3
     Todos os cálculos de PCLD, classificação de risco e fatores de scoring
     estão documentados e auditáveis. Sistema apto para remessa ao BCB.
""")
    print(SEP2)


# ─── Runner Principal ─────────────────────────────────────────────────────────

def run_portfolio_demo(export_csv: bool = True) -> None:
    print("Gerando carteira mock...")
    carteira = gerar_carteira_mock()

    print(f"Carteira gerada: {carteira.total_operacoes} operações | {len(carteira.associados)} associados")
    print("Executando engine de risco (scoring + PCLD + stress tests)...")

    engine = RiskEngine()

    # Enriquecer carteira (scores + níveis) e calcular PCLD manualmente
    # para passar ao print_pcld — generate_executive_report faz tudo internamente
    engine._enrich_carteira(carteira)
    pcld_result = engine.calculate_pcld(carteira)

    # Relatório executivo completo
    rel = engine.generate_executive_report(carteira)

    # ── Impressão ─────────────────────────────────────────────────────────────
    _print_cabecalho(rel)
    _print_visao_geral(rel)
    _print_pcld(rel, pcld_result)
    _print_stress(rel.stress_selic,    "CENÁRIO 1 — SELIC +2pp")
    _print_stress(rel.stress_agro,     "CENÁRIO 2 — INADIMPLÊNCIA AGRO +10%")
    _print_stress(rel.stress_garantia, "CENÁRIO 3 — DESVALORIZAÇÃO DE GARANTIAS -15%")
    _print_conselho(rel)

    # ── DataFrame ─────────────────────────────────────────────────────────────
    df = engine.to_dataframe(carteira)
    print(f"\nEstatísticas descritivas da carteira (pandas):\n")
    print(df[["saldo_devedor", "taxa_am_pct", "dpd_atual", "score_coop", "pcld_brl"]].describe().to_string())

    if export_csv:
        csv_path = "carteira_2026.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"\nDataFrame exportado: {csv_path} ({len(df)} linhas)")


if __name__ == "__main__":
    run_portfolio_demo(export_csv=True)
