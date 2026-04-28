import { useMemo } from 'react'
import type { Associado, OperacaoCredito, Garantia, CreditGraph, GraphNode, GraphLink, FilterState } from '../types/credit'
const scoreInRange = (score: number, min: number) => score >= min

export const useCreditGraph = (
  associados: Associado[],
  operacoes: OperacaoCredito[],
  garantias: Garantia[],
  filters: FilterState,
): CreditGraph => {
  return useMemo(() => {
    // ── Filtragem ──────────────────────────────────────────────────────────
    const ops = operacoes.filter(op => {
      const assoc = associados.find(a => a.id === op.associado_id)
      if (filters.segmento !== 'all' && op.segmento !== filters.segmento) return false
      if (filters.nivelRisco !== 'all' && op.nivel_risco !== filters.nivelRisco) return false
      if (!scoreInRange(assoc?.score_cooperativo ?? 0, filters.scoreMin)) return false
      if (filters.searchTerm) {
        const t = filters.searchTerm.toLowerCase()
        if (!assoc?.nome.toLowerCase().includes(t) && !op.id.toLowerCase().includes(t)) return false
      }
      return true
    })

    const opIds    = new Set(ops.map(o => o.id))
    const assocIds = new Set(ops.map(o => o.associado_id))
    const garIds   = new Set(ops.map(o => o.garantia_id).filter(Boolean) as string[])

    // ── Nós ────────────────────────────────────────────────────────────────
    const assocNodes: GraphNode[] = associados
      .filter(a => assocIds.has(a.id))
      .map(a => ({
        id:         a.id,
        label:      a.nome.split(' ')[0],
        type:       'associado' as const,
        nivelRisco: 'AA' as const,         // cor do nó associado = score_coop
        value:      a.capital_integralizado,
        segmento:   undefined,
        meta: {
          nome:              a.nome,
          'Score Coop.':     a.score_cooperativo,
          'Capital Integr.': `R$ ${a.capital_integralizado.toLocaleString('pt-BR')}`,
          'Renda':           `R$ ${a.renda_mensal.toLocaleString('pt-BR')}/mês`,
          'Tempo Coop.':     `${a.anos_associado} anos`,
        },
      }))

    const opNodes: GraphNode[] = ops
      .slice(0, 60)   // cap para performance visual
      .map(op => ({
        id:         op.id,
        label:      op.id.replace('OP-',''),
        type:       'operacao' as const,
        nivelRisco: op.nivel_risco,
        value:      op.saldo_devedor,
        segmento:   op.segmento,
        meta: {
          Segmento:       op.segmento,
          'Saldo Devedor': `R$ ${op.saldo_devedor.toLocaleString('pt-BR')}`,
          'Dias Atraso':   op.dias_atraso,
          'Nível Risco':   op.nivel_risco,
          'Taxa':          `${op.taxa_mensal_pct}% a.m.`,
          'PCLD':          `R$ ${op.pcld.toLocaleString('pt-BR')}`,
        },
      }))

    const garNodes: GraphNode[] = garantias
      .filter(g => garIds.has(g.id) && opIds.has(g.operacao_id))
      .slice(0, 40)
      .map(g => ({
        id:         g.id,
        label:      g.tipo.replace('_',' '),
        type:       'garantia' as const,
        nivelRisco: 'AA' as const,
        value:      g.valor,
        meta: {
          Tipo:  g.tipo.replace('_',' '),
          Valor: `R$ ${g.valor.toLocaleString('pt-BR')}`,
          LTV:   g.ltv.toFixed(2),
        },
      }))

    const nodes = [...assocNodes, ...opNodes, ...garNodes]
    const nodeIds = new Set(nodes.map(n => n.id))

    // ── Arestas ────────────────────────────────────────────────────────────
    const links: GraphLink[] = []

    for (const op of ops.slice(0, 60)) {
      if (nodeIds.has(op.associado_id) && nodeIds.has(op.id)) {
        links.push({ source: op.associado_id, target: op.id, tipo: 'contrato' })
      }
      if (op.garantia_id && nodeIds.has(op.garantia_id) && nodeIds.has(op.id)) {
        links.push({ source: op.id, target: op.garantia_id, tipo: 'garantia' })
      }
    }

    return { nodes, links }
  }, [associados, operacoes, garantias, filters])
}
