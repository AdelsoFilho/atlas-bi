"""
demo.py — Atlas BI Risk Engine
Executa análise completa dos 5 associados mock e imprime relatórios de conformidade.

Mock data calibrado para o cenário Brasil 2026:
  - Selic 15%, inadimplência agro elevada, carteira PJ crescendo 22%
  - 5 perfis: 1 agro grande, 2 PME, 2 assalariados (1 saudável, 1 estressado)

Execução:
    python -m risk_engine.demo
"""

from __future__ import annotations

import json
import sys
import io
from datetime import date

# Force UTF-8 output on Windows (cp1252 cannot render box/emoji chars)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .models import (
    AssociadoProfile,
    RelacionamentoCooperativa,
    ComportamentoPagamento,
    PerfilFinanceiro,
    ContextoAgro,
    SetorEconomico,
    CicloCultura,
)
from .engine import CreditRiskEngine
from .compliance import DROComplianceLogger


# ─── Mock Data: 5 Associados ──────────────────────────────────────────────────

ASSOCIADOS: list[AssociadoProfile] = [

    # ── 1. Produtor rural de soja — grande, mas em entressafra e sem seguro ──
    AssociadoProfile(
        id="ASS-001",
        nome="João Augusto Fonseca",
        cpf_cnpj="012.345.678-90",
        tipo="PF",
        setor=SetorEconomico.AGRO_SOJA,
        data_nascimento_fundacao=date(1972, 3, 15),
        valor_solicitado_brl=450_000.0,
        finalidade="Custeio safra soja 2026/27 — insumos e combustível",
        prazo_meses=18,
        analista_id="ANA-007",
        relacionamento=RelacionamentoCooperativa(
            anos_associado=12.5,
            capital_integralizado_brl=22_000.0,
            participacao_assembleias_pct=75.0,
            numero_produtos_ativos=4,
            possui_conta_salario=True,
            historico_inadimplencia_coop=1,
        ),
        comportamento=ComportamentoPagamento(
            score_bureau=680,
            restricoes_ativas=0,
            atrasos_30d_ultimos_3m=1,
            atrasos_60d_ultimos_3m=0,
            atrasos_90d_ultimos_3m=0,
            tendencia_pagamento=-0.8,       # Leve deterioração recente
            comprometimento_renda_pct=38.0,
            dividas_total_brl=180_000.0,
        ),
        financeiro=PerfilFinanceiro(
            renda_bruta_mensal_brl=28_000.0,
            patrimonio_liquido_brl=1_200_000.0,  # Terra + maquinário
            receita_agro_anual_brl=890_000.0,
            area_cultivada_hectares=320.0,
        ),
        contexto_agro=ContextoAgro(
            ciclo_atual=CicloCultura.ENTRESSAFRA,
            cultura_principal="soja",
            possui_seguro_safra=False,           # Hard Rule HR-05 ativada
            exposicao_clima_score=7.2,            # Região de risco El Niño (MT)
            preco_commodity_tendencia=-8.5,       # Soja em queda nos futuros
            custeio_financiado_pct=72.0,          # Alta dependência de crédito
        ),
    ),

    # ── 2. Comerciante PME — perfil saudável, boa fidelidade ─────────────────
    AssociadoProfile(
        id="ASS-002",
        nome="Mercado Bom Preço Ltda",
        cpf_cnpj="12.345.678/0001-90",
        tipo="PJ",
        setor=SetorEconomico.COMERCIO_VAREJO,
        data_nascimento_fundacao=date(2011, 7, 22),
        valor_solicitado_brl=80_000.0,
        finalidade="Capital de giro para estoque natalino",
        prazo_meses=12,
        analista_id="ANA-003",
        relacionamento=RelacionamentoCooperativa(
            anos_associado=8.0,
            capital_integralizado_brl=6_500.0,
            participacao_assembleias_pct=60.0,
            numero_produtos_ativos=5,
            possui_conta_salario=True,
            historico_inadimplencia_coop=0,
        ),
        comportamento=ComportamentoPagamento(
            score_bureau=760,
            restricoes_ativas=0,
            atrasos_30d_ultimos_3m=0,
            atrasos_60d_ultimos_3m=0,
            atrasos_90d_ultimos_3m=0,
            tendencia_pagamento=1.2,             # Melhora consistente
            comprometimento_renda_pct=22.0,
            dividas_total_brl=35_000.0,
        ),
        financeiro=PerfilFinanceiro(
            renda_bruta_mensal_brl=18_000.0,
            patrimonio_liquido_brl=320_000.0,
            faturamento_mensal_pj_brl=95_000.0,
            margem_liquida_pj_pct=8.5,
        ),
    ),

    # ── 3. PME — pequeno prestador de serviços, alto endividamento ───────────
    AssociadoProfile(
        id="ASS-003",
        nome="Tech Manutenção ME",
        cpf_cnpj="98.765.432/0001-10",
        tipo="PJ",
        setor=SetorEconomico.SERVICOS_PME,
        data_nascimento_fundacao=date(2019, 2, 10),
        valor_solicitado_brl=35_000.0,
        finalidade="Equipamentos de informática",
        prazo_meses=24,
        analista_id="ANA-003",
        relacionamento=RelacionamentoCooperativa(
            anos_associado=2.0,
            capital_integralizado_brl=800.0,
            participacao_assembleias_pct=25.0,
            numero_produtos_ativos=2,
            possui_conta_salario=False,
            historico_inadimplencia_coop=2,
        ),
        comportamento=ComportamentoPagamento(
            score_bureau=420,
            restricoes_ativas=1,                 # HR-01 ativada (análise manual)
            atrasos_30d_ultimos_3m=2,
            atrasos_60d_ultimos_3m=1,
            atrasos_90d_ultimos_3m=0,
            tendencia_pagamento=-1.5,
            comprometimento_renda_pct=48.0,      # HR-02 ativada
            dividas_total_brl=62_000.0,
        ),
        financeiro=PerfilFinanceiro(
            renda_bruta_mensal_brl=9_500.0,
            patrimonio_liquido_brl=15_000.0,
            faturamento_mensal_pj_brl=22_000.0,
            margem_liquida_pj_pct=4.2,
        ),
    ),

    # ── 4. Assalariado CLT — perfil exemplar, servidor público ───────────────
    AssociadoProfile(
        id="ASS-004",
        nome="Maria Aparecida Rocha",
        cpf_cnpj="456.789.012-34",
        tipo="PF",
        setor=SetorEconomico.FUNCIONALISMO,
        data_nascimento_fundacao=date(1985, 11, 30),
        valor_solicitado_brl=25_000.0,
        finalidade="Reforma residencial",
        prazo_meses=36,
        analista_id="ANA-011",
        relacionamento=RelacionamentoCooperativa(
            anos_associado=15.0,
            capital_integralizado_brl=3_200.0,
            participacao_assembleias_pct=90.0,
            numero_produtos_ativos=6,
            possui_conta_salario=True,
            historico_inadimplencia_coop=0,
        ),
        comportamento=ComportamentoPagamento(
            score_bureau=855,
            restricoes_ativas=0,
            atrasos_30d_ultimos_3m=0,
            atrasos_60d_ultimos_3m=0,
            atrasos_90d_ultimos_3m=0,
            tendencia_pagamento=2.0,
            comprometimento_renda_pct=18.0,
            dividas_total_brl=12_000.0,
        ),
        financeiro=PerfilFinanceiro(
            renda_bruta_mensal_brl=7_800.0,
            patrimonio_liquido_brl=280_000.0,
        ),
    ),

    # ── 5. Assalariado CLT — em espiral de endividamento pós-Selic 15% ───────
    AssociadoProfile(
        id="ASS-005",
        nome="Ricardo Mendes Souza",
        cpf_cnpj="789.012.345-67",
        tipo="PF",
        setor=SetorEconomico.ASSALARIADO_CLT,
        data_nascimento_fundacao=date(1991, 6, 4),
        valor_solicitado_brl=18_000.0,
        finalidade="Consolidação de dívidas (cartão + financiamento)",
        prazo_meses=48,
        analista_id=None,                        # FLAG-OP-03: analista não identificado
        relacionamento=RelacionamentoCooperativa(
            anos_associado=1.5,
            capital_integralizado_brl=300.0,
            participacao_assembleias_pct=10.0,
            numero_produtos_ativos=1,
            possui_conta_salario=False,
            historico_inadimplencia_coop=3,
        ),
        comportamento=ComportamentoPagamento(
            score_bureau=310,
            restricoes_ativas=2,                 # HR-01 BLOQUEIO
            atrasos_30d_ultimos_3m=3,
            atrasos_60d_ultimos_3m=2,
            atrasos_90d_ultimos_3m=1,            # HR-03 BLOQUEIO
            tendencia_pagamento=-3.2,
            comprometimento_renda_pct=67.0,      # HR-02 ativada
            dividas_total_brl=48_000.0,
        ),
        financeiro=PerfilFinanceiro(
            renda_bruta_mensal_brl=4_200.0,
            patrimonio_liquido_brl=0.0,          # FLAG-OP-02
        ),
    ),
]


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_demo(save_logs: bool = True) -> None:
    engine = CreditRiskEngine()
    logger = DROComplianceLogger(log_dir="./compliance_logs") if save_logs else None

    LINHA = "─" * 72

    print(f"\n{'═' * 72}")
    print("  ATLAS BI — Engine de Scoring de Crédito Cooperativo")
    print(f"  Cenario: Selic 15% a.a. | Brasil 2026 | DRO 5050 S3")
    print(f"  Modelo v{CreditRiskEngine.VERSION} | DRO 5050 S3 | {len(ASSOCIADOS)} associados")
    print(f"{'═' * 72}\n")

    for associado in ASSOCIADOS:
        print(LINHA)
        print(f"  Associado: {associado.nome} [{associado.id}] | {associado.tipo} | {associado.setor.value}")
        print(f"  Solicitação: R$ {associado.valor_solicitado_brl:>12,.2f} | {associado.prazo_meses}m | {associado.finalidade[:50]}")
        print(LINHA)

        try:
            analise = engine.calculate_score(associado)
            decisao = engine.suggest_limit(analise, associado)
            report  = engine.generate_risk_report(analise, associado)

            # Resumo visual
            decisao_emoji = {
                "APROVADO":         "✅",
                "APROVADO_PARCIAL": "⚠️ ",
                "ANALISE_MANUAL":   "🔍",
                "NEGADO":           "❌",
                "BLOQUEADO":        "🔒",
            }.get(analise.decisao.value, "❓")

            print(f"  {decisao_emoji} DECISÃO:          {analise.decisao.value}")
            print(f"  📊 Score Cooperativo: {analise.score_cooperativo:>6.0f} / 1000")
            print(f"  📈 Score Bureau:      {analise.score_mercado:>6.0f} / 1000")
            print(f"  📉 PD Atual:          {analise.probabilidade_default:>6.2f}%")
            print(f"  📉 PD Stress +2pp:    {analise.pd_stress_selic_mais_2pct:>6.2f}%")
            print(f"  🏦 Nível BCB:         {analise.nivel_risco_bcb} (provisão {analise.provisao_requerida_pct:.0f}%)")
            print(f"  💰 Limite Aprovado:   R$ {analise.limite_aprovado_brl:>12,.2f}")
            print(f"  💲 Taxa Sugerida:     {analise.taxa_sugerida_pct:.2f}% a.m.")
            print(f"  📅 Prazo Máximo:      {analise.prazo_maximo_meses} meses")

            if analise.hard_rules_violadas:
                print(f"\n  ⚡ Hard Rules ({len(analise.hard_rules_violadas)}):")
                for hr in analise.hard_rules_violadas:
                    icon = "🔴" if hr.severidade == "BLOQUEIO" else "🟡"
                    print(f"     {icon} [{hr.regra}] {hr.descricao[:65]}")

            print(f"\n  🔍 Top Fatores de Risco:")
            for i, f in enumerate(analise.fatores_risco[:4], 1):
                direcao = "↑risco" if f.impacto_pd > 0 else "↓risco"
                print(f"     {i}. {f.descricao[:55]:<55} {direcao} ({abs(f.impacto_pd):.3f}pp PD)")

            if analise.flags_operacionais:
                print(f"\n  ⚠️  Flags Operacionais DRO 5050:")
                for flag in analise.flags_operacionais:
                    print(f"     • {flag}")

            apto = report["conformidade_dro5050"]["apto_remessa_bacen"]
            print(f"\n  {'✅' if apto else '❌'} Apto remessa BACEN: {'SIM' if apto else 'NÃO'}")

            if logger:
                log_path = logger.log(report)
                print(f"  📁 Log salvo: {log_path}")

        except ValueError as e:
            print(f"  ❌ Erro de validação: {e}")

        print()

    # Sumário de conformidade do dia
    if logger:
        print(f"{'═' * 72}")
        print("  SUMÁRIO DE CONFORMIDADE — DRO 5050 S3")
        print(f"{'═' * 72}")
        summary = logger.audit_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_demo(save_logs=True)
