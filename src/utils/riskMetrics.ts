import type { Driver, Vehicle, Incident, FleetKPIs, RiskLevel } from '../types/fleet'

// DAX: DIVIDE(num, den, 0) → pure TS equivalent
export const safeDivide = (num: number, den: number, fallback = 0): number =>
  den === 0 ? fallback : num / den

// DAX: [Índice Acidentes KM] = DIVIDE([Total Acidentes], [Total KM], 0) * 1000
export const accidentRatePer1000km = (incidents: Incident[], vehicles: Vehicle[]): number => {
  const totalKm = vehicles.reduce((s, v) => s + v.kmTotal, 0)
  const accidents = incidents.filter(i => i.type === 'accident').length
  return safeDivide(accidents, totalKm) * 1000
}

// DAX: [Custo por Veículo Ativo] = DIVIDE([Custo Total], COUNTROWS(FILTER(Veiculos, Status="Ativo")))
export const costPerActiveVehicle = (vehicles: Vehicle[]): number => {
  const active = vehicles.filter(v => v.status === 'active')
  const total = active.reduce((s, v) => s + v.monthlyCostBRL, 0)
  return safeDivide(total, active.length)
}

// DAX: [Score Médio Risco] = AVERAGEX(Motoristas, Motoristas[RiskScore])
export const avgRiskScore = (drivers: Driver[]): number =>
  safeDivide(drivers.reduce((s, d) => s + d.riskScore, 0), drivers.length)

export const riskLevelFromScore = (score: number): RiskLevel => {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 40) return 'medium'
  if (score >= 20) return 'low'
  return 'none'
}

export const riskColor = (level: RiskLevel): string => {
  const map: Record<RiskLevel, string> = {
    critical: '#ef4444',
    high:     '#f97316',
    medium:   '#eab308',
    low:      '#22c55e',
    none:     '#3b82f6',
  }
  return map[level]
}

export const riskColorHex = (score: number): string =>
  riskColor(riskLevelFromScore(score))

export const computeKPIs = (
  vehicles: Vehicle[],
  drivers: Driver[],
  incidents: Incident[],
): FleetKPIs => {
  const active = vehicles.filter(v => v.status === 'active')
  return {
    totalVehicles:           vehicles.length,
    activeVehicles:          active.length,
    totalDrivers:            drivers.length,
    totalIncidents:          incidents.length,
    totalCostBRL:            incidents.reduce((s, i) => s + i.costBRL, 0),
    avgRiskScore:            avgRiskScore(drivers),
    accidentRatePer1000km:   accidentRatePer1000km(incidents, vehicles),
    costPerActiveVehicle:    costPerActiveVehicle(vehicles),
    criticalIncidents:       incidents.filter(i => i.severity === 'critical').length,
    maintenancePending:      vehicles.filter(v => v.status === 'maintenance').length,
  }
}

export const formatBRL = (value: number): string =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value)

export const formatNumber = (value: number, decimals = 1): string =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value)
