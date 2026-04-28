import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { CreditNetworkGraph } from './CreditNetworkGraph'
import { CreditFilterPanel } from './CreditFilterPanel'
import { KpiCard } from './KpiCard'
import { useCreditGraph } from '../hooks/useCreditGraph'
import { ASSOCIADOS, OPERACOES, GARANTIAS } from '../data/mockCredit'
import { computeKPIs, fmtBRLShort, fmtNum } from '../utils/creditMetrics'
import type { FilterState, NivelRisco } from '../types/credit'

const INITIAL_FILTERS: FilterState = {
  segmento:   'all',
  nivelRisco: 'all',
  scoreMin:   0,
  searchTerm: '',
}

// Barra de distribuição de risco por nível
const NIVEL_COLORS: Record<NivelRisco, string> = {
  AA: '#22c55e', A: '#4ade80', B: '#a3e635', C: '#eab308',
  D:  '#f97316', E: '#fb923c', F: '#ef4444', G: '#dc2626', H: '#7f1d1d',
}

export const CreditDashboard = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [graphSize, setGraphSize] = useState({ width: 900, height: 600 })
  const [filters, setFilters]     = useState<FilterState>(INITIAL_FILTERS)

  useEffect(() => {
    if (!containerRef.current) return
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setGraphSize({ width: Math.floor(width), height: Math.max(500, Math.floor(height)) })
    })
    obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  const mergeFilters = useCallback((p: Partial<FilterState>) => {
    setFilters(prev => ({ ...prev, ...p }))
  }, [])

  const graph = useCreditGraph(ASSOCIADOS, OPERACOES, GARANTIAS, filters)

  const kpis = useMemo(() => computeKPIs(OPERACOES, ASSOCIADOS, GARANTIAS), [])

  const graphKey = useMemo(
    () => `${filters.segmento}-${filters.nivelRisco}-${filters.scoreMin}-${filters.searchTerm}`,
    [filters]
  )

  // Distribuição por nível para a barra visual
  const distribuicao = useMemo(() => {
    const totSaldo = OPERACOES.reduce((s, o) => s + o.saldo_devedor, 0)
    const niveis = ['AA','A','B','C','D','E','F','G','H'] as NivelRisco[]
    return niveis.map(n => {
      const saldo = OPERACOES.filter(o => o.nivel_risco === n).reduce((s,o) => s+o.saldo_devedor, 0)
      return { nivel: n, pct: totSaldo > 0 ? saldo/totSaldo*100 : 0 }
    }).filter(d => d.pct > 0)
  }, [])

  const basileia_ok = kpis.indice_basileia >= 10.5  // Exigência BCB mínima

  return (
    <div className="min-h-screen bg-surface-900 text-slate-100 flex flex-col font-[Inter,sans-serif]">
      {/* Topbar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-surface-700 bg-surface-800">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse-slow" />
          <span className="font-semibold text-slate-200 tracking-tight">Atlas BI</span>
          <span className="text-slate-500">/</span>
          <span className="text-slate-400 text-sm">Carteira de Crédito & Exposição de Risco</span>
        </div>
        <div className="flex items-center gap-4">
          {/* Barra de distribuição de risco */}
          <div className="hidden md:flex items-center gap-1.5">
            <span className="text-xs text-slate-500 mr-1">Carteira:</span>
            <div className="flex h-4 w-48 rounded overflow-hidden">
              {distribuicao.map(d => (
                <div key={d.nivel} title={`${d.nivel}: ${d.pct.toFixed(1)}%`}
                  style={{ width: `${d.pct}%`, backgroundColor: NIVEL_COLORS[d.nivel] }} />
              ))}
            </div>
          </div>
          <div className="text-xs font-mono text-slate-500">
            {new Date().toLocaleDateString('pt-BR')}
          </div>
        </div>
      </header>

      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Sidebar */}
        <div className="p-4 shrink-0">
          <CreditFilterPanel
            filters={filters}
            onChange={mergeFilters}
            totals={{ nodes: graph.nodes.length, links: graph.links.length }}
          />
        </div>

        {/* Main */}
        <main className="flex-1 flex flex-col gap-4 p-4 min-w-0 overflow-auto">
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard
              label="Carteira Ativa Total"
              value={fmtBRLShort(kpis.carteira_total)}
              sub={`${kpis.total_operacoes} ops · ${kpis.total_associados} associados`}
              accent="blue"
              icon="🏦"
            />
            <KpiCard
              label="Operações em Default (>90d)"
              value={String(kpis.operacoes_default)}
              sub={`NPL D–H: ${fmtNum(kpis.npl_pct)}% da carteira`}
              accent={kpis.npl_pct > 5 ? 'red' : kpis.npl_pct > 3 ? 'orange' : 'green'}
              icon="⚠️"
            />
            <KpiCard
              label="Provisão PCLD Exigida"
              value={fmtBRLShort(kpis.pcld_total)}
              sub={`${fmtNum(kpis.pcld_total / kpis.carteira_total * 100)}% do saldo`}
              accent={kpis.pcld_total / kpis.carteira_total > 0.08 ? 'red' : 'orange'}
              icon="📋"
            />
            <KpiCard
              label="Índice de Basileia"
              value={`${fmtNum(kpis.indice_basileia)}%`}
              sub={basileia_ok ? 'Acima do mínimo BCB (10,5%)' : 'ABAIXO do mínimo BCB'}
              accent={basileia_ok ? 'green' : 'red'}
              icon="⚖️"
            />
          </div>

          {/* Grafo */}
          <div ref={containerRef}
            className="flex-1 relative rounded-2xl border border-surface-700 overflow-hidden bg-surface-900"
            style={{ minHeight: 500 }}>
            {/* Overlay de título */}
            <div className="absolute top-4 left-4 z-10 pointer-events-none">
              <span className="text-xs uppercase text-slate-500 tracking-widest">Network Graph</span>
              <p className="text-slate-300 font-semibold text-sm">
                Rede de Exposição: Associado → Operação → Garantia
              </p>
            </div>

            {/* Legenda de risco no canto */}
            <div className="absolute top-4 right-4 z-10 pointer-events-none flex flex-col gap-1">
              <span className="text-xs text-slate-500 uppercase tracking-widest mb-1">Risco Operação</span>
              {(['AA','C','F','H'] as NivelRisco[]).map(n => (
                <div key={n} className="flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: NIVEL_COLORS[n] }} />
                  {n} — {n === 'AA' ? 'Baixíssimo' : n === 'C' ? 'Médio' : n === 'F' ? 'Crítico' : 'Perda Total'}
                </div>
              ))}
            </div>

            {graph.nodes.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
                Nenhuma operação encontrada para os filtros selecionados.
              </div>
            ) : (
              <CreditNetworkGraph
                key={graphKey}
                graph={graph}
                width={graphSize.width}
                height={graphSize.height}
              />
            )}
          </div>

          {/* Rodapé informativo */}
          <div className="flex items-center justify-between text-xs text-slate-600 px-1">
            <span>
              Base: {OPERACOES.length} operações · {ASSOCIADOS.length} associados · {GARANTIAS.length} garantias
              · Selic 14,75% a.a.
            </span>
            <span>Res. CMN 2.682/99 · DRO 5050 S3 · Basileia II Cooperativas</span>
          </div>
        </main>
      </div>
    </div>
  )
}
