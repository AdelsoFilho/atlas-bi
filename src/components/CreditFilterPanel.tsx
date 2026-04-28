import type { FilterState, NivelRisco, Segmento } from '../types/credit'

interface Props {
  filters: FilterState
  onChange: (f: Partial<FilterState>) => void
  totals: { nodes: number; links: number }
}

const NIVEIS: { value: NivelRisco | 'all'; label: string; color: string }[] = [
  { value: 'all', label: 'Todos', color: '#64748b' },
  { value: 'AA',  label: 'AA — Mínimo',  color: '#22c55e' },
  { value: 'A',   label: 'A  — Muito Baixo', color: '#4ade80' },
  { value: 'B',   label: 'B  — Baixo',    color: '#a3e635' },
  { value: 'C',   label: 'C  — Médio',    color: '#eab308' },
  { value: 'D',   label: 'D  — Alto',     color: '#f97316' },
  { value: 'E',   label: 'E  — Muito Alto', color: '#fb923c' },
  { value: 'F',   label: 'F  — Crítico',  color: '#ef4444' },
  { value: 'G',   label: 'G  — Grave',    color: '#dc2626' },
  { value: 'H',   label: 'H  — Perda',    color: '#7f1d1d' },
]

const SEGMENTOS: { value: Segmento | 'all'; label: string }[] = [
  { value: 'all',         label: 'Todos os Segmentos' },
  { value: 'agro',        label: 'Agronegócio' },
  { value: 'varejo',      label: 'Varejo / Comércio' },
  { value: 'imobiliario', label: 'Imobiliário' },
  { value: 'pessoal',     label: 'Crédito Pessoal' },
  { value: 'consignado',  label: 'Consignado' },
]

const SCORE_FAIXAS = [
  { value: 0,   label: 'Todos os scores' },
  { value: 300, label: '≥ 300' },
  { value: 500, label: '≥ 500 (Regular)' },
  { value: 650, label: '≥ 650 (Bom)' },
  { value: 750, label: '≥ 750 (Excelente)' },
]

export const CreditFilterPanel = ({ filters, onChange, totals }: Props) => (
  <aside className="w-64 shrink-0 flex flex-col gap-5 bg-surface-800 rounded-2xl p-5 border border-surface-600 h-fit">
    {/* Header */}
    <div>
      <h3 className="text-xs uppercase text-slate-400 tracking-widest mb-1 font-semibold">Atlas BI</h3>
      <p className="text-slate-200 font-bold text-lg leading-tight">Carteira de Crédito</p>
      <p className="text-xs text-slate-500 mt-1">Exposição & Risco Cooperativo</p>
      <div className="h-px bg-surface-600 mt-3" />
    </div>

    {/* Busca */}
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Buscar Associado / Op.</label>
      <input
        type="text"
        placeholder="Nome ou ID da operação..."
        value={filters.searchTerm}
        onChange={e => onChange({ searchTerm: e.target.value })}
        className="bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
      />
    </div>

    {/* Segmento */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Segmento</label>
      <div className="flex flex-col gap-1">
        {SEGMENTOS.map(s => (
          <button key={s.value} onClick={() => onChange({ segmento: s.value })}
            className={`px-3 py-1.5 rounded-lg text-xs text-left transition-all ${
              filters.segmento === s.value
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                : 'text-slate-400 hover:bg-surface-700'
            }`}>
            {s.label}
          </button>
        ))}
      </div>
    </div>

    <div className="h-px bg-surface-600" />

    {/* Nível de Risco BCB */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Classificação BCB</label>
      <div className="flex flex-col gap-0.5 max-h-52 overflow-y-auto">
        {NIVEIS.map(n => (
          <button key={n.value} onClick={() => onChange({ nivelRisco: n.value })}
            className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-all text-left ${
              filters.nivelRisco === n.value ? 'bg-surface-600 text-slate-100' : 'text-slate-400 hover:bg-surface-700'
            }`}>
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: n.color }} />
            {n.label}
          </button>
        ))}
      </div>
    </div>

    <div className="h-px bg-surface-600" />

    {/* Score Cooperativo */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Score Cooperativo Mín.</label>
      <select value={filters.scoreMin} onChange={e => onChange({ scoreMin: Number(e.target.value) })}
        className="bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors">
        {SCORE_FAIXAS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
      </select>
    </div>

    <div className="h-px bg-surface-600" />

    {/* Legenda */}
    <div className="flex flex-col gap-2">
      <label className="text-xs text-slate-400 uppercase tracking-wider">Legenda — Nós</label>
      {[
        { color: '#818cf8', label: 'Associado (CPF/CNPJ)' },
        { color: '#38bdf8', label: 'Operação de Crédito' },
        { color: '#fb923c', label: 'Garantia / Colateral' },
      ].map(l => (
        <div key={l.label} className="flex items-center gap-2 text-xs text-slate-400">
          <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: l.color }} />
          {l.label}
        </div>
      ))}
      <div className="mt-1 flex flex-col gap-1">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="w-8 border-t border-indigo-500/60" /> Contrato
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="w-8 border-t border-dashed border-amber-500/60" /> Garantia
        </div>
      </div>
    </div>

    <div className="mt-auto text-center">
      <div className="text-xs text-slate-500 font-mono">
        {totals.nodes} nós · {totals.links} conexões
      </div>
      <div className="text-xs text-slate-600 mt-1">Scroll p/ zoom · Arraste nós</div>
    </div>
  </aside>
)
