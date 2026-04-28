"""
portfolio_engine.py — Atlas BI Risk Engine
Motor de risco de carteira cooperativo: scoring mutualista, PCLD e stress test.

Modelo white-box: toda regra é auditável linha a linha pelo BCB.
Sem dependências de ML — apenas lógica estatística transparente.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .portfolio_models import (
    Associado,
    Carteira,
    DPD_PARA_NIVEL,
    Garantia,
    NivelRiscoBCB,
    OperacaoCredito,
    PCLD_PERCENTUAIS,
    SELIC_ATUAL_PCT_AM,
    SetorAtividade,
    TipoGarantia,
    TipoTaxa,
    LTV_MAXIMO,
)


# ─── Outputs estruturados ─────────────────────────────────────────────────────

@dataclass
class ResultadoPCLD:
    """Posição de provisão da carteira por nível de risco."""
    por_nivel: dict[str, dict]          # nivel → {saldo, pcld, qtd_ops}
    pcld_total_brl: float
    pcld_especifica_brl: float          # Ops com DPD > 0 individualmente
    pcld_coletiva_brl: float            # Risco latente das ops AA/A
    indice_cobertura_pct: float         # PCLD / Saldo total × 100
    saldo_total_carteira_brl: float


@dataclass
class ResultadoStress:
    """Impacto de um cenário de estresse na carteira."""
    cenario: str
    descricao: str
    saldo_afetado_brl: float
    ops_migradas: int
    pcld_adicional_brl: float           # Aumento de provisão necessária
    inadimplencia_antes_pct: float
    inadimplencia_depois_pct: float
    delta_inadimplencia_pp: float       # Variação em pontos percentuais
    ops_sem_cobertura: int = 0          # Ops onde LTV > limite após choque
    detalhe_migracoes: list[dict] = field(default_factory=list)


@dataclass
class RelatorioExecutivo:
    """Sumário para o Conselho de Administração."""
    data_posicao: str
    saldo_carteira_brl: float
    total_operacoes: int
    total_associados: int

    # Qualidade
    inadimplencia_d_h_pct: float        # NPL: operações D–H / saldo total
    inadimplencia_90d_pct: float        # Critério internacional: DPD > 90
    operacoes_renegociadas_pct: float

    # Provisão
    pcld_necessaria_brl: float
    pcld_sobre_carteira_pct: float
    nivel_cobertura_pct: float

    # Concentração de risco
    concentracao_top10_pct: float       # % do saldo nos 10 maiores devedores
    concentracao_agro_pct: float
    concentracao_varejo_pct: float
    concentracao_imob_pct: float

    # Stress tests
    stress_selic: ResultadoStress
    stress_agro: ResultadoStress
    stress_garantia: ResultadoStress

    # Score da carteira
    score_medio_cooperativo: float
    pct_carteira_aa_b: float            # % carteira em nível AA/A/B (boa qualidade)


# ─── Engine Principal ─────────────────────────────────────────────────────────

class RiskEngine:
    """
    Motor de risco de carteira cooperativo.

    Fluxo de análise:
      1. calculate_mutual_score()   → score 0-1000 ponderando bureau + vínculo
      2. classify_risk_level()      → nível AA-H por DPD + ajuste qualitativo
      3. calculate_ltv()            → Loan-to-Value por operação
      4. calculate_pcld()           → provisão total + por nível
      5. stress_test()              → 3 cenários adversos
      6. generate_executive_report() → consolidado para o Conselho
    """

    # ── Pesos do Score Mutualista ─────────────────────────────────────────────
    # Soma = 1.0; calibrados para capturar o diferencial cooperativo
    # vs. modelo de banco tradicional (que usa 100% do bureau externo)
    W_BUREAU         = 0.35   # Score Serasa/SCR (base de mercado)
    W_RELACIONAMENTO = 0.28   # Tempo de casa + participação + produtos
    W_PATRIMONIAL    = 0.22   # Capital integralizado + cotas + patrimônio
    W_COMPORTAMENTAL = 0.15   # Histórico interno de pagamento na coop

    # Bônus de limite: associado fiel com capital integralizado relevante
    BONUS_LIMITE_PCT   = 0.20   # +20% no limite aprovado
    THRESHOLD_SCORE    = 720.0  # Score mínimo para o bônus
    THRESHOLD_CAPITAL  = 5_000  # Capital integralizado mínimo para o bônus (R$)

    # PCLD coletiva: percentual aplicado sobre AA e A (risco latente)
    PCLD_COLETIVA_AA   = 0.0010  # 0,10% do saldo AA
    PCLD_COLETIVA_A    = 0.0025  # 0,25% do saldo A

    def __init__(self, selic_am_pct: float = SELIC_ATUAL_PCT_AM) -> None:
        self.selic_am_pct = selic_am_pct

    # ─── 1. Scoring Mutualista ────────────────────────────────────────────────

    def calculate_mutual_score(self, associado: Associado) -> float:
        """
        Score Cooperativo 0–1000 — ponderação dos 4 fatores mutualistas.

        Diferencial vs. banco tradicional:
          Um associado de 15 anos com R$ 8k integralizado e 80% de participação
          em assembleias recebe bônus de relacionamento que eleva o score ~60pts
          mesmo com bureau moderado (600), sinalizando risco real menor que o
          bureau externo indica isoladamente.
        """
        # Fator 1: Bureau (normalizado 0–1)
        f_bureau = associado.score_serasa / 1000.0

        # Fator 2: Relacionamento — tempo + participação + vínculo bancário
        # Tempo: satura em 20 anos (1.0); curva raiz para capturar ganho marginal
        f_tempo = min(math.sqrt(associado.anos_associado / 20.0), 1.0)
        f_assembly = associado.participacao_assembleias_pct / 100.0
        f_vinculo = min(associado.numero_produtos_ativos / 6.0, 1.0)
        f_conta_sal = 0.1 if associado.possui_conta_salario else 0.0
        f_relacionamento = (f_tempo * 0.50 + f_assembly * 0.25 + f_vinculo * 0.15 + f_conta_sal * 0.10)

        # Fator 3: Patrimonial — capital integralizado normalizado por renda anual
        # Associado que integraliza capital tem "skin in the game"
        renda_anual = associado.renda_bruta_mensal_brl * 12
        f_capital = min(associado.capital_integralizado_brl / max(renda_anual * 0.30, 1), 1.0)
        # Patrimônio pessoal como colchão
        f_patrimonio = min(associado.patrimonio_liquido_brl / max(renda_anual * 5, 1), 1.0)
        f_patrimonial = f_capital * 0.65 + f_patrimonio * 0.35

        # Fator 4: Comportamental — penaliza histórico negativo externo
        f_comportamental = 0.30 if associado.possui_historico_negativo_externo else 1.0

        # Score composto
        score_raw = (
            self.W_BUREAU         * f_bureau         +
            self.W_RELACIONAMENTO * f_relacionamento  +
            self.W_PATRIMONIAL    * f_patrimonial     +
            self.W_COMPORTAMENTAL * f_comportamental
        )
        return round(score_raw * 1000, 1)

    def check_bonus_limit(self, associado: Associado) -> bool:
        """
        Regra de negócio cooperativa: associado fiel com capital integralizado
        tem direito a limite 20% superior ao padrão de mercado.
        """
        return (
            associado.score_cooperativo >= self.THRESHOLD_SCORE
            and associado.capital_integralizado_brl >= self.THRESHOLD_CAPITAL
        )

    # ─── 2. Classificação de Risco AA–H ──────────────────────────────────────

    def classify_risk_level(
        self,
        operacao: OperacaoCredito,
        associado: Optional[Associado] = None,
    ) -> NivelRiscoBCB:
        """
        Classificação por DPD com downgrade qualitativo.

        Regra base: Res. CMN 2.682/99 — DPD determina o piso do nível.
        Downgrade qualitativo (Art. 3º): operação pode ser rebaixada além
        do DPD quando há sinais de deterioração (renegociações, score baixo).
        """
        dpd = operacao.historico.dpd_atual

        # Nível piso por DPD
        nivel_base = NivelRiscoBCB.H
        for limite_dpd, nivel in DPD_PARA_NIVEL:
            if dpd <= limite_dpd:
                nivel_base = nivel
                break

        # Downgrades qualitativos (Art. 3º da 2.682)
        nivel_ord = list(NivelRiscoBCB)
        idx = nivel_ord.index(nivel_base)

        # Renegociação/refinanciamento → downgrade 1 nível
        if operacao.historico.renegociacoes >= 2 or operacao.historico.refinanciamentos >= 1:
            idx = min(idx + 1, len(nivel_ord) - 1)

        # Score cooperativo muito baixo (<350) em operação relevante → downgrade
        if (
            associado is not None
            and associado.score_cooperativo < 350
            and operacao.saldo_devedor_brl > 20_000
        ):
            idx = min(idx + 1, len(nivel_ord) - 1)

        # DPD máx 12m alto mesmo com DPD atual zerado (sinal de instabilidade)
        if operacao.historico.dpd_maximo_12m > 30 and dpd == 0:
            idx = min(idx + 1, len(nivel_ord) - 1)

        return nivel_ord[idx]

    # ─── 3. Loan-to-Value ────────────────────────────────────────────────────

    def calculate_ltv(self, operacao: OperacaoCredito) -> float:
        """
        LTV = Saldo Devedor / Valor das Garantias.
        Sem garantia: LTV = 999 (indica exposição total sem cobertura).
        """
        total_garantias = operacao.total_garantias_brl
        if total_garantias <= 0:
            return 999.0
        return round(operacao.saldo_devedor_brl / total_garantias, 4)

    # ─── 4. Cálculo de PCLD ──────────────────────────────────────────────────

    def calculate_pcld(self, carteira: Carteira) -> ResultadoPCLD:
        """
        PCLD total = Provisão Específica (ops deterioradas) + Provisão Coletiva.

        Provisão Específica: ops com nível B–H, percentual por saldo devedor.
        Provisão Coletiva: risco latente nas ops AA/A saudáveis da carteira.
        (Res. CMN 2.682/99 não exige coletiva explicitamente, mas é boa prática
        e recomendada pelo BACEN em inspeções de cooperativas de médio porte.)
        """
        por_nivel: dict[str, dict] = {
            n.value: {"saldo_brl": 0.0, "pcld_brl": 0.0, "qtd_ops": 0}
            for n in NivelRiscoBCB
        }

        pcld_especifica = 0.0
        pcld_coletiva   = 0.0

        for op in carteira.operacoes:
            nivel = op.nivel_risco
            pct   = PCLD_PERCENTUAIS[nivel] / 100.0
            pcld  = op.saldo_devedor_brl * pct

            por_nivel[nivel.value]["saldo_brl"] += op.saldo_devedor_brl
            por_nivel[nivel.value]["pcld_brl"]  += pcld
            por_nivel[nivel.value]["qtd_ops"]   += 1

            if nivel == NivelRiscoBCB.AA:
                pcld_coletiva += op.saldo_devedor_brl * self.PCLD_COLETIVA_AA
            elif nivel == NivelRiscoBCB.A:
                pcld_coletiva += op.saldo_devedor_brl * self.PCLD_COLETIVA_A
            else:
                pcld_especifica += pcld

        # Enriquece dict com percentuais
        for nivel_str, dados in por_nivel.items():
            pct_nivel = PCLD_PERCENTUAIS[NivelRiscoBCB(nivel_str)]
            dados["pcld_percentual"] = pct_nivel
            dados["saldo_brl"]       = round(dados["saldo_brl"], 2)
            dados["pcld_brl"]        = round(dados["pcld_brl"], 2)

        pcld_total = pcld_especifica + pcld_coletiva
        saldo_total = carteira.saldo_total_brl

        return ResultadoPCLD(
            por_nivel=por_nivel,
            pcld_total_brl=round(pcld_total, 2),
            pcld_especifica_brl=round(pcld_especifica, 2),
            pcld_coletiva_brl=round(pcld_coletiva, 2),
            indice_cobertura_pct=round(pcld_total / max(saldo_total, 1) * 100, 2),
            saldo_total_carteira_brl=round(saldo_total, 2),
        )

    # ─── 5. Stress Tests ─────────────────────────────────────────────────────

    def stress_test(
        self,
        carteira: Carteira,
        pcld_atual: ResultadoPCLD,
        delta_selic_pp: float = 2.0,
        delta_desemprego_agro_pct: float = 10.0,
        delta_garantia_pct: float = -15.0,
    ) -> tuple[ResultadoStress, ResultadoStress, ResultadoStress]:
        """
        Três cenários de estresse regulatórios (Res. CMN 4.557/2017).
        Retorna (stress_selic, stress_agro, stress_garantia).
        """
        return (
            self._stress_selic(carteira, pcld_atual, delta_selic_pp),
            self._stress_agro(carteira, pcld_atual, delta_desemprego_agro_pct),
            self._stress_garantia(carteira, pcld_atual, delta_garantia_pct),
        )

    def _stress_selic(
        self, carteira: Carteira, pcld_atual: ResultadoPCLD, delta_pp: float
    ) -> ResultadoStress:
        """
        Cenário Selic + Δpp.

        Mecanismo:
          1. Recalcula PMT para operações de taxa variável com nova taxa.
          2. Verifica se novo PMT > 35% da renda → inadimplência projetada.
          3. Reclassifica essas ops para nível D (gatilho de incapacidade).
          4. Calcula PCLD adicional necessária.

        Base: Res. BCB 4.676/2018 — stress de capacidade de pagamento.
        """
        nova_selic_am = self.selic_am_pct + (delta_pp / 12)
        ops_migradas: list[dict] = []
        pcld_adicional = 0.0
        saldo_afetado = 0.0

        for op in carteira.operacoes:
            if op.tipo_taxa != TipoTaxa.VARIAVEL:
                continue
            if op.nivel_risco in (NivelRiscoBCB.E, NivelRiscoBCB.F, NivelRiscoBCB.G, NivelRiscoBCB.H):
                continue  # Já inadimplente — não piora por taxa

            assoc = carteira.associados.get(op.associado_id)
            if assoc is None:
                continue

            # Nova taxa = taxa atual + proporção da alta Selic ao spread
            # Conservador: 70% do aumento de Selic repassa para taxa variável
            nova_taxa_am = op.taxa_juros_mensal_pct + (delta_pp * 0.70) / 12

            # Novo PMT com mesma amortização restante
            n = max(op.prazo_restante_meses, 1)
            r = nova_taxa_am / 100
            novo_pmt = op.saldo_devedor_brl * r / (1 - (1 + r) ** -n)

            renda = assoc.renda_bruta_mensal_brl
            comprometimento_novo = novo_pmt / max(renda, 1) * 100

            # Migração: comprometimento pós-Selic > 40% (limite BCB 4.676)
            # OU aumento do PMT > 15% (choque relevante de prestação)
            aumento_pmt_pct = (novo_pmt - op.prestacao_mensal_brl) / op.prestacao_mensal_brl * 100
            if comprometimento_novo > 40 or aumento_pmt_pct > 15:
                nivel_anterior = op.nivel_risco
                nivel_ord = list(NivelRiscoBCB)
                idx_atual = nivel_ord.index(nivel_anterior)
                # Migra no mínimo para C; se já em C, vai para D
                idx_novo = max(idx_atual + 2, nivel_ord.index(NivelRiscoBCB.C))
                idx_novo = min(idx_novo, nivel_ord.index(NivelRiscoBCB.D))
                nivel_novo = nivel_ord[idx_novo]

                pcld_antes = op.saldo_devedor_brl * PCLD_PERCENTUAIS[nivel_anterior] / 100
                pcld_depois = op.saldo_devedor_brl * PCLD_PERCENTUAIS[nivel_novo] / 100
                pcld_adicional += pcld_depois - pcld_antes
                saldo_afetado += op.saldo_devedor_brl

                ops_migradas.append({
                    "op_id": op.id,
                    "de": nivel_anterior.value,
                    "para": nivel_novo.value,
                    "novo_pmt": round(novo_pmt, 2),
                    "aumento_pmt_pct": round(aumento_pmt_pct, 2),
                    "comprometimento_pct": round(comprometimento_novo, 2),
                })

        inadi_antes = self._calcular_inadimplencia(carteira)
        inadi_depois = self._calcular_inadimplencia_stress(carteira, ops_migradas)

        return ResultadoStress(
            cenario="SELIC_ALTA",
            descricao=f"Selic +{delta_pp}pp ({self.selic_am_pct * 12:.2f}% → {(self.selic_am_pct + delta_pp / 12) * 12:.2f}% a.a.)",
            saldo_afetado_brl=round(saldo_afetado, 2),
            ops_migradas=len(ops_migradas),
            pcld_adicional_brl=round(pcld_adicional, 2),
            inadimplencia_antes_pct=inadi_antes,
            inadimplencia_depois_pct=inadi_depois,
            delta_inadimplencia_pp=round(inadi_depois - inadi_antes, 2),
            detalhe_migracoes=ops_migradas[:10],  # Top 10 para relatório
        )

    def _stress_agro(
        self, carteira: Carteira, pcld_atual: ResultadoPCLD, delta_desemprego_pct: float
    ) -> ResultadoStress:
        """
        Cenário Desemprego/Sinistro Agro + Δ%.

        Mecanismo: percentual das operações agro migram 2 níveis de risco,
        simulando queda de safra, frustração de colheita ou queda de preço.
        Probabilidade de migração = delta_desemprego_pct / 100 (calibrado).
        """
        ops_migradas = []
        pcld_adicional = 0.0
        saldo_afetado = 0.0
        rng = np.random.default_rng(seed=42)  # Seed fixo para reprodutibilidade

        setores_agro = {SetorAtividade.AGRONEGOCIO, SetorAtividade.RURAL_FAMILIAR}
        ops_agro = [op for op in carteira.operacoes if op.setor_risco in setores_agro]

        for op in ops_agro:
            if op.nivel_risco in (NivelRiscoBCB.G, NivelRiscoBCB.H):
                continue

            # Probabilidade de migração = delta/100, maior para ops já fragilizadas
            prob_base = delta_desemprego_pct / 100
            prob_ajust = prob_base * (1.5 if op.nivel_risco.value in ("C", "D", "E") else 1.0)

            if rng.random() < prob_ajust:
                nivel_ord = list(NivelRiscoBCB)
                idx_atual = nivel_ord.index(op.nivel_risco)
                idx_novo  = min(idx_atual + 2, len(nivel_ord) - 1)
                nivel_novo = nivel_ord[idx_novo]

                pcld_antes  = op.saldo_devedor_brl * PCLD_PERCENTUAIS[op.nivel_risco] / 100
                pcld_depois = op.saldo_devedor_brl * PCLD_PERCENTUAIS[nivel_novo] / 100
                pcld_adicional += pcld_depois - pcld_antes
                saldo_afetado += op.saldo_devedor_brl

                ops_migradas.append({
                    "op_id": op.id,
                    "de": op.nivel_risco.value,
                    "para": nivel_novo.value,
                    "saldo": op.saldo_devedor_brl,
                })

        inadi_antes  = self._calcular_inadimplencia(carteira)
        inadi_depois = self._calcular_inadimplencia_stress(carteira, ops_migradas)

        return ResultadoStress(
            cenario="INADIMPLENCIA_AGRO",
            descricao=f"Frustração de safra / Sinistro agro +{delta_desemprego_pct:.0f}%",
            saldo_afetado_brl=round(saldo_afetado, 2),
            ops_migradas=len(ops_migradas),
            pcld_adicional_brl=round(pcld_adicional, 2),
            inadimplencia_antes_pct=inadi_antes,
            inadimplencia_depois_pct=inadi_depois,
            delta_inadimplencia_pp=round(inadi_depois - inadi_antes, 2),
            detalhe_migracoes=ops_migradas[:10],
        )

    def _stress_garantia(
        self, carteira: Carteira, pcld_atual: ResultadoPCLD, delta_pct: float
    ) -> ResultadoStress:
        """
        Cenário Queda de Garantias (delta_pct negativo = desvalorização).

        Mecanismo:
          1. Reduz valor de todas as garantias em |delta_pct|%.
          2. Recalcula LTV.
          3. Ops com novo LTV > limite prudencial ficam "sem cobertura suficiente".
          4. Ops descobertas em nível B+ migram para C (exige provisão adicional).

        Aplicação prática: queda de 15% no valor de terras agrícolas (EMBRAPA)
        ou depreciação de imóveis (crise de crédito imobiliário).
        """
        fator_queda = 1 + (delta_pct / 100)  # ex: -15% → 0.85
        ops_migradas = []
        pcld_adicional = 0.0
        saldo_afetado = 0.0
        ops_sem_cobertura = 0

        for op in carteira.operacoes:
            if not op.garantias:
                continue

            # Aplica choque de preço nas garantias
            novo_valor_garantias = op.total_garantias_brl * fator_queda
            novo_ltv = op.saldo_devedor_brl / max(novo_valor_garantias, 1)

            # Tipo de garantia predominante (maior valor)
            garantia_principal = max(op.garantias, key=lambda g: g.valor_avaliado_brl)
            ltv_max = LTV_MAXIMO.get(garantia_principal.tipo, 0.80)

            if novo_ltv > ltv_max:
                ops_sem_cobertura += 1
                saldo_afetado += op.saldo_devedor_brl

                # Se op estava em AA/A/B → migra para C (exige atenção)
                if op.nivel_risco in (NivelRiscoBCB.AA, NivelRiscoBCB.A, NivelRiscoBCB.B):
                    nivel_novo = NivelRiscoBCB.C
                    pcld_antes  = op.saldo_devedor_brl * PCLD_PERCENTUAIS[op.nivel_risco] / 100
                    pcld_depois = op.saldo_devedor_brl * PCLD_PERCENTUAIS[nivel_novo] / 100
                    pcld_adicional += pcld_depois - pcld_antes

                    ops_migradas.append({
                        "op_id": op.id,
                        "de": op.nivel_risco.value,
                        "para": nivel_novo.value,
                        "ltv_antes": round(op.ltv, 3),
                        "ltv_depois": round(novo_ltv, 3),
                        "queda_garantia_brl": round(
                            op.total_garantias_brl - novo_valor_garantias, 2
                        ),
                    })

        inadi_antes  = self._calcular_inadimplencia(carteira)
        inadi_depois = self._calcular_inadimplencia_stress(carteira, ops_migradas)

        return ResultadoStress(
            cenario="QUEDA_GARANTIAS",
            descricao=f"Desvalorização de garantias ({delta_pct:.0f}%): imóveis/terra/safra",
            saldo_afetado_brl=round(saldo_afetado, 2),
            ops_migradas=len(ops_migradas),
            pcld_adicional_brl=round(pcld_adicional, 2),
            inadimplencia_antes_pct=inadi_antes,
            inadimplencia_depois_pct=inadi_depois,
            delta_inadimplencia_pp=round(inadi_depois - inadi_antes, 2),
            ops_sem_cobertura=ops_sem_cobertura,
            detalhe_migracoes=ops_migradas[:10],
        )

    # ─── 6. Relatório Executivo ───────────────────────────────────────────────

    def generate_executive_report(self, carteira: Carteira) -> RelatorioExecutivo:
        """
        Pipeline completo: enriquece carteira → calcula PCLD → stress tests → relatório.
        Ponto único de entrada para o CRO / Conselho de Administração.
        """
        # Passo 1: Calcular scores e classificar toda a carteira
        self._enrich_carteira(carteira)

        # Passo 2: PCLD
        pcld = self.calculate_pcld(carteira)

        # Passo 3: Stress tests
        stress_selic, stress_agro, stress_garantia = self.stress_test(carteira, pcld)

        # Passo 4: Métricas de qualidade
        saldo_total = carteira.saldo_total_brl
        inadi_d_h   = self._calcular_inadimplencia(carteira)
        inadi_90d   = self._calcular_inadimplencia_90d(carteira)

        ops_reneg = sum(
            1 for op in carteira.operacoes if op.historico.renegociacoes > 0
        )

        # Concentração setorial
        saldos_por_setor: dict[str, float] = {}
        for op in carteira.operacoes:
            setor = op.setor_risco.value
            saldos_por_setor[setor] = saldos_por_setor.get(setor, 0.0) + op.saldo_devedor_brl

        agro_pct  = sum(
            v for k, v in saldos_por_setor.items()
            if k in ("AGRONEGOCIO", "RURAL_FAMILIAR")
        ) / max(saldo_total, 1) * 100
        varejo_pct = saldos_por_setor.get("COMERCIO", 0.0) / max(saldo_total, 1) * 100
        imob_pct   = saldos_por_setor.get("INDUSTRIA", 0.0) / max(saldo_total, 1) * 100

        # Concentração top-10 devedores
        saldos_por_assoc = {}
        for op in carteira.operacoes:
            saldos_por_assoc[op.associado_id] = (
                saldos_por_assoc.get(op.associado_id, 0.0) + op.saldo_devedor_brl
            )
        top10 = sum(sorted(saldos_por_assoc.values(), reverse=True)[:10])
        conc_top10 = top10 / max(saldo_total, 1) * 100

        # Score médio da carteira
        scores = [
            carteira.associados[op.associado_id].score_cooperativo
            for op in carteira.operacoes
            if op.associado_id in carteira.associados
        ]
        score_medio = sum(scores) / len(scores) if scores else 0.0

        # % carteira em nível bom (AA, A, B)
        saldo_aa_b = sum(
            op.saldo_devedor_brl for op in carteira.operacoes
            if op.nivel_risco in (NivelRiscoBCB.AA, NivelRiscoBCB.A, NivelRiscoBCB.B)
        )
        pct_aa_b = saldo_aa_b / max(saldo_total, 1) * 100

        return RelatorioExecutivo(
            data_posicao=carteira.data_posicao.strftime("%d/%m/%Y"),
            saldo_carteira_brl=round(saldo_total, 2),
            total_operacoes=carteira.total_operacoes,
            total_associados=len(carteira.associados),
            inadimplencia_d_h_pct=inadi_d_h,
            inadimplencia_90d_pct=inadi_90d,
            operacoes_renegociadas_pct=round(ops_reneg / max(carteira.total_operacoes, 1) * 100, 1),
            pcld_necessaria_brl=pcld.pcld_total_brl,
            pcld_sobre_carteira_pct=pcld.indice_cobertura_pct,
            nivel_cobertura_pct=pcld.indice_cobertura_pct,
            concentracao_top10_pct=round(conc_top10, 1),
            concentracao_agro_pct=round(agro_pct, 1),
            concentracao_varejo_pct=round(varejo_pct, 1),
            concentracao_imob_pct=round(imob_pct, 1),
            stress_selic=stress_selic,
            stress_agro=stress_agro,
            stress_garantia=stress_garantia,
            score_medio_cooperativo=round(score_medio, 1),
            pct_carteira_aa_b=round(pct_aa_b, 1),
        )

    # ─── Helpers Internos ────────────────────────────────────────────────────

    def _enrich_carteira(self, carteira: Carteira) -> None:
        """Calcula scores, níveis e LTV para toda a carteira (in-place)."""
        for assoc in carteira.associados.values():
            assoc.score_cooperativo = self.calculate_mutual_score(assoc)

        for op in carteira.operacoes:
            assoc = carteira.associados.get(op.associado_id)
            op.nivel_risco = self.classify_risk_level(op, assoc)
            op.ltv = self.calculate_ltv(op)
            pct = PCLD_PERCENTUAIS[op.nivel_risco] / 100.0
            op.pcld_individual_brl = round(op.saldo_devedor_brl * pct, 2)

    def _calcular_inadimplencia(self, carteira: Carteira) -> float:
        """NPL D–H: saldo das ops D até H / saldo total."""
        niveis_inadimplentes = {NivelRiscoBCB.D, NivelRiscoBCB.E, NivelRiscoBCB.F,
                                NivelRiscoBCB.G, NivelRiscoBCB.H}
        saldo_inadi = sum(
            op.saldo_devedor_brl for op in carteira.operacoes
            if op.nivel_risco in niveis_inadimplentes
        )
        return round(saldo_inadi / max(carteira.saldo_total_brl, 1) * 100, 2)

    def _calcular_inadimplencia_90d(self, carteira: Carteira) -> float:
        """Critério BIS: DPD > 90 dias."""
        saldo_90d = sum(
            op.saldo_devedor_brl for op in carteira.operacoes
            if op.historico.dpd_atual > 90
        )
        return round(saldo_90d / max(carteira.saldo_total_brl, 1) * 100, 2)

    def _calcular_inadimplencia_stress(
        self, carteira: Carteira, migracoes: list[dict]
    ) -> float:
        """
        Projeta inadimplência considerando migrações do stress test.
        Migração para D ou pior conta como inadimplente.
        """
        niveis_inadimplentes = {"D", "E", "F", "G", "H"}
        ops_migradas_inadi = {
            m["op_id"] for m in migracoes if m.get("para", "") in niveis_inadimplentes
        }

        saldo_inadi = 0.0
        for op in carteira.operacoes:
            if op.nivel_risco.value in niveis_inadimplentes:
                saldo_inadi += op.saldo_devedor_brl
            elif op.id in ops_migradas_inadi:
                saldo_inadi += op.saldo_devedor_brl

        return round(saldo_inadi / max(carteira.saldo_total_brl, 1) * 100, 2)

    # ─── Utilitário: Tabela Pandas ────────────────────────────────────────────

    def to_dataframe(self, carteira: Carteira) -> pd.DataFrame:
        """Exporta carteira enriquecida como DataFrame para análises ad-hoc."""
        rows = []
        for op in carteira.operacoes:
            assoc = carteira.associados.get(op.associado_id)
            rows.append({
                "op_id":               op.id,
                "associado_id":        op.associado_id,
                "nome":                assoc.nome if assoc else "-",
                "tipo":                op.tipo.value,
                "setor":               op.setor_risco.value,
                "taxa_tipo":           op.tipo_taxa.value,
                "valor_contratado":    op.valor_contratado_brl,
                "saldo_devedor":       op.saldo_devedor_brl,
                "taxa_am_pct":         op.taxa_juros_mensal_pct,
                "prazo_restante_m":    op.prazo_restante_meses,
                "dpd_atual":           op.historico.dpd_atual,
                "renegociacoes":       op.historico.renegociacoes,
                "nivel_risco":         op.nivel_risco.value,
                "pcld_brl":            op.pcld_individual_brl,
                "ltv":                 op.ltv,
                "score_coop":          assoc.score_cooperativo if assoc else 0,
                "score_serasa":        assoc.score_serasa if assoc else 0,
                "anos_associado":      assoc.anos_associado if assoc else 0,
                "capital_integr_brl":  assoc.capital_integralizado_brl if assoc else 0,
            })
        return pd.DataFrame(rows)
