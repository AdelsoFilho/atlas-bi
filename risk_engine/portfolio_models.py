"""
portfolio_models.py — Atlas BI Risk Engine
Modelos Pydantic v2 para Carteira de Crédito Cooperativo.

Base normativa:
  - Resolução CMN 2.682/1999 — Classificação de risco e PCLD
  - Resolução BCB 4.676/2018 — Avaliação da capacidade de pagamento
  - Resolução CMN 4.557/2017 — Gestão de risco de crédito (stress test)
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field, model_validator


# ─── Enumerações ──────────────────────────────────────────────────────────────

class NivelRiscoBCB(str, Enum):
    """
    Classificação de risco por dias em atraso (DPD).
    Res. CMN 2.682/1999 — Art. 2º.
    O prazo máximo para reclassificação é de 60 dias (operações até R$ 50k)
    ou 90 dias (demais). Aqui adotamos o critério conservador universal.
    """
    AA = "AA"   # 0 dias — adimplente, melhor histórico
    A  = "A"    # 1–14 dias
    B  = "B"    # 15–30 dias
    C  = "C"    # 31–60 dias
    D  = "D"    # 61–90 dias    ← gatilho de atenção supervisora
    E  = "E"    # 91–120 dias
    F  = "F"    # 121–150 dias
    G  = "G"    # 151–180 dias
    H  = "H"    # >180 dias     ← provisão 100%, write-off candidate


class TipoOperacao(str, Enum):
    CDC_PESSOAL    = "CDC_PESSOAL"      # Crédito Direto ao Consumidor
    CAPITAL_GIRO   = "CAPITAL_GIRO"     # PJ — giro de curto prazo
    IMOBILIARIO    = "IMOBILIARIO"      # Crédito habitacional / comercial
    AGRO_CUSTEIO   = "AGRO_CUSTEIO"    # Custeio de safra
    AGRO_INVESTIMENTO = "AGRO_INVEST"  # Máquinas, equipamentos, terra
    CONSIGNADO     = "CONSIGNADO"       # Desconto em folha
    CHEQUE_ESPECIAL = "CH_ESPECIAL"     # Rotativo — maior risco


class TipoTaxa(str, Enum):
    FIXA     = "FIXA"       # Não impactada por mudança de Selic
    VARIAVEL = "VARIAVEL"   # Indexada ao CDI/Selic — impactada no stress test


class TipoGarantia(str, Enum):
    SEM_GARANTIA  = "SEM_GARANTIA"
    AVALISTA      = "AVALISTA"      # Coobrigado pessoa física
    PENHOR_SAFRA  = "PENHOR_SAFRA"  # Penhor de produto agrícola
    ALIENACAO_FID = "ALIENACAO_FID" # Alienação fiduciária de bem móvel/imóvel
    HIPOTECA      = "HIPOTECA"      # Hipoteca de imóvel
    PENHOR_EQUIP  = "PENHOR_EQUIP"  # Penhor de máquinas/equipamentos


class SetorAtividade(str, Enum):
    AGRONEGOCIO  = "AGRONEGOCIO"
    COMERCIO     = "COMERCIO"
    INDUSTRIA    = "INDUSTRIA"
    SERVICOS     = "SERVICOS"
    FUNCIONALISMO = "FUNCIONALISMO"
    APOSENTADO   = "APOSENTADO"
    RURAL_FAMILIAR = "RURAL_FAMILIAR"


# ─── Entidade: Associado ─────────────────────────────────────────────────────

class Associado(BaseModel):
    """
    Perfil completo do associado — combina dados de bureau com vínculo mutualista.

    O diferencial cooperativo está nos campos de relacionamento:
    um associado com 15 anos de casa e R$ 8.000 em cotas partes
    tem risco estruturalmente diferente de um cliente bancário novo
    com o mesmo score Serasa.
    """
    id: str
    nome: str
    cpf_cnpj: str
    tipo: str = Field(pattern="^(PF|PJ)$")
    setor: SetorAtividade
    data_ingresso_cooperativa: date

    # Capacidade financeira
    renda_bruta_mensal_brl: float = Field(gt=0)
    patrimonio_liquido_brl: float = Field(ge=0)
    faturamento_mensal_pj_brl: Optional[float] = None  # Apenas PJ

    # Relacionamento mutualista (diferencial cooperativo)
    capital_integralizado_brl: float = Field(ge=0)      # Cotas subscritas e integralizadas
    cotas_partes_qty: int = Field(ge=0)                  # Número de cotas capital social
    participacao_assembleias_pct: float = Field(ge=0, le=100)  # % assembleias (2 anos)
    numero_produtos_ativos: int = Field(ge=0)            # Relacionamento ativo

    # Scores
    score_serasa: float = Field(ge=0, le=1000)           # Bureau externo
    score_cooperativo: float = Field(default=0, ge=0, le=1000)  # Calculado pela engine

    # Flags
    possui_conta_salario: bool = False
    possui_historico_negativo_externo: bool = False      # Negativado fora da coop

    @computed_field  # type: ignore[misc]
    @property
    def anos_associado(self) -> float:
        delta = date.today() - self.data_ingresso_cooperativa
        return round(delta.days / 365.25, 2)


# ─── Entidade: Histórico de Pagamento ────────────────────────────────────────

class HistoricoPagamento(BaseModel):
    """
    Registro comportamental dentro da cooperativa.
    Mais relevante que bureau externo para scoring mutualista.
    """
    operacao_id: str
    dpd_atual: int = Field(ge=0)                # Days Past Due — dias de atraso hoje
    dpd_maximo_12m: int = Field(ge=0)           # Máximo DPD nos últimos 12 meses
    ocorrencias_atraso_12m: int = Field(ge=0)   # Qtd. de atrasos >5 dias no ano
    renegociacoes: int = Field(ge=0)             # Renegociações acumuladas
    refinanciamentos: int = Field(ge=0)          # Refinanciamentos acumulados


# ─── Entidade: Garantia ──────────────────────────────────────────────────────

class Garantia(BaseModel):
    tipo: TipoGarantia
    valor_avaliado_brl: float = Field(ge=0)
    data_avaliacao: date
    percentual_cobertura: float = Field(ge=0, le=100)  # % do saldo coberto pela garantia


# ─── Entidade: Operação de Crédito ───────────────────────────────────────────

class OperacaoCredito(BaseModel):
    """
    Operação individual na carteira — granularidade base do sistema de risco.

    Regra financeira: prestação (PMT) deve ser calculada como
      PMT = PV × r / (1 − (1+r)^−n)
    onde r = taxa_juros_mensal / 100 e n = prazo_meses.
    """
    id: str
    associado_id: str
    tipo: TipoOperacao
    tipo_taxa: TipoTaxa
    setor_risco: SetorAtividade          # Setor econômico da operação (pode diferir do associado)

    # Valores financeiros
    valor_contratado_brl: float = Field(gt=0)
    saldo_devedor_brl: float = Field(ge=0)    # Posição atual (corrigida)
    taxa_juros_mensal_pct: float = Field(gt=0) # Taxa efetiva ao mês
    prazo_meses: int = Field(gt=0)
    prazo_restante_meses: int = Field(ge=0)
    prestacao_mensal_brl: float = Field(gt=0)

    # Qualidade
    historico: HistoricoPagamento
    garantias: list[Garantia] = Field(default_factory=list)

    # Datas
    data_contratacao: date
    data_vencimento: date

    # Campos calculados pela engine (preenchidos após análise)
    nivel_risco: NivelRiscoBCB = NivelRiscoBCB.AA
    pcld_individual_brl: float = 0.0
    ltv: float = 0.0                     # Loan-to-Value = saldo / valor garantia

    @computed_field  # type: ignore[misc]
    @property
    def comprometimento_renda_pct(self) -> float:
        """Calculado na engine após vínculo com Associado."""
        return 0.0

    @computed_field  # type: ignore[misc]
    @property
    def total_garantias_brl(self) -> float:
        return sum(g.valor_avaliado_brl for g in self.garantias)


# ─── Entidade: Carteira ──────────────────────────────────────────────────────

class Carteira(BaseModel):
    """Carteira consolidada — unidade de análise do CRO."""
    id: str
    nome: str
    data_posicao: date                            # Data base da carteira
    associados: dict[str, Associado]              # key: associado_id
    operacoes: list[OperacaoCredito]

    @computed_field  # type: ignore[misc]
    @property
    def saldo_total_brl(self) -> float:
        return sum(op.saldo_devedor_brl for op in self.operacoes)

    @computed_field  # type: ignore[misc]
    @property
    def total_operacoes(self) -> int:
        return len(self.operacoes)


# ─── Constantes Regulatórias ─────────────────────────────────────────────────

# Percentuais de PCLD por nível — Res. CMN 2.682/99 Art. 6º
PCLD_PERCENTUAIS: dict[NivelRiscoBCB, float] = {
    NivelRiscoBCB.AA: 0.0,
    NivelRiscoBCB.A:  0.5,
    NivelRiscoBCB.B:  1.0,
    NivelRiscoBCB.C:  3.0,
    NivelRiscoBCB.D:  10.0,
    NivelRiscoBCB.E:  30.0,
    NivelRiscoBCB.F:  50.0,
    NivelRiscoBCB.G:  70.0,
    NivelRiscoBCB.H:  100.0,
}

# DPD máximo para cada nível (critério conservador — operações > R$ 50k)
DPD_PARA_NIVEL: list[tuple[int, NivelRiscoBCB]] = [
    (0,   NivelRiscoBCB.AA),
    (14,  NivelRiscoBCB.A),
    (30,  NivelRiscoBCB.B),
    (60,  NivelRiscoBCB.C),
    (90,  NivelRiscoBCB.D),
    (120, NivelRiscoBCB.E),
    (150, NivelRiscoBCB.F),
    (180, NivelRiscoBCB.G),
    (9999, NivelRiscoBCB.H),
]

SELIC_ATUAL_PCT_AA: float = 14.75   # Selic atual a.a. (Copom mar/2026)
SELIC_ATUAL_PCT_AM: float = SELIC_ATUAL_PCT_AA / 12

# LTV máximo por tipo de garantia (limites prudenciais internos)
LTV_MAXIMO: dict[TipoGarantia, float] = {
    TipoGarantia.SEM_GARANTIA:  0.60,
    TipoGarantia.AVALISTA:      0.75,
    TipoGarantia.PENHOR_SAFRA:  0.70,
    TipoGarantia.ALIENACAO_FID: 0.80,
    TipoGarantia.HIPOTECA:      0.85,
    TipoGarantia.PENHOR_EQUIP:  0.70,
}
