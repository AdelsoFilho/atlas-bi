import type { NivelRisco, OperacaoCredito, Associado, Garantia, CreditKPIs } from '../types/credit'

export const PCLD_PCT: Record<NivelRisco, number> = {
  AA: 0, A: 0.5, B: 1, C: 3, D: 10, E: 30, F: 50, G: 70, H: 100,
}

// Pesos de RWA por nível (simplificado — Basileia II cooperativas)
const RWA_WEIGHT: Record<NivelRisco, number> = {
  AA: 0.20, A: 0.50, B: 0.75, C: 1.00,
  D: 1.50,  E: 2.00, F: 3.00, G: 4.00, H: 5.00,
}

export const nivelColor = (n: NivelRisco): string => ({
  AA: '#22c55e', A: '#4ade80', B: '#a3e635', C: '#eab308',
  D:  '#f97316', E: '#fb923c', F: '#ef4444', G: '#dc2626', H: '#7f1d1d',
})[n]

export const nivelFromDPD = (dpd: number, renegs = 0): NivelRisco => {
  let base: NivelRisco =
    dpd === 0   ? 'AA' :
    dpd <= 14   ? 'A'  :
    dpd <= 30   ? 'B'  :
    dpd <= 60   ? 'C'  :
    dpd <= 90   ? 'D'  :
    dpd <= 120  ? 'E'  :
    dpd <= 150  ? 'F'  :
    dpd <= 180  ? 'G'  : 'H'

  const ordem: NivelRisco[] = ['AA','A','B','C','D','E','F','G','H']
  let idx = ordem.indexOf(base)
  if (renegs >= 2) idx = Math.min(idx + 1, 8)
  return ordem[idx]
}

export const calcPCLD = (ops: OperacaoCredito[]): number =>
  ops.reduce((s, op) => s + op.saldo_devedor * PCLD_PCT[op.nivel_risco] / 100, 0)

export const calcBasileia = (ops: OperacaoCredito[], capitalProprio: number): number => {
  const rwa = ops.reduce((s, op) => s + op.saldo_devedor * RWA_WEIGHT[op.nivel_risco], 0)
  return rwa === 0 ? 0 : (capitalProprio / rwa) * 100
}

export const computeKPIs = (
  ops: OperacaoCredito[],
  assocs: Associado[],
  garantias: Garantia[],
): CreditKPIs => {
  const carteira_total   = ops.reduce((s, o) => s + o.saldo_devedor, 0)
  const pcld_total       = calcPCLD(ops)
  const default90        = ops.filter(o => o.dias_atraso > 90)
  const nivelDH          = ops.filter(o => ['D','E','F','G','H'].includes(o.nivel_risco))
  const totalGarantias   = garantias.reduce((s, g) => s + g.valor, 0)
  const capitalProprio   = carteira_total * 0.13   // ~13% simulado
  return {
    carteira_total,
    operacoes_default:       default90.length,
    pcld_total,
    indice_basileia:         calcBasileia(ops, capitalProprio),
    npl_pct:                 nivelDH.reduce((s,o) => s + o.saldo_devedor, 0) / Math.max(carteira_total, 1) * 100,
    total_operacoes:         ops.length,
    total_associados:        assocs.length,
    cobertura_garantias_pct: totalGarantias / Math.max(carteira_total, 1) * 100,
  }
}

export const fmtBRL = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)

export const fmtBRLShort = (v: number): string => {
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000)     return `R$ ${(v / 1_000).toFixed(0)}k`
  return fmtBRL(v)
}

export const fmtNum = (v: number, d = 1) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }).format(v)
