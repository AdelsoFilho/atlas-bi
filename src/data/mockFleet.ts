import type { Driver, Vehicle, Incident, Route, RiskLevel } from '../types/fleet'

// ─── Seed helpers ────────────────────────────────────────────────────────────
const seed = (n: number) => {
  let s = n
  return () => { s = (s * 16807 + 0) % 2147483647; return (s - 1) / 2147483646 }
}
const rng = seed(42)
const rand  = (min: number, max: number) => Math.floor(rng() * (max - min + 1)) + min
const pick  = <T>(arr: T[]): T => arr[rand(0, arr.length - 1)]
const fmtDate = (daysAgo: number): string => {
  const d = new Date(); d.setDate(d.getDate() - daysAgo)
  return d.toISOString().split('T')[0]
}

// ─── Reference data ──────────────────────────────────────────────────────────
const REGIONS:   string[]         = ['Sul', 'Sudeste', 'Centro-Oeste', 'Nordeste', 'Norte']
const MODELS:    string[]         = ['Volvo FH 460', 'Scania R 450', 'Mercedes Actros', 'DAF XF', 'Ford Cargo', 'Iveco Tector', 'Fiat Ducato', 'Sprinter']
const VH_TYPES:  Vehicle['type'][]  = ['truck', 'van', 'car', 'motorcycle']
const INC_TYPES: Incident['type'][] = ['accident', 'breakdown', 'fine', 'near_miss', 'theft']
const SEVERITY:  RiskLevel[]        = ['critical', 'high', 'medium', 'low', 'none']
const FIRST     = ['Carlos','Ana','José','Maria','Pedro','Fernanda','Lucas','Juliana','Roberto','Camila']
const LAST      = ['Silva','Santos','Oliveira','Souza','Pereira','Costa','Ferreira','Alves','Rocha','Lima']

// ─── Routes (15) ─────────────────────────────────────────────────────────────
export const ROUTES: Route[] = Array.from({ length: 15 }, (_, i) => ({
  id:          `R${String(i + 1).padStart(3, '0')}`,
  name:        `Rota ${i + 1}`,
  originCity:  pick(['São Paulo', 'Rio de Janeiro', 'Curitiba', 'Porto Alegre', 'Belo Horizonte', 'Salvador', 'Recife', 'Manaus']),
  destCity:    pick(['Brasília', 'Goiânia', 'Campo Grande', 'Cuiabá', 'Belém', 'Fortaleza', 'Natal', 'Florianópolis']),
  distanceKm:  rand(80, 1800),
  riskLevel:   pick(SEVERITY),
  avgSpeedKmh: rand(55, 95),
  incidentCount: rand(0, 22),
}))

// ─── Drivers (50) ────────────────────────────────────────────────────────────
export const DRIVERS: Driver[] = Array.from({ length: 50 }, (_, i) => ({
  id:               `D${String(i + 1).padStart(3, '0')}`,
  name:             `${pick(FIRST)} ${pick(LAST)}`,
  license:          `${rand(10000000, 99999999)}`,
  age:              rand(24, 58),
  experienceYears:  rand(1, 25),
  riskScore:        rand(5, 98),
  accidentsLast12m: rand(0, 4),
  region:           pick(REGIONS),
}))

// ─── Vehicles (80) ───────────────────────────────────────────────────────────
export const VEHICLES: Vehicle[] = Array.from({ length: 80 }, (_, i) => {
  const driver = DRIVERS[i % DRIVERS.length]
  const status = rng() > 0.15 ? (rng() > 0.12 ? 'active' : 'maintenance') : 'inactive'
  return {
    id:                 `V${String(i + 1).padStart(3, '0')}`,
    plate:              `${pick(['ABC','DEF','GHI','JKL','MNO'])}-${rand(1000, 9999)}`,
    model:              pick(MODELS),
    year:               rand(2015, 2024),
    type:               pick(VH_TYPES),
    status,
    kmTotal:            rand(12000, 980000),
    monthlyCostBRL:     rand(4500, 28000),
    lastMaintenanceDate: fmtDate(rand(1, 180)),
    assignedDriverId:   driver.id,
    riskScore:          Math.round((driver.riskScore * 0.6) + rand(0, 40) * 0.4),
  }
})

// ─── Incidents (500) ─────────────────────────────────────────────────────────
const SEVERITY_COSTS: Record<RiskLevel, [number, number]> = {
  critical: [25000, 180000],
  high:     [8000,  24999],
  medium:   [1500,  7999],
  low:      [200,   1499],
  none:     [50,    199],
}

export const INCIDENTS: Incident[] = Array.from({ length: 500 }, (_, i) => {
  const severity = pick(SEVERITY)
  const [min, max] = SEVERITY_COSTS[severity]
  const vehicle    = pick(VEHICLES)
  const driver     = DRIVERS.find(d => d.id === vehicle.assignedDriverId) ?? pick(DRIVERS)
  const route      = pick(ROUTES)
  return {
    id:          `I${String(i + 1).padStart(4, '0')}`,
    date:        fmtDate(rand(0, 365)),
    type:        pick(INC_TYPES),
    severity,
    vehicleId:   vehicle.id,
    driverId:    driver.id,
    routeId:     route.id,
    costBRL:     rand(min, max),
    description: `Ocorrência tipo ${pick(INC_TYPES)} na ${route.name} — gravidade ${severity}`,
    kmAtEvent:   rand(1000, vehicle.kmTotal),
  }
})
