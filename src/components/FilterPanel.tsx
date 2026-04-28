import type { FilterState, RiskLevel } from '../types/fleet'

interface Props {
  filters: FilterState
  regions: string[]
  onChange: (f: Partial<FilterState>) => void
}

const RISK_LEVELS: { value: RiskLevel | 'all'; label: string; color: string }[] = [
  { value: 'all',      label: 'Todos',    color: '#64748b' },
  { value: 'critical', label: 'Crítico',  color: '#ef4444' },
  { value: 'high',     label: 'Alto',     color: '#f97316' },
  { value: 'medium',   label: 'Médio',    color: '#eab308' },
  { value: 'low',      label: 'Baixo',    color: '#22c55e' },
  { value: 'none',     label: 'Nenhum',   color: '#3b82f6' },
]

const VEHICLE_TYPES = [
  { value: 'all',        label: 'Todos' },
  { value: 'truck',      label: 'Caminhão' },
  { value: 'van',        label: 'Van' },
  { value: 'car',        label: 'Carro' },
  { value: 'motorcycle', label: 'Moto' },
] as const

export const FilterPanel = ({ filters, regions, onChange }: Props) => (
  <aside className="w-64 shrink-0 flex flex-col gap-5 bg-surface-800 rounded-2xl p-5 border border-surface-600 h-fit">
    <div>
      <h3 className="text-xs uppercase text-slate-400 tracking-widest mb-1 font-semibold">Atlas BI</h3>
      <p className="text-slate-200 font-bold text-lg leading-tight">Risco de Frota</p>
      <div className="h-px bg-surface-600 mt-3" />
    </div>

    {/* Search */}
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Busca</label>
      <input
        type="text"
        placeholder="Placa ou motorista..."
        value={filters.searchTerm}
        onChange={e => onChange({ searchTerm: e.target.value })}
        className="bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
      />
    </div>

    {/* Risk Level */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Nível de Risco</label>
      <div className="flex flex-col gap-1">
        {RISK_LEVELS.map(r => (
          <button
            key={r.value}
            onClick={() => onChange({ riskLevel: r.value })}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all text-left ${
              filters.riskLevel === r.value
                ? 'bg-surface-600 text-slate-100'
                : 'text-slate-400 hover:bg-surface-700'
            }`}
          >
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: r.color }} />
            {r.label}
          </button>
        ))}
      </div>
    </div>

    {/* Vehicle Type */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Tipo de Veículo</label>
      <select
        value={filters.vehicleType}
        onChange={e => onChange({ vehicleType: e.target.value as FilterState['vehicleType'] })}
        className="bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
      >
        {VEHICLE_TYPES.map(t => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>
    </div>

    {/* Region */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Região</label>
      <select
        value={filters.region}
        onChange={e => onChange({ region: e.target.value })}
        className="bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
      >
        <option value="all">Todas</option>
        {regions.map(r => <option key={r} value={r}>{r}</option>)}
      </select>
    </div>

    <div className="h-px bg-surface-600" />

    {/* Legend */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Legenda — Nós</label>
      {[
        { color: '#818cf8', label: 'Motorista' },
        { color: '#38bdf8', label: 'Veículo' },
        { color: '#fb923c', label: 'Rota' },
      ].map(l => (
        <div key={l.label} className="flex items-center gap-2 text-xs text-slate-400">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: l.color }} />
          {l.label}
        </div>
      ))}
    </div>

    <div className="mt-auto text-xs text-slate-600 text-center">
      Arraste nós · Scroll para zoom
    </div>
  </aside>
)
