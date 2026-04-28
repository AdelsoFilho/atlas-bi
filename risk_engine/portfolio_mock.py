"""
portfolio_mock.py — Atlas BI Risk Engine
Gerador de carteira mock realista: 100 operações, 60 associados.

Distribuição calibrada para carteira típica de cooperativa de médio porte:
  - Agro (custeio + investimento):    35 ops  35%
  - Comércio/Varejo PJ:               30 ops  30%
  - CDC Pessoal / Consignado:         25 ops  25%
  - Imobiliário:                      10 ops  10%

Perfis de risco:
  - Bons pagadores (AA/A):   ~55%
  - Atenção (B/C):           ~25%
  - Inadimplentes (D/H):     ~20%  ← acima da média SNCC para teste de estresse
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

import numpy as np

from .portfolio_models import (
    Associado,
    Carteira,
    Garantia,
    HistoricoPagamento,
    NivelRiscoBCB,
    OperacaoCredito,
    SetorAtividade,
    TipoGarantia,
    TipoOperacao,
    TipoTaxa,
)


# ─── RNG determinística (reprodutibilidade) ──────────────────────────────────
RNG = np.random.default_rng(seed=2026)


def _rand(lo: float, hi: float) -> float:
    return float(RNG.uniform(lo, hi))


def _randi(lo: int, hi: int) -> int:
    return int(RNG.integers(lo, hi + 1))


def _pick(arr: list):
    return arr[int(RNG.integers(0, len(arr)))]


def _data_passada(dias: int) -> date:
    return date.today() - timedelta(days=dias)


def _pmt(pv: float, taxa_am: float, n: int) -> float:
    """Price (Sistema Francês): PMT = PV × r / (1 − (1+r)^−n)"""
    if taxa_am <= 0 or n <= 0:
        return pv / max(n, 1)
    r = taxa_am / 100
    return pv * r / (1 - (1 + r) ** -n)


def _saldo_devedor_atual(pv: float, taxa_am: float, n_total: int, n_pago: int) -> float:
    """Saldo devedor após n_pago prestações (Price)."""
    r = taxa_am / 100
    if r <= 0:
        return pv * (n_total - n_pago) / max(n_total, 1)
    return pv * ((1 + r) ** n_total - (1 + r) ** n_pago) / ((1 + r) ** n_total - 1)


# ─── Nomes e dados de referência ─────────────────────────────────────────────
NOMES_PF = [
    "Antônio Ferreira", "Maria das Graças", "José Luiz Oliveira", "Ana Paula Costa",
    "Roberto Mendes", "Fernanda Lima", "Marcos Souza", "Juliana Alves",
    "Carlos Eduardo", "Patrícia Rocha", "Sérgio Nunes", "Luciana Pereira",
    "Fabio Carvalho", "Camila Vieira", "Rogério Santos", "Adriana Fonseca",
    "Alexandre Melo", "Vanessa Barros", "Fernando Dias", "Cristiane Moura",
    "Paulo Henrique", "Daniela Castro", "Leandro Gomes", "Aline Ribeiro",
    "Gustavo Silva", "Mariana Campos", "Thiago Araújo", "Renata Xavier",
]

NOMES_PJ = [
    "Agro Cerrado Ltda", "Comércio União ME", "Fazenda Santa Fé",
    "Distribuidora Central SA", "Pecuária Rio Verde", "Tech Serviços ME",
    "Supermercado Estrela Ltda", "Coop Agro Leste", "Metalúrgica União",
    "Transporte Rápido ME", "Soja Sul SA", "Padaria Central ME",
    "Maquinas & Cia Ltda", "Laticínios Norte ME", "Construções Alpha",
]

CIDADES = [
    "Sorriso/MT", "Lucas do Rio Verde/MT", "Campo Verde/MT", "Rondonópolis/MT",
    "Primavera do Leste/MT", "Londrina/PR", "Maringá/PR", "Cascavel/PR",
    "Passo Fundo/RS", "Cruz Alta/RS",
]


# ─── Gerador de Associados ────────────────────────────────────────────────────

def _gerar_associado(id_: str, perfil: str) -> Associado:
    """
    perfil: "excelente" | "bom" | "regular" | "fragil" | "inadimplente"
    """
    eh_pj = perfil in ("excelente",) and RNG.random() < 0.4

    params = {
        "excelente": dict(
            score=(780, 950), anos=(10, 22), capital=(8_000, 40_000),
            renda=(15_000, 60_000), patrimonio=(200_000, 2_000_000),
            assembly=(70, 100), produtos=(4, 6), neg_ext=False,
        ),
        "bom": dict(
            score=(620, 780), anos=(4, 12), capital=(3_000, 12_000),
            renda=(6_000, 18_000), patrimonio=(80_000, 500_000),
            assembly=(40, 80), produtos=(2, 5), neg_ext=False,
        ),
        "regular": dict(
            score=(450, 620), anos=(2, 7), capital=(500, 4_000),
            renda=(3_500, 9_000), patrimonio=(15_000, 150_000),
            assembly=(20, 55), produtos=(1, 3), neg_ext=RNG.random() < 0.25,
        ),
        "fragil": dict(
            score=(300, 500), anos=(1, 4), capital=(200, 2_000),
            renda=(2_500, 6_000), patrimonio=(5_000, 50_000),
            assembly=(10, 40), produtos=(1, 2), neg_ext=RNG.random() < 0.50,
        ),
        "inadimplente": dict(
            score=(150, 400), anos=(0.5, 3), capital=(100, 1_500),
            renda=(2_000, 5_000), patrimonio=(0, 20_000),
            assembly=(0, 20), produtos=(1, 2), neg_ext=True,
        ),
    }[perfil]

    tipo = "PJ" if eh_pj else "PF"
    nome = _pick(NOMES_PJ) if eh_pj else _pick(NOMES_PF)
    cpf_cnpj = (
        f"{_randi(10,99)}.{_randi(100,999)}.{_randi(100,999)}/0001-{_randi(10,99)}"
        if eh_pj
        else f"{_randi(100,999)}.{_randi(100,999)}.{_randi(100,999)}-{_randi(10,99)}"
    )

    anos = _rand(*params["anos"])  # type: ignore[arg-type]
    ingresso = date.today() - timedelta(days=int(anos * 365.25))

    setor_map = {
        "excelente": _pick([SetorAtividade.AGRONEGOCIO, SetorAtividade.FUNCIONALISMO, SetorAtividade.COMERCIO]),
        "bom":       _pick([SetorAtividade.COMERCIO, SetorAtividade.AGRONEGOCIO, SetorAtividade.SERVICOS]),
        "regular":   _pick([SetorAtividade.COMERCIO, SetorAtividade.SERVICOS, SetorAtividade.RURAL_FAMILIAR]),
        "fragil":    _pick([SetorAtividade.COMERCIO, SetorAtividade.SERVICOS]),
        "inadimplente": _pick([SetorAtividade.COMERCIO, SetorAtividade.SERVICOS]),
    }

    return Associado(
        id=id_,
        nome=nome,
        cpf_cnpj=cpf_cnpj,
        tipo=tipo,
        setor=setor_map[perfil],
        data_ingresso_cooperativa=ingresso,
        renda_bruta_mensal_brl=round(_rand(*params["renda"]), 2),  # type: ignore[arg-type]
        patrimonio_liquido_brl=round(_rand(*params["patrimonio"]), 2),  # type: ignore[arg-type]
        capital_integralizado_brl=round(_rand(*params["capital"]), 2),  # type: ignore[arg-type]
        cotas_partes_qty=_randi(5, 200),
        participacao_assembleias_pct=round(_rand(*params["assembly"]), 1),  # type: ignore[arg-type]
        numero_produtos_ativos=_randi(*params["produtos"]),  # type: ignore[arg-type]
        score_serasa=round(_rand(*params["score"]), 0),  # type: ignore[arg-type]
        possui_conta_salario=RNG.random() < (0.8 if perfil == "excelente" else 0.4),
        possui_historico_negativo_externo=params["neg_ext"],  # type: ignore[arg-type]
        faturamento_mensal_pj_brl=round(_rand(30_000, 500_000), 2) if eh_pj else None,
    )


# ─── Gerador de Operação ──────────────────────────────────────────────────────

def _garantia_para_tipo(tipo_op: TipoOperacao, valor_contratado: float) -> list[Garantia]:
    if tipo_op in (TipoOperacao.AGRO_CUSTEIO, TipoOperacao.AGRO_INVESTIMENTO):
        tipo_gar = _pick([TipoGarantia.PENHOR_SAFRA, TipoGarantia.ALIENACAO_FID, TipoGarantia.HIPOTECA])
        cobertura = _rand(0.85, 1.30)
    elif tipo_op == TipoOperacao.IMOBILIARIO:
        tipo_gar = TipoGarantia.HIPOTECA
        cobertura = _rand(1.10, 1.50)
    elif tipo_op == TipoOperacao.CAPITAL_GIRO:
        tipo_gar = _pick([TipoGarantia.AVALISTA, TipoGarantia.PENHOR_EQUIP, TipoGarantia.SEM_GARANTIA])
        cobertura = _rand(0.60, 1.10)
    else:  # CDC / Consignado
        tipo_gar = _pick([TipoGarantia.AVALISTA, TipoGarantia.SEM_GARANTIA])
        cobertura = _rand(0.50, 0.90)

    if tipo_gar == TipoGarantia.SEM_GARANTIA:
        return []

    return [Garantia(
        tipo=tipo_gar,
        valor_avaliado_brl=round(valor_contratado * cobertura, 2),
        data_avaliacao=_data_passada(_randi(30, 365)),
        # percentual_cobertura representa o quanto da operação a garantia cobre
        # capped at 100 (excesso fica no valor_avaliado)
        percentual_cobertura=min(round(cobertura * 100, 1), 100.0),
    )]


def _gerar_operacao(op_id: str, assoc_id: str, template: dict) -> OperacaoCredito:
    tipo_op   = template["tipo"]
    setor_op  = template["setor"]
    taxa_am   = round(_rand(*template["taxa"]), 3)
    valor     = round(_rand(*template["valor"]), -2)  # Arredonda centenas
    prazo     = _randi(*template["prazo"])
    dpd       = template["dpd"]()
    reneg     = _randi(0, 1) if dpd > 30 else 0
    refin     = _randi(0, 1) if dpd > 60 else 0

    meses_pago = _randi(1, max(prazo - 1, 1))
    saldo     = round(_saldo_devedor_atual(valor, taxa_am, prazo, meses_pago), 2)
    pmt       = round(_pmt(valor, taxa_am, prazo), 2)
    data_cont = _data_passada(meses_pago * 30)
    data_venc = data_cont + timedelta(days=prazo * 30)

    tipo_taxa = TipoTaxa.VARIAVEL if template.get("variavel", False) else TipoTaxa.FIXA

    return OperacaoCredito(
        id=op_id,
        associado_id=assoc_id,
        tipo=tipo_op,
        tipo_taxa=tipo_taxa,
        setor_risco=setor_op,
        valor_contratado_brl=valor,
        saldo_devedor_brl=saldo,
        taxa_juros_mensal_pct=taxa_am,
        prazo_meses=prazo,
        prazo_restante_meses=prazo - meses_pago,
        prestacao_mensal_brl=pmt,
        historico=HistoricoPagamento(
            operacao_id=op_id,
            dpd_atual=dpd,
            dpd_maximo_12m=max(dpd, _randi(0, dpd + 15)),
            ocorrencias_atraso_12m=_randi(0, max(1, dpd // 30)),
            renegociacoes=reneg,
            refinanciamentos=refin,
        ),
        garantias=_garantia_para_tipo(tipo_op, valor),
        data_contratacao=data_cont,
        data_vencimento=data_venc,
    )


# ─── Perfis de Operações por Segmento ────────────────────────────────────────

_TEMPLATES_AGRO_BOM = [
    {"tipo": TipoOperacao.AGRO_CUSTEIO,      "setor": SetorAtividade.AGRONEGOCIO,
     "taxa": (1.20, 1.80), "valor": (80_000, 400_000), "prazo": (12, 18),
     "dpd": lambda: 0, "variavel": False},
    {"tipo": TipoOperacao.AGRO_INVESTIMENTO, "setor": SetorAtividade.AGRONEGOCIO,
     "taxa": (0.95, 1.40), "valor": (150_000, 800_000), "prazo": (36, 84),
     "dpd": lambda: _randi(0, 5), "variavel": False},
    {"tipo": TipoOperacao.AGRO_CUSTEIO,      "setor": SetorAtividade.RURAL_FAMILIAR,
     "taxa": (1.10, 1.60), "valor": (15_000, 60_000), "prazo": (6, 12),
     "dpd": lambda: _randi(0, 10), "variavel": False},
]

_TEMPLATES_AGRO_MAU = [
    {"tipo": TipoOperacao.AGRO_CUSTEIO, "setor": SetorAtividade.AGRONEGOCIO,
     "taxa": (1.30, 2.00), "valor": (50_000, 250_000), "prazo": (12, 24),
     "dpd": lambda: _randi(60, 200), "variavel": False},
    {"tipo": TipoOperacao.AGRO_INVESTIMENTO, "setor": SetorAtividade.RURAL_FAMILIAR,
     "taxa": (1.20, 1.80), "valor": (30_000, 120_000), "prazo": (24, 60),
     "dpd": lambda: _randi(30, 120), "variavel": False},
]

_TEMPLATES_VAREJO_BOM = [
    {"tipo": TipoOperacao.CAPITAL_GIRO, "setor": SetorAtividade.COMERCIO,
     "taxa": (1.60, 2.20), "valor": (30_000, 200_000), "prazo": (12, 36),
     "dpd": lambda: 0, "variavel": True},
    {"tipo": TipoOperacao.CAPITAL_GIRO, "setor": SetorAtividade.INDUSTRIA,
     "taxa": (1.40, 1.90), "valor": (50_000, 350_000), "prazo": (12, 48),
     "dpd": lambda: _randi(0, 8), "variavel": True},
    {"tipo": TipoOperacao.CDC_PESSOAL,  "setor": SetorAtividade.COMERCIO,
     "taxa": (1.80, 2.50), "valor": (5_000, 40_000), "prazo": (12, 36),
     "dpd": lambda: 0, "variavel": False},
]

_TEMPLATES_VAREJO_MAU = [
    {"tipo": TipoOperacao.CAPITAL_GIRO,   "setor": SetorAtividade.COMERCIO,
     "taxa": (2.00, 2.80), "valor": (20_000, 100_000), "prazo": (12, 24),
     "dpd": lambda: _randi(45, 180), "variavel": True},
    {"tipo": TipoOperacao.CHEQUE_ESPECIAL, "setor": SetorAtividade.SERVICOS,
     "taxa": (3.50, 5.00), "valor": (2_000, 15_000),  "prazo": (1, 6),
     "dpd": lambda: _randi(30, 150), "variavel": True},
]

_TEMPLATES_PF_BOM = [
    {"tipo": TipoOperacao.CDC_PESSOAL,  "setor": SetorAtividade.FUNCIONALISMO,
     "taxa": (1.20, 1.70), "valor": (10_000, 80_000), "prazo": (24, 72),
     "dpd": lambda: 0, "variavel": False},
    {"tipo": TipoOperacao.CONSIGNADO,   "setor": SetorAtividade.FUNCIONALISMO,
     "taxa": (0.90, 1.30), "valor": (15_000, 100_000), "prazo": (36, 84),
     "dpd": lambda: 0, "variavel": False},
    {"tipo": TipoOperacao.CDC_PESSOAL,  "setor": SetorAtividade.SERVICOS,
     "taxa": (1.60, 2.20), "valor": (5_000, 30_000), "prazo": (12, 48),
     "dpd": lambda: _randi(0, 12), "variavel": False},
]

_TEMPLATES_PF_MAU = [
    {"tipo": TipoOperacao.CDC_PESSOAL,  "setor": SetorAtividade.SERVICOS,
     "taxa": (2.20, 3.50), "valor": (3_000, 20_000), "prazo": (12, 36),
     "dpd": lambda: _randi(30, 200), "variavel": False},
    {"tipo": TipoOperacao.CHEQUE_ESPECIAL, "setor": SetorAtividade.COMERCIO,
     "taxa": (4.00, 6.00), "valor": (1_000, 8_000),  "prazo": (1, 3),
     "dpd": lambda: _randi(60, 250), "variavel": True},
]

_TEMPLATES_IMOB = [
    {"tipo": TipoOperacao.IMOBILIARIO, "setor": SetorAtividade.FUNCIONALISMO,
     "taxa": (0.75, 1.10), "valor": (150_000, 600_000), "prazo": (120, 240),
     "dpd": lambda: 0, "variavel": False},
    {"tipo": TipoOperacao.IMOBILIARIO, "setor": SetorAtividade.COMERCIO,
     "taxa": (0.85, 1.20), "valor": (200_000, 900_000), "prazo": (120, 180),
     "dpd": lambda: _randi(0, 20), "variavel": False},
]


# ─── Montagem da Carteira ──────────────────────────────────────────────────────

def gerar_carteira_mock() -> Carteira:
    """
    Gera carteira realista com 100 operações e 60 associados.

    Distribuição de perfis de associado:
      excelente:   15 (25%)  — produtores rurais estabelecidos, servidores
      bom:         20 (33%)  — comerciantes, professores, técnicos
      regular:     13 (22%)  — pequenos negócios, autônomos
      fragil:       8 (13%)  — renda variável, baixo relacionamento
      inadimplente: 4  (7%)  — em espiral de dívida
    """
    associados: dict[str, Associado] = {}
    operacoes:  list[OperacaoCredito] = []

    # ── Gerar associados ──────────────────────────────────────────────────────
    perfis = (
        [("excelente", 15)] +
        [("bom",       20)] +
        [("regular",   13)] +
        [("fragil",     8)] +
        [("inadimplente", 4)]
    )
    assoc_list: list[tuple[str, str]] = []  # (id, perfil)
    i = 1
    for perfil, qtd in perfis:
        for _ in range(qtd):
            aid = f"ASC-{i:04d}"
            associados[aid] = _gerar_associado(aid, perfil)
            assoc_list.append((aid, perfil))
            i += 1

    # ── Gerar 100 operações distribuídas ──────────────────────────────────────
    op_idx = 1

    def _add_op(assoc_id: str, template: dict) -> None:
        nonlocal op_idx
        op_id = f"OP-{op_idx:04d}"
        operacoes.append(_gerar_operacao(op_id, assoc_id, template))
        op_idx += 1

    # Filtros de associados por perfil
    excelentes    = [a for a, p in assoc_list if p == "excelente"]
    bons          = [a for a, p in assoc_list if p == "bom"]
    regulares     = [a for a, p in assoc_list if p == "regular"]
    frageis       = [a for a, p in assoc_list if p == "fragil"]
    inadimplentes = [a for a, p in assoc_list if p == "inadimplente"]

    # Agro bom (18 ops) — associados excelentes e bons
    for _ in range(18):
        _add_op(_pick(excelentes + bons), _pick(_TEMPLATES_AGRO_BOM))

    # Agro problemático (8 ops) — regulares e frágeis
    for _ in range(8):
        _add_op(_pick(regulares + frageis + inadimplentes), _pick(_TEMPLATES_AGRO_MAU))

    # Varejo bom (18 ops)
    for _ in range(18):
        _add_op(_pick(excelentes + bons), _pick(_TEMPLATES_VAREJO_BOM))

    # Varejo problemático (10 ops)
    for _ in range(10):
        _add_op(_pick(regulares + frageis + inadimplentes), _pick(_TEMPLATES_VAREJO_MAU))

    # PF bom (17 ops)
    for _ in range(17):
        _add_op(_pick(excelentes + bons + regulares), _pick(_TEMPLATES_PF_BOM))

    # PF problemático (8 ops)
    for _ in range(8):
        _add_op(_pick(frageis + inadimplentes), _pick(_TEMPLATES_PF_MAU))

    # Imobiliário (10 ops — maioria boa, garantia forte)
    for _ in range(10):
        _add_op(_pick(excelentes + bons), _pick(_TEMPLATES_IMOB))

    # Operações extras para atingir 100 exatas
    while len(operacoes) < 100:
        _add_op(_pick(bons + regulares), _pick(_TEMPLATES_VAREJO_BOM))

    return Carteira(
        id="CART-2026-001",
        nome="Carteira Cooperativa — Posição Abr/2026",
        data_posicao=date.today(),
        associados=associados,
        operacoes=operacoes[:100],
    )
