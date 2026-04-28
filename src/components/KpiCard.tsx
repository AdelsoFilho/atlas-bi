interface Props {
  label: string
  value: string
  sub?: string
  accent?: 'red' | 'orange' | 'green' | 'blue' | 'default'
  icon?: string
}

const accentMap = {
  red:     'border-risk-critical text-risk-critical',
  orange:  'border-risk-high text-risk-high',
  green:   'border-risk-low text-risk-low',
  blue:    'border-risk-none text-risk-none',
  default: 'border-surface-600 text-slate-200',
}

export const KpiCard = ({ label, value, sub, accent = 'default', icon }: Props) => (
  <div className={`rounded-xl border bg-surface-800 p-4 flex flex-col gap-1 border-l-4 animate-fade-in ${accentMap[accent]}`}>
    <div className="flex items-center gap-2 text-xs text-slate-400 uppercase tracking-wider font-medium">
      {icon && <span>{icon}</span>}
      {label}
    </div>
    <div className="text-2xl font-bold font-mono">{value}</div>
    {sub && <div className="text-xs text-slate-500">{sub}</div>}
  </div>
)
