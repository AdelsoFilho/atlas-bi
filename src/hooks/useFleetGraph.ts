import { useMemo } from 'react'
import type { Driver, Vehicle, Incident, FleetGraph, GraphNode, GraphLink, FilterState } from '../types/fleet'
import { ROUTES } from '../data/mockFleet'

export const useFleetGraph = (
  drivers: Driver[],
  vehicles: Vehicle[],
  incidents: Incident[],
  filters: FilterState,
): FleetGraph => {
  return useMemo(() => {
    // Apply filters
    const filteredIncidents = incidents.filter(inc => {
      const vehicle = vehicles.find(v => v.id === inc.vehicleId)
      const driver  = drivers.find(d => d.id === inc.driverId)
      if (filters.riskLevel !== 'all' && inc.severity !== filters.riskLevel) return false
      if (filters.vehicleType !== 'all' && vehicle?.type !== filters.vehicleType) return false
      if (filters.region !== 'all' && driver?.region !== filters.region) return false
      if (filters.searchTerm) {
        const term = filters.searchTerm.toLowerCase()
        if (
          !vehicle?.plate.toLowerCase().includes(term) &&
          !driver?.name.toLowerCase().includes(term)
        ) return false
      }
      return true
    })

    // Build incident frequency maps
    const driverIncCount  = new Map<string, number>()
    const vehicleIncCount = new Map<string, number>()
    const routeIncCount   = new Map<string, number>()

    for (const inc of filteredIncidents) {
      driverIncCount.set(inc.driverId,  (driverIncCount.get(inc.driverId)  ?? 0) + 1)
      vehicleIncCount.set(inc.vehicleId, (vehicleIncCount.get(inc.vehicleId) ?? 0) + 1)
      routeIncCount.set(inc.routeId,    (routeIncCount.get(inc.routeId)    ?? 0) + 1)
    }

    // Only include entities with at least 1 incident (keeps graph readable)
    const involvedDriverIds  = new Set(filteredIncidents.map(i => i.driverId))
    const involvedVehicleIds = new Set(filteredIncidents.map(i => i.vehicleId))
    const involvedRouteIds   = new Set(filteredIncidents.map(i => i.routeId))

    const nodes: GraphNode[] = [
      ...drivers
        .filter(d => involvedDriverIds.has(d.id))
        .slice(0, 20)
        .map(d => ({
          id:        d.id,
          label:     d.name.split(' ')[0],
          type:      'driver' as const,
          riskScore: d.riskScore,
        })),
      ...vehicles
        .filter(v => involvedVehicleIds.has(v.id))
        .slice(0, 20)
        .map(v => ({
          id:        v.id,
          label:     v.plate,
          type:      'vehicle' as const,
          riskScore: v.riskScore,
        })),
      ...ROUTES
        .filter(r => involvedRouteIds.has(r.id))
        .slice(0, 10)
        .map(r => ({
          id:        r.id,
          label:     r.name,
          type:      'route' as const,
          riskScore: r.incidentCount * 4,
        })),
    ]

    const nodeIds = new Set(nodes.map(n => n.id))

    // Build links: driver→vehicle, vehicle→route (weighted by incident count)
    const linkMap = new Map<string, GraphLink>()

    for (const inc of filteredIncidents) {
      if (!nodeIds.has(inc.driverId) || !nodeIds.has(inc.vehicleId)) continue

      const dvKey = `${inc.driverId}::${inc.vehicleId}`
      if (!linkMap.has(dvKey)) {
        linkMap.set(dvKey, { source: inc.driverId, target: inc.vehicleId, weight: 0, riskLevel: inc.severity })
      }
      const dvLink = linkMap.get(dvKey)!
      dvLink.weight++

      if (!nodeIds.has(inc.routeId)) continue
      const vrKey = `${inc.vehicleId}::${inc.routeId}`
      if (!linkMap.has(vrKey)) {
        linkMap.set(vrKey, { source: inc.vehicleId, target: inc.routeId, weight: 0, riskLevel: inc.severity })
      }
      linkMap.get(vrKey)!.weight++
    }

    return { nodes, links: Array.from(linkMap.values()) }
  }, [drivers, vehicles, incidents, filters])
}
