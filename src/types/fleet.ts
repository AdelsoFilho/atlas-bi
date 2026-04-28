export type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'none'

export interface Driver {
  id: string
  name: string
  license: string
  age: number
  experienceYears: number
  riskScore: number        // 0–100
  accidentsLast12m: number
  region: string
}

export interface Vehicle {
  id: string
  plate: string
  model: string
  year: number
  type: 'truck' | 'van' | 'car' | 'motorcycle'
  status: 'active' | 'maintenance' | 'inactive'
  kmTotal: number
  monthlyCostBRL: number
  lastMaintenanceDate: string
  assignedDriverId: string
  riskScore: number
}

export interface Route {
  id: string
  name: string
  originCity: string
  destCity: string
  distanceKm: number
  riskLevel: RiskLevel
  avgSpeedKmh: number
  incidentCount: number
}

export interface Incident {
  id: string
  date: string
  type: 'accident' | 'breakdown' | 'fine' | 'near_miss' | 'theft'
  severity: RiskLevel
  vehicleId: string
  driverId: string
  routeId: string
  costBRL: number
  description: string
  kmAtEvent: number
}

// Network Graph types
export interface GraphNode {
  id: string
  label: string
  type: 'driver' | 'vehicle' | 'route'
  riskScore: number
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

export interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  weight: number          // incident count between the two nodes
  riskLevel: RiskLevel
}

export interface FleetGraph {
  nodes: GraphNode[]
  links: GraphLink[]
}

// Aggregated KPIs — equiv. to DAX measures
export interface FleetKPIs {
  totalVehicles: number
  activeVehicles: number
  totalDrivers: number
  totalIncidents: number
  totalCostBRL: number
  avgRiskScore: number
  accidentRatePer1000km: number
  costPerActiveVehicle: number
  criticalIncidents: number
  maintenancePending: number
}

export interface FilterState {
  riskLevel: RiskLevel | 'all'
  vehicleType: Vehicle['type'] | 'all'
  region: string | 'all'
  dateRange: [string, string]
  searchTerm: string
}
