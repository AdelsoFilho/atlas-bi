"""
CreditRiskEngine — Atlas BI
Engine de scoring híbrida: Hard Rules + Regressão Logística Simulada (White Box)

Arquitetura do modelo:
  1. Hard Rules → bloqueio/restrição imediata (não passa pelo modelo estatístico)
  2. Feature normalization → transforma cada variável para escala 0–1
  3. Weighted logit → Σ(βᵢ × xᵢ) = log-odds de default
  4. PD = sigmoid(logit) → probabilidade de inadimplência
  5. Score Cooperativo = 1000 × (1 − PD) com ajuste de fidelidade
  6. Stress test → recalcula PD sob Selic + 2pp
  7. Limit suggestion → baseado em capacidade de pagamento e nível de risco BCB
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import (
    AssociadoProfile,
    AnaliseCredito,
    DecisaoCredito,
    DecisaoEnum,
    FatorRisco,
    HardRuleViolation,
    SetorEconomico,
    CicloCultura,
)

# ─── Configuração Macro (Brasil 2026) ─────────────────────────────────────────

SELIC_ATUAL_PCT: float = 15.0
SPREAD_COOPERATIVA_PCT: float = 4.5    # Spread médio histórico SNCC sobre Selic
CUSTO_CAPITAL_BASE_PCT: float = SELIC_ATUAL_PCT + SPREAD_COOPERATIVA_PCT

# ─── Coeficientes β — Regressão Logística Calibrada ──────────────────────────
# Sinais:  positivo = aumenta PD (risco)
#          negativo = reduz PD (proteção)
# Escala:  cada coef. opera sobre variável normalizada [0, 1]
# Calibração: baseada em dados históricos SNCC 2019–2024 (simulados para este MVP)

BETAS: dict[str, float] = {
    "intercepto":                  -1.80,  # PD base ~14% sem nenhum fator
    # Bureau / mercado
    "score_bureau_inv":            +2.60,  # Quanto MENOR o score, MAIOR o risco
    "restricoes_ativas":           +1.80,
    "comprometimento_renda":       +1.50,  # Endividamento % renda
    "tendencia_pagamento_inv":     +1.20,  # Deterioração recente
    "atrasos_recentes":            +2.00,  # Atrasos 30/60/90d últimos 3m
    # Relacionamento cooperativa (fatores protetores)
    "anos_associado":              -0.70,
    "capital_integralizado":       -0.60,
    "participacao_assembleias":    -0.35,
    "produtos_ativos":             -0.25,
    "conta_salario":               -0.40,
    # Contexto agro (fator de risco situacional)
    "ciclo_plantio_entressafra":   +0.90,  # Ativado apenas se agro + ciclo ruim
    "sem_seguro_safra":            +0.70,  # Ativado se agro sem seguro
    "exposicao_clima":             +0.50,
    "custeio_financiado_alto":     +0.60,
    # Setor econômico — volatilidade sistêmica
    "volatilidade_setor":          +1.10,
}

# Volatilidade por setor (0 = mínima, 1 = máxima)
VOLATILIDADE_SETOR: dict[SetorEconomico, float] = {
    SetorEconomico.AGRO_SOJA:        0.85,
    SetorEconomico.AGRO_MILHO:       0.65,
    SetorEconomico.AGRO_CAFE:        0.72,
    SetorEconomico.AGRO_PECUARIA:    0.60,
    SetorEconomico.COMERCIO_VAREJO:  0.68,
    SetorEconomico.SERVICOS_PME:     0.55,
    SetorEconomico.ASSALARIADO_CLT:  0.20,
    SetorEconomico.APOSENTADO_INSS:  0.10,
    SetorEconomico.FUNCIONALISMO:    0.12,
    SetorEconomico.PROFISSIONAL_LIB: 0.48,
}

# Mapeamento PD → nível de risco BCB (Resolução CMN 2.682/99)
BCB_RISK_LEVELS: list[tuple[float, str, float]] = [
    # (PD_max%, nível, provisão_%)
    (0.50,  "AA", 0.0),
    (2.00,  "A",  0.5),
    (5.00,  "B",  1.0),
    (10.0,  "C",  3.0),
    (20.0,  "D",  10.0),
    (35.0,  "E",  30.0),
    (55.0,  "F",  50.0),
    (80.0,  "G",  70.0),
    (100.0, "H",  100.0),
]

# Sensibilidade Selic por setor: Δpp de PD por +1pp na Selic
SELIC_SENSITIVITY: dict[SetorEconomico, float] = {
    SetorEconomico.AGRO_SOJA:        0.55,  # Custeio caro + preço commodity pressiona
    SetorEconomico.AGRO_MILHO:       0.45,
    SetorEconomico.AGRO_CAFE:        0.50,
    SetorEconomico.AGRO_PECUARIA:    0.40,
    SetorEconomico.COMERCIO_VAREJO:  0.48,  # Crédito ao consumidor seca
    SetorEconomico.SERVICOS_PME:     0.38,
    SetorEconomico.ASSALARIADO_CLT:  0.22,
    SetorEconomico.APOSENTADO_INSS:  0.10,
    SetorEconomico.FUNCIONALISMO:    0.12,
    SetorEconomico.PROFISSIONAL_LIB: 0.35,
}


class CreditRiskEngine:
    """
    Engine híbrida de scoring cooperativo.

    Uso:
        engine = CreditRiskEngine()
        analise = engine.calculate_score(associado)
        report  = engine.generate_risk_report(analise, associado)
        decisao = engine.suggest_limit(analise, associado)
    """

    VERSION = "1.0.0"

    # ── Hard Rules ────────────────────────────────────────────────────────────

    def _apply_hard_rules(
        self,
        p: AssociadoProfile,
    ) -> list[HardRuleViolation]:
        violations: list[HardRuleViolation] = []

        # HR-01: Restrições ativas no bureau → bloqueio imediato
        if p.comportamento.restricoes_ativas >= 2:
            violations.append(HardRuleViolation(
                regra="HR-01",
                severidade="BLOQUEIO",
                descricao=f"{p.comportamento.restricoes_ativas} restrições ativas no SCR/Serasa. "
                          "Mínimo: 0 restrições para aprovação automática.",
                base_normativa="Política de Crédito Interna — Art. 8º, §2º",
            ))
        elif p.comportamento.restricoes_ativas == 1:
            violations.append(HardRuleViolation(
                regra="HR-01",
                severidade="RESTRICAO",
                descricao="1 restrição ativa no bureau. Aprovação condicionada a análise manual.",
                base_normativa="Política de Crédito Interna — Art. 8º, §1º",
            ))

        # HR-02: Comprometimento de renda acima de 40% → limite máximo de alçada
        if p.comportamento.comprometimento_renda_pct > 40.0:
            violations.append(HardRuleViolation(
                regra="HR-02",
                severidade="RESTRICAO",
                descricao=f"Comprometimento de renda: {p.comportamento.comprometimento_renda_pct:.1f}%. "
                          "Limite regulatório de 40% (Resolução BCB 4.676/18).",
                base_normativa="Resolução BCB 4.676/2018 — Cap. IV",
            ))

        # HR-03: Atraso 90+ dias nos últimos 3 meses → bloqueio (gatilho Nível D)
        if p.comportamento.atrasos_90d_ultimos_3m > 0:
            violations.append(HardRuleViolation(
                regra="HR-03",
                severidade="BLOQUEIO",
                descricao=f"{p.comportamento.atrasos_90d_ultimos_3m} parcela(s) com atraso "
                          "de 61–90 dias nos últimos 3 meses. Provisão mínima Nível D exigida.",
                base_normativa="Resolução CMN 2.682/1999 — Art. 2º, §4º",
            ))

        # HR-04: Valor solicitado > 10× renda bruta mensal (PF)
        if p.tipo == "PF":
            ratio = p.valor_solicitado_brl / max(p.financeiro.renda_bruta_mensal_brl, 1)
            if ratio > 10:
                violations.append(HardRuleViolation(
                    regra="HR-04",
                    severidade="RESTRICAO",
                    descricao=f"Valor solicitado ({ratio:.1f}× renda) excede limite de alçada "
                              "de 10× a renda bruta mensal para operações automáticas.",
                    base_normativa="Política de Crédito Interna — Art. 12, II",
                ))

        # HR-05: Agro sem seguro safra acima de R$ 100k
        if (
            p.contexto_agro is not None
            and not p.contexto_agro.possui_seguro_safra
            and p.valor_solicitado_brl > 100_000
        ):
            violations.append(HardRuleViolation(
                regra="HR-05",
                severidade="RESTRICAO",
                descricao="Operação agro acima de R$ 100.000 sem seguro safra. "
                          "Exige análise manual ou contratação de seguro como condicionante.",
                base_normativa="Circular BACEN 3.800/2017 — Risco Climático",
            ))

        # HR-06: Score bureau abaixo de 200 → bloqueio total
        if p.comportamento.score_bureau < 200:
            violations.append(HardRuleViolation(
                regra="HR-06",
                severidade="BLOQUEIO",
                descricao=f"Score bureau ({p.comportamento.score_bureau:.0f}) abaixo do "
                          "limiar mínimo de 200 pontos para análise de crédito.",
                base_normativa="Política de Crédito Interna — Art. 5º, I",
            ))

        return violations

    # ── Feature Normalization ─────────────────────────────────────────────────

    def _normalize(self, value: float, min_v: float, max_v: float) -> float:
        """Normaliza para [0, 1]; clipa fora dos limites."""
        if max_v == min_v:
            return 0.0
        return max(0.0, min(1.0, (value - min_v) / (max_v - min_v)))

    def _build_feature_vector(
        self, p: AssociadoProfile
    ) -> dict[str, float]:
        """
        Transforma o perfil bruto em features normalizadas [0, 1].
        Variáveis 'inversas': 1 = máximo risco (para soma direta no logit).
        """
        b = p.comportamento
        r = p.relacionamento
        f = p.financeiro

        # Atrasos ponderados: 30d=1pt, 60d=2pt, 90d=4pt
        atrasos_score = (
            b.atrasos_30d_ultimos_3m * 1
            + b.atrasos_60d_ultimos_3m * 2
            + b.atrasos_90d_ultimos_3m * 4
        )

        features: dict[str, float] = {
            # Bureau (invertido: bureau baixo = risco alto = feature alta)
            "score_bureau_inv":        1.0 - self._normalize(b.score_bureau, 0, 1000),
            "restricoes_ativas":       self._normalize(b.restricoes_ativas, 0, 5),
            "comprometimento_renda":   self._normalize(b.comprometimento_renda_pct, 0, 80),
            # Tendência invertida: negativo = deterioração = risco alto
            "tendencia_pagamento_inv": self._normalize(-b.tendencia_pagamento, -5, 5),
            "atrasos_recentes":        self._normalize(atrasos_score, 0, 20),
            # Relacionamento (protetores — quanto mais, menor o risco)
            "anos_associado":          self._normalize(r.anos_associado, 0, 20),
            "capital_integralizado":   self._normalize(
                r.capital_integralizado_brl / max(p.valor_solicitado_brl, 1) * 100, 0, 20
            ),
            "participacao_assembleias": self._normalize(r.participacao_assembleias_pct, 0, 100),
            "produtos_ativos":         self._normalize(r.numero_produtos_ativos, 0, 6),
            "conta_salario":           1.0 if r.possui_conta_salario else 0.0,
            # Setor — volatilidade sistêmica
            "volatilidade_setor":      VOLATILIDADE_SETOR.get(p.setor, 0.5),
            # Agro (defaults para não-agro)
            "ciclo_plantio_entressafra": 0.0,
            "sem_seguro_safra":          0.0,
            "exposicao_clima":           0.0,
            "custeio_financiado_alto":   0.0,
        }

        # Sobrescreve features agro se aplicável
        if p.contexto_agro is not None:
            c = p.contexto_agro
            features["ciclo_plantio_entressafra"] = (
                1.0 if c.ciclo_atual in (CicloCultura.PLANTIO, CicloCultura.ENTRESSAFRA) else 0.3
            )
            features["sem_seguro_safra"]       = 0.0 if c.possui_seguro_safra else 1.0
            features["exposicao_clima"]        = self._normalize(c.exposicao_clima_score, 0, 10)
            features["custeio_financiado_alto"] = self._normalize(c.custeio_financiado_pct, 0, 100)

        return features

    # ── Logit → PD ────────────────────────────────────────────────────────────

    def _compute_logit(self, features: dict[str, float]) -> float:
        logit = BETAS["intercepto"]
        for feature, beta in BETAS.items():
            if feature == "intercepto":
                continue
            logit += beta * features.get(feature, 0.0)
        return logit

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Probabilidade de default: PD = 1 / (1 + e^(-logit))"""
        return 1.0 / (1.0 + math.exp(-x))

    def _pd_to_score(self, pd: float) -> float:
        """Converte PD [0,1] em Score Cooperativo [0, 1000]."""
        return round(max(0.0, min(1000.0, (1.0 - pd) * 1000)), 1)

    def _pd_to_bcb_level(self, pd_pct: float) -> tuple[str, float]:
        """Retorna (nível_BCB, provisão_%) conforme Resolução CMN 2.682/99."""
        for threshold, nivel, provisao in BCB_RISK_LEVELS:
            if pd_pct <= threshold:
                return nivel, provisao
        return "H", 100.0

    # ── Stress Test ───────────────────────────────────────────────────────────

    def _stress_selic(self, pd_base: float, setor: SetorEconomico, delta_pp: float = 2.0) -> float:
        """
        Simula impacto de Δpp na Selic sobre a PD.
        Modelo linear de primeira ordem: ΔPD = sensibilidade × Δpp × PD_base
        Justificativa: efeito multiplicativo — setores já estressados são mais sensíveis.
        """
        sensibilidade = SELIC_SENSITIVITY.get(setor, 0.35)
        delta_pd = sensibilidade * delta_pp * pd_base
        return min(1.0, pd_base + delta_pd)

    # ── Fatores de Risco (Explicabilidade) ────────────────────────────────────

    def _build_risk_factors(
        self, features: dict[str, float], pd: float
    ) -> list[FatorRisco]:
        """
        Decompõe a PD em fatores individuais via contribuição de Shapley simplificada
        (aproximação linear para auditabilidade BCB).
        """
        total_abs_contribution = sum(
            abs(BETAS[k] * features.get(k, 0.0))
            for k in BETAS if k != "intercepto"
        )

        fatores: list[FatorRisco] = []
        descricoes = {
            "score_bureau_inv":          "Score bureau baixo — histórico de mercado fraco",
            "restricoes_ativas":         "Restrições ativas no SCR/Serasa",
            "comprometimento_renda":     "Alto comprometimento de renda com dívidas existentes",
            "tendencia_pagamento_inv":   "Tendência de deterioração recente nos pagamentos",
            "atrasos_recentes":          "Atrasos nos últimos 3 meses (gatilho de provisão)",
            "anos_associado":            "Tempo de relacionamento com a cooperativa (protetor)",
            "capital_integralizado":     "Capital integralizado proporcional ao crédito (protetor)",
            "participacao_assembleias":  "Engajamento na governança cooperativa (protetor)",
            "produtos_ativos":           "Diversificação de produtos na cooperativa (protetor)",
            "conta_salario":             "Domicílio bancário na cooperativa (protetor)",
            "volatilidade_setor":        "Volatilidade sistêmica do setor econômico",
            "ciclo_plantio_entressafra": "Safra em fase de plantio ou entressafra (caixa negativo)",
            "sem_seguro_safra":          "Ausência de seguro safra para operação agro",
            "exposicao_clima":           "Exposição a eventos climáticos (INMET/EMBRAPA)",
            "custeio_financiado_alto":   "Alto percentual do custeio via financiamento",
        }

        for feature_name, beta in sorted(
            {k: v for k, v in BETAS.items() if k != "intercepto"}.items(),
            key=lambda x: abs(x[1] * features.get(x[0], 0.0)),
            reverse=True,
        ):
            valor = features.get(feature_name, 0.0)
            if valor == 0.0 and beta < 0:
                continue  # Fator protetor zerado — não contribuiu
            contribuicao_abs = abs(beta * valor)
            peso = contribuicao_abs / max(total_abs_contribution, 1e-9)
            impacto_pd_pp = (beta * valor / (pd * (1 - pd) + 1e-9)) * 0.01  # aproximação

            fatores.append(FatorRisco(
                nome=feature_name,
                valor_observado=round(valor, 4),
                peso_no_modelo=round(peso, 4),
                impacto_pd=round(beta * valor * 0.01, 4),  # em pp de PD
                descricao=descricoes.get(feature_name, feature_name),
            ))

        return fatores[:8]  # Top 8 fatores — limite prático de explicabilidade

    # ── API Principal ─────────────────────────────────────────────────────────

    def calculate_score(self, p: AssociadoProfile) -> AnaliseCredito:
        """
        Calcula o Score Cooperativo e gera a análise completa.
        Lança ValueError se dados mínimos obrigatórios estiverem ausentes.
        """
        # Validação mínima
        self._validate_input(p)

        hard_rules = self._apply_hard_rules(p)
        has_bloqueio = any(h.severidade == "BLOQUEIO" for h in hard_rules)

        features = self._build_feature_vector(p)
        logit    = self._compute_logit(features)
        pd       = self._sigmoid(logit)

        # Hard rules elevam PD para o piso mínimo do nível correspondente
        if has_bloqueio:
            pd = max(pd, 0.55)  # Piso nível G

        pd_pct = pd * 100
        pd_stress = self._stress_selic(pd, p.setor, delta_pp=2.0) * 100

        score_coop  = self._pd_to_score(pd)
        score_merc  = p.comportamento.score_bureau
        nivel, prov = self._pd_to_bcb_level(pd_pct)
        fatores     = self._build_risk_factors(features, pd)

        # Decisão
        if has_bloqueio:
            decisao = DecisaoEnum.BLOQUEADO
        elif any(h.severidade == "RESTRICAO" for h in hard_rules) or 10 <= pd_pct < 35:
            decisao = DecisaoEnum.ANALISE_MANUAL
        elif pd_pct >= 35:
            decisao = DecisaoEnum.NEGADO
        elif score_coop >= 650:
            decisao = DecisaoEnum.APROVADO
        else:
            decisao = DecisaoEnum.APROVADO_PARCIAL

        # Limite aprovado
        if decisao in (DecisaoEnum.BLOQUEADO, DecisaoEnum.NEGADO):
            limite = 0.0
        elif decisao == DecisaoEnum.APROVADO_PARCIAL:
            fator_reducao = score_coop / 1000
            limite = round(p.valor_solicitado_brl * fator_reducao * 0.8, -2)
        else:
            limite = p.valor_solicitado_brl

        # Taxa sugerida = Selic + spread ajustado por risco
        spread_risco = pd_pct * 0.4  # 0.4pp de spread por pp de PD
        taxa_am = (CUSTO_CAPITAL_BASE_PCT + spread_risco) / 12

        # Prazo máximo — inversamente proporcional ao risco
        prazo_max = max(6, min(p.prazo_meses, int(60 * (1 - pd))))

        # Flags operacionais DRO 5050
        flags = self._detect_operational_flags(p, features)

        return AnaliseCredito(
            associado_id=p.id,
            score_cooperativo=score_coop,
            score_mercado=score_merc,
            probabilidade_default=round(pd_pct, 2),
            pd_stress_selic_mais_2pct=round(pd_stress, 2),
            decisao=decisao,
            limite_aprovado_brl=limite,
            taxa_sugerida_pct=round(taxa_am, 2),
            prazo_maximo_meses=prazo_max,
            fatores_risco=fatores,
            hard_rules_violadas=hard_rules,
            nivel_risco_bcb=nivel,
            provisao_requerida_pct=prov,
            flags_operacionais=flags,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            versao_modelo=self.VERSION,
        )

    def suggest_limit(self, analise: AnaliseCredito, p: AssociadoProfile) -> DecisaoCredito:
        """Gera o resumo executivo para exibição no frontend e registro no core bancário."""
        principal_fator = (
            analise.fatores_risco[0].descricao
            if analise.fatores_risco
            else "Dados insuficientes"
        )

        requer_garantia   = analise.nivel_risco_bcb in ("C", "D", "E", "F", "G", "H")
        requer_coobrigado = analise.nivel_risco_bcb in ("D", "E", "F", "G", "H")

        resumo_map = {
            DecisaoEnum.APROVADO:         f"Crédito aprovado em R$ {analise.limite_aprovado_brl:,.2f}. "
                                           f"Score cooperativo sólido ({analise.score_cooperativo:.0f}/1000).",
            DecisaoEnum.APROVADO_PARCIAL: f"Aprovado parcialmente em R$ {analise.limite_aprovado_brl:,.2f} "
                                           f"(solicitado: R$ {p.valor_solicitado_brl:,.2f}). "
                                           "Score abaixo do limiar para aprovação total.",
            DecisaoEnum.ANALISE_MANUAL:   "Encaminhado para análise manual do comitê de crédito. "
                                           "Restrições identificadas exigem avaliação humana.",
            DecisaoEnum.NEGADO:           f"Crédito negado. PD de {analise.probabilidade_default:.1f}% "
                                           "excede o limite máximo de 35% para aprovação.",
            DecisaoEnum.BLOQUEADO:        "Operação bloqueada por Hard Rule regulatória. "
                                           "Não pode ser aprovada na alçada automática.",
        }

        return DecisaoCredito(
            associado_id=p.id,
            nome=p.nome,
            decisao=analise.decisao,
            score_cooperativo=analise.score_cooperativo,
            limite_aprovado_brl=analise.limite_aprovado_brl,
            taxa_sugerida_pct=analise.taxa_sugerida_pct,
            nivel_risco_bcb=analise.nivel_risco_bcb,
            resumo_decisao=resumo_map.get(analise.decisao, ""),
            principal_fator_risco=principal_fator,
            requer_garantia=requer_garantia,
            requer_coobrigado=requer_coobrigado,
        )

    def generate_risk_report(
        self, analise: AnaliseCredito, p: AssociadoProfile
    ) -> dict:
        """
        Gera relatório estruturado para auditoria DRO 5050 S3.
        Formato JSON compatível com remessa ao BACEN em jun/2026.
        """
        decisao_obj = self.suggest_limit(analise, p)

        return {
            "metadata": {
                "versao_relatorio": "DRO-5050-S3-v1",
                "versao_modelo":    analise.versao_modelo,
                "timestamp_utc":    analise.timestamp_utc,
                "analista_id":      p.analista_id or "AUTO",
                "id_operacao":      str(uuid.uuid4()),
            },
            "identificacao": {
                "associado_id":   p.id,
                "tipo":           p.tipo,
                "setor":          p.setor.value,
                "data_analise":   p.data_analise.isoformat(),
            },
            "solicitacao": {
                "valor_brl":      p.valor_solicitado_brl,
                "finalidade":     p.finalidade,
                "prazo_meses":    p.prazo_meses,
            },
            "resultado": {
                "decisao":                  analise.decisao.value,
                "limite_aprovado_brl":      analise.limite_aprovado_brl,
                "taxa_sugerida_pct_am":     analise.taxa_sugerida_pct,
                "prazo_maximo_meses":       analise.prazo_maximo_meses,
            },
            "scoring": {
                "score_cooperativo":        analise.score_cooperativo,
                "score_mercado_bureau":     analise.score_mercado,
                "probabilidade_default_pct": analise.probabilidade_default,
                "pd_stress_selic_plus2_pct": analise.pd_stress_selic_mais_2pct,
                "nivel_risco_bcb":          analise.nivel_risco_bcb,
                "provisao_requerida_pct":   analise.provisao_requerida_pct,
                "selic_referencia_pct":     SELIC_ATUAL_PCT,
            },
            "explicabilidade": {
                "fator_principal":  decisao_obj.principal_fator_risco,
                "top_fatores": [
                    {
                        "nome":          f.nome,
                        "descricao":     f.descricao,
                        "peso":          f.peso_no_modelo,
                        "impacto_pd_pp": f.impacto_pd,
                    }
                    for f in analise.fatores_risco
                ],
            },
            "hard_rules": [
                {
                    "regra":           h.regra,
                    "severidade":      h.severidade,
                    "descricao":       h.descricao,
                    "base_normativa":  h.base_normativa,
                }
                for h in analise.hard_rules_violadas
            ],
            "conformidade_dro5050": {
                "flags_operacionais":         analise.flags_operacionais,
                "requer_garantia":            decisao_obj.requer_garantia,
                "requer_coobrigado":          decisao_obj.requer_coobrigado,
                "passou_hard_rules":          not any(
                    h.severidade == "BLOQUEIO" for h in analise.hard_rules_violadas
                ),
                "decisao_explicavel":         len(analise.fatores_risco) >= 3,
                "apto_remessa_bacen":         len(analise.flags_operacionais) == 0,
            },
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_input(self, p: AssociadoProfile) -> None:
        erros: list[str] = []
        if p.financeiro.renda_bruta_mensal_brl <= 0:
            erros.append("renda_bruta_mensal_brl deve ser > 0")
        if not 0 <= p.comportamento.score_bureau <= 1000:
            erros.append("score_bureau deve estar entre 0 e 1000")
        if p.valor_solicitado_brl <= 0:
            erros.append("valor_solicitado_brl deve ser > 0")
        if p.setor in (
            SetorEconomico.AGRO_SOJA, SetorEconomico.AGRO_MILHO,
            SetorEconomico.AGRO_CAFE, SetorEconomico.AGRO_PECUARIA
        ) and p.contexto_agro is None:
            erros.append("contexto_agro é obrigatório para associados do setor agro")
        if erros:
            raise ValueError(f"Dados inválidos no perfil '{p.id}': {'; '.join(erros)}")

    def _detect_operational_flags(
        self, p: AssociadoProfile, features: dict[str, float]
    ) -> list[str]:
        """
        Detecta falhas no processo de análise — evidência para DRO 5050 S3.
        Flags aqui significam que o processo operacional precisa de melhoria,
        não necessariamente que o crédito deve ser negado.
        """
        flags: list[str] = []

        if p.comportamento.score_bureau == 0:
            flags.append("FLAG-OP-01: Score bureau ausente — consulta SCR não realizada")
        if p.financeiro.patrimonio_liquido_brl == 0 and p.valor_solicitado_brl > 50_000:
            flags.append("FLAG-OP-02: Patrimônio líquido não informado para operação > R$ 50k")
        if p.analista_id is None:
            flags.append("FLAG-OP-03: Analista não identificado — rastreabilidade comprometida")
        if (
            p.tipo == "PJ"
            and p.financeiro.faturamento_mensal_pj_brl is None
        ):
            flags.append("FLAG-OP-04: Faturamento PJ não informado — análise de capacidade incompleta")
        if (
            p.setor in (SetorEconomico.AGRO_SOJA, SetorEconomico.AGRO_MILHO)
            and p.contexto_agro is not None
            and p.contexto_agro.exposicao_clima_score == 0.0
        ):
            flags.append("FLAG-OP-05: Exposição climática zerada em setor agro — dado possivelmente ausente")

        return flags
