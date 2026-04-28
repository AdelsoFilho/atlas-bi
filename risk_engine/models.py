"""
Modelos de dados — Atlas BI Risk Engine
Esquema central do associado e outputs da análise.

Feature engineering justificado para o cenário Brasil 2026:
  Selic 15% → custo do capital elevado → cada variável reduz PD (Probability of Default)
  de forma transparente e auditável.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


# ─── Enums ────────────────────────────────────────────────────────────────────

class SetorEconomico(str, Enum):
    AGRO_SOJA        = "agro_soja"        # Alta volatilidade: El Niño + câmbio + Selic
    AGRO_MILHO       = "agro_milho"       # Volatilidade média
    AGRO_CAFE        = "agro_cafe"        # Volatilidade média-alta (ciclo bienal)
    AGRO_PECUARIA    = "agro_pecuaria"    # Volatilidade média (preço da arroba)
    COMERCIO_VAREJO  = "comercio_varejo"  # Sensível à Selic (crédito ao consumidor seco)
    SERVICOS_PME     = "servicos_pme"     # Moderado
    ASSALARIADO_CLT  = "assalariado_clt"  # Baixo: renda estável
    APOSENTADO_INSS  = "aposentado_inss"  # Muito baixo: indexado ao INSS
    FUNCIONALISMO    = "funcionalismo"    # Muito baixo: margem consignável
    PROFISSIONAL_LIB = "profissional_lib" # Moderado: oscilação de receita


class CicloCultura(str, Enum):
    """Estágio do ciclo da safra — impacta capacidade de pagamento no mês."""
    PLANTIO    = "plantio"    # Alto consumo de insumos, caixa negativo
    CRESCIMENTO = "crescimento"
    COLHEITA   = "colheita"   # Pico de receita
    ENTRESSAFRA = "entressafra"  # Risco máximo: sem renda, financiamentos vencendo


class DecisaoEnum(str, Enum):
    APROVADO        = "APROVADO"
    APROVADO_PARCIAL = "APROVADO_PARCIAL"  # Limite menor que solicitado
    ANALISE_MANUAL  = "ANALISE_MANUAL"
    NEGADO          = "NEGADO"
    BLOQUEADO       = "BLOQUEADO"          # Hard rule ativada


# ─── Input: Perfil do Associado ───────────────────────────────────────────────

@dataclass
class RelacionamentoCooperativa:
    """
    Variáveis de fidelidade — reduzem PD porque o associado tem 'skin in the game'.

    Justificativa matemática:
      Cada ano adicional como associado reduz PD em ~0.8% (coef. empírico SNCC).
      Capital integralizado >5% do limite pedido reduz PD em 1.2%.
      Participação em assembleias captura governança e comprometimento (proxy de
      caráter no modelo 5Cs de crédito).
    """
    anos_associado: float                   # Tempo como associado (frações permitidas)
    capital_integralizado_brl: float        # R$ integralizados de capital social
    participacao_assembleias_pct: float     # % das assembleias dos últimos 2 anos (0–100)
    numero_produtos_ativos: int             # Conta, crédito, seguro, previdência etc.
    possui_conta_salario: bool              # Domicílio bancário na cooperativa
    historico_inadimplencia_coop: int       # Qtd. de parcelas em atraso nos últimos 24m


@dataclass
class ComportamentoPagamento:
    """
    Tendência recente — mais preditiva que histórico estático em ambientes de alta Selic.

    Justificativa: Com Selic 15%, a deterioração é rápida. Um score estático de 700
    calculado há 6 meses pode esconder uma espiral de endividamento iniciada há 90 dias.
    Capturamos a DERIVADA do comportamento, não só o estado.
    """
    score_bureau: float                     # Serasa/SCR: 0–1000
    restricoes_ativas: int                  # Negativações ativas (SPC/Serasa)
    atrasos_30d_ultimos_3m: int             # Parcelas 1–30 dias em atraso (últimos 3m)
    atrasos_60d_ultimos_3m: int             # 31–60 dias
    atrasos_90d_ultimos_3m: int             # 61–90 dias (gatilho de provisão BACEN)
    tendencia_pagamento: float              # Δ médio das parcelas: positivo = melhorando
    comprometimento_renda_pct: float        # % da renda bruta comprometida com dívidas (0–100)
    dividas_total_brl: float                # Total de dívidas no mercado (SCR)


@dataclass
class PerfilFinanceiro:
    """Capacidade de pagamento — fluxo de caixa e patrimônio."""
    renda_bruta_mensal_brl: float
    patrimonio_liquido_brl: float           # Imóveis + veículos − passivos (auto-declarado)
    faturamento_mensal_pj_brl: Optional[float] = None  # Apenas para PJ
    margem_liquida_pj_pct: Optional[float] = None      # % lucro sobre faturamento PJ
    receita_agro_anual_brl: Optional[float] = None     # Receita total da safra (agro)
    area_cultivada_hectares: Optional[float] = None    # Ha cultivados


@dataclass
class ContextoAgro:
    """
    Variáveis sazonais e climáticas — obrigatórias para associados do setor agro.

    Justificativa: Selic 15% + eventos climáticos (El Niño/La Niña) = risco sistêmico
    concentrado. Um modelo sem sazonalidade subestima PD em 40–60% no plantio de soja.
    """
    ciclo_atual: CicloCultura
    cultura_principal: str                  # "soja", "milho", "café", "boi gordo"
    possui_seguro_safra: bool               # Reduz PD significativamente
    exposicao_clima_score: float            # 0–10: índice público INMET/EMBRAPA por região
    preco_commodity_tendencia: float        # Δ% preço futuro da commodity (−100 a +100)
    custeio_financiado_pct: float           # % do custeio financiado (vs. capital próprio)


@dataclass
class AssociadoProfile:
    """
    Perfil completo do associado — input para a CreditRiskEngine.
    Campos obrigatórios são os mínimos para análise sem Hard Rule de dados incompletos.
    """
    # Identificação
    id: str
    nome: str
    cpf_cnpj: str
    tipo: str                               # "PF" | "PJ"
    setor: SetorEconomico
    data_nascimento_fundacao: date

    # Solicitação
    valor_solicitado_brl: float
    finalidade: str
    prazo_meses: int

    # Módulos de risco
    relacionamento: RelacionamentoCooperativa
    comportamento: ComportamentoPagamento
    financeiro: PerfilFinanceiro

    # Opcional — obrigatório apenas para setor agro
    contexto_agro: Optional[ContextoAgro] = None

    # Metadados da análise
    data_analise: date = field(default_factory=date.today)
    analista_id: Optional[str] = None


# ─── Output: Resultado da Análise ─────────────────────────────────────────────

@dataclass
class FatorRisco:
    """Fator individual explicando a decisão — requisito de explicabilidade DRO 5050."""
    nome: str
    valor_observado: float
    peso_no_modelo: float                   # Contribuição relativa (0–1)
    impacto_pd: float                       # Quanto este fator eleva/reduz PD (pp)
    descricao: str


@dataclass
class HardRuleViolation:
    """Violação de regra rígida — bloqueia ou restringe independentemente do score."""
    regra: str
    severidade: str                         # "BLOQUEIO" | "RESTRICAO" | "ALERTA"
    descricao: str
    base_normativa: str                     # Ex: "Resolução CMN 2.682/99 — Art. 4º"


@dataclass
class AnaliseCredito:
    """Output completo da engine — contém score, decisão e auditoria."""
    associado_id: str
    score_cooperativo: float                # 0–1000 (modelo híbrido interno)
    score_mercado: float                    # Normalizado do bureau (0–1000)
    probabilidade_default: float            # PD em % (0–100)
    pd_stress_selic_mais_2pct: float        # PD sob stress: Selic + 2pp

    decisao: DecisaoEnum
    limite_aprovado_brl: float
    taxa_sugerida_pct: float                # Taxa ao mês sugerida pelo modelo
    prazo_maximo_meses: int

    fatores_risco: list[FatorRisco]
    hard_rules_violadas: list[HardRuleViolation]

    # Campos obrigatórios DRO 5050 S3
    nivel_risco_bcb: str                    # AA / A / B / C / D / E / F / G / H
    provisao_requerida_pct: float           # % de provisão per Res. 2682/99
    flags_operacionais: list[str]           # Falhas no processo de análise

    timestamp_utc: str
    versao_modelo: str = "1.0.0"


@dataclass
class DecisaoCredito:
    """Resumo executivo — para exibição no frontend e registro no core bancário."""
    associado_id: str
    nome: str
    decisao: DecisaoEnum
    score_cooperativo: float
    limite_aprovado_brl: float
    taxa_sugerida_pct: float
    nivel_risco_bcb: str
    resumo_decisao: str
    principal_fator_risco: str
    requer_garantia: bool
    requer_coobrigado: bool
