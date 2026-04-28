import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { NetworkGraph } from './NetworkGraph'
import { KpiCard } from './KpiCard'
import { FilterPanel } from './FilterPanel'
import { useFleetGraph } from '../hooks/useFleetGraph'
import { DRIVERS, VEHICLES, INCIDENTS } from '../data/mockFleet'
import { computeKPIs, formatBRL, formatNumber } from '../utils/riskMetrics'
import type { FilterState } from '../types/fleet'

const INITIAL_FILTERS: FilterState = {
  riskLevel:   'all',
  vehicleType: 'all',
  region:      'all',
  dateRange:   ['2024-01-01', '2025-12-31'],
  searchTerm:  '',
}

const REGIONS = [...new Set(DRIVERS.map(d => d.region))].sort()

export const RiskDashboard = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [graphSize, setGraphSize]   = useState({ width: 900, height: 600 })
  const [filters, setFilters]       = useState<FilterState>(INITIAL_FILTERS)
  const [liveMode, setLiveMode]     = useState(false)
  const [tickCount, setTickCount]   = useState(0)

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setGraphSize({ width: Math.floor(width), height: Math.max(500, Math.floor(height)) })
    })
    obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  // Live mode: random incident injection every 2s
  useEffect(() => {
    if (!liveMode) return
    const timer = setInterval(() => setTickCount(c => c + 1), 2000)
    return () => clearInterval(timer)
  }, [liveMode])

  const mergeFilters = useCallback((partial: Partial<FilterState>) => {
    setFilters(prev => ({ ...prev, ...partial }))
  }, [])

  const graph = useFleetGraph(DRIVERS, VEHICLES, INCIDENTS, filters)

  const kpis = useMemo(() => computeKPIs(VEHICLES, DRIVERS, INCIDENTS), [])

  const graphKey = useMemo(
    () => `${filters.riskLevel}-${filters.vehicleType}-${filters.region}-${filters.searchTerm}-${tickCount}`,
    [filters, tickCount]
  )

  return (
    <div className="min-h-screen bg-surface-900 text-slate-100 flex flex-col font-[Inter,sans-serif]">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-surface-700 bg-surface-800">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse-slow" />
          <span className="font-semibold text-slate-200 tracking-tight">Atlas BI</span>
          <span className="text-slate-500">/</span>
          <span className="text-slate-400 text-sm">Inteligência de Risco · Frota</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">
            {graph.nodes.length} nós · {graph.links.length} conexões
          </span>
          <button
            onClick={() => setLiveMode(l => !l)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              liveMode
                ? 'bg-risk-critical/20 text-risk-critical border border-risk-critical/40'
                : 'bg-surface-700 text-slate-400 border border-surface-600 hover:text-slate-200'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${liveMode ? 'bg-risk-critical animate-pulse' : 'bg-slate-500'}`} />
            {liveMode ? 'LIVE' : 'Ativar Live'}
          </button>
          <div className="text-xs font-mono text-slate-500">
            {new Date().toLocaleDateString('pt-BR')}
          </div>
        </div>
      </header>

      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Sidebar */}
        <div className="p-4 shrink-0">
          <FilterPanel filters={filters} regions={REGIONS} onChange={mergeFilters} />
        </div>

        {/* Main content */}
        <main className="flex-1 flex flex-col gap-4 p-4 min-w-0 overflow-auto">
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
            <KpiCard
              label="Veículos Ativos"
              value={String(kpis.activeVehicles)}
              sub={`de ${kpis.totalVehicles} total`}
              accent="blue"
              icon="🚛"
            />
            <KpiCard
              label="Incidentes"
              value={String(kpis.totalIncidents)}
              sub={`${kpis.criticalIncidents} críticos`}
              accent="red"
              icon="⚠️"
            />
            <KpiCard
              label="Custo Total"
              value={formatBRL(kpis.totalCostBRL)}
              sub={`${formatBRL(kpis.costPerActiveVehicle)}/veículo`}
              accent="orange"
              icon="💸"
            />
            <KpiCard
              label="Acidentes / 1000 km"
              value={formatNumber(kpis.accidentRatePer1000km, 2)}
              sub="índice de exposição"
              accent={kpis.accidentRatePer1000km > 1 ? 'red' : 'green'}
              icon="📍"
            />
            <KpiCard
              label="Score Médio Risco"
              value={formatNumber(kpis.avgRiskScore, 0)}
              sub="escala 0–100"
              accent={kpis.avgRiskScore > 60 ? 'red' : kpis.avgRiskScore > 40 ? 'orange' : 'green'}
              icon="🎯"
            />
          </div>

          {/* Graph container */}
          <div
            ref={containerRef}
            className="flex-1 relative rounded-2xl border border-surface-700 overflow-hidden bg-surface-900"
            style={{ minHeight: 500 }}
          >
            {/* Graph title overlay */}
            <div className="absolute top-4 left-4 z-10 flex flex-col gap-1 pointer-events-none">
              <span className="text-xs uppercase text-slate-500 tracking-widest">Network Graph</span>
              <span className="text-slate-300 font-semibold text-sm">
                Correlações Motorista · Veículo · Rota
              </span>
            </div>

            {graph.nodes.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
                Nenhum incidente encontrado para os filtros selecionados.
              </div>
            ) : (
              <NetworkGraph
                key={graphKey}
                graph={graph}
                width={graphSize.width}
                height={graphSize.height}
              />
            )}
          </div>

          {/* Bottom info bar */}
          <div className="flex items-center justify-between text-xs text-slate-600 px-1">
            <span>Dataset: {INCIDENTS.length} incidentes · {VEHICLES.length} veículos · {DRIVERS.length} motoristas</span>
            <span>Powered by D3.js Force Simulation — impossível no Power BI nativo</span>
          </div>
        </main>
      </div>
    </div>
  )
}
