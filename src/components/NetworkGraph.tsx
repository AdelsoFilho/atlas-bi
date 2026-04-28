import { useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'
import type { FleetGraph, GraphNode, GraphLink, RiskLevel } from '../types/fleet'
import { riskColor, riskLevelFromScore } from '../utils/riskMetrics'

interface Props {
  graph: FleetGraph
  width: number
  height: number
}

const NODE_RADIUS: Record<GraphNode['type'], number> = { driver: 10, vehicle: 14, route: 18 }
const NODE_COLOR:  Record<GraphNode['type'], string>  = { driver: '#818cf8', vehicle: '#38bdf8', route: '#fb923c' }

const linkStroke = (level: RiskLevel) => riskColor(level)

export const NetworkGraph = ({ graph, width, height }: Props) => {
  const svgRef  = useRef<SVGSVGElement>(null)
  const simRef  = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null)

  const draw = useCallback(() => {
    const svg = d3.select(svgRef.current!)
    svg.selectAll('*').remove()

    const { nodes, links } = graph

    // Clone to avoid mutating hook output
    const nodesCopy: GraphNode[] = nodes.map(n => ({ ...n }))
    const linksCopy = links.map(l => ({
      ...l,
      source: typeof l.source === 'string' ? l.source : (l.source as GraphNode).id,
      target: typeof l.target === 'string' ? l.target : (l.target as GraphNode).id,
    }))

    // ── Defs: glow filter ──────────────────────────────────────────────────
    const defs = svg.append('defs')
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur')
    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode').attr('in', 'coloredBlur')
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // ── Container with zoom ────────────────────────────────────────────────
    const g = svg.append('g')

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on('zoom', e => g.attr('transform', e.transform))
    )

    // ── Force simulation ───────────────────────────────────────────────────
    const sim = d3.forceSimulation<GraphNode>(nodesCopy)
      .force('link', d3.forceLink<GraphNode, typeof linksCopy[0]>(linksCopy as any)
        .id(d => d.id)
        .distance(d => 80 + (d.weight ?? 1) * 8)
        .strength(0.6))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<GraphNode>(d => NODE_RADIUS[d.type] + 8))

    simRef.current = sim as unknown as d3.Simulation<GraphNode, GraphLink>

    // ── Links ──────────────────────────────────────────────────────────────
    const linkSel = g.append('g').selectAll('line')
      .data(linksCopy)
      .join('line')
      .attr('stroke', d => linkStroke(d.riskLevel))
      .attr('stroke-opacity', 0.55)
      .attr('stroke-width', d => Math.sqrt(d.weight + 1) * 1.4)

    // ── Nodes ──────────────────────────────────────────────────────────────
    const nodeSel = g.append('g').selectAll<SVGGElement, GraphNode>('g')
      .data(nodesCopy)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) sim.alphaTarget(0)
            d.fx = null; d.fy = null
          })
      )

    // Risk aura ring
    nodeSel.append('circle')
      .attr('r', d => NODE_RADIUS[d.type] + 5)
      .attr('fill', 'none')
      .attr('stroke', d => riskColor(riskLevelFromScore(d.riskScore)))
      .attr('stroke-width', 2)
      .attr('opacity', 0.5)
      .attr('filter', 'url(#glow)')

    // Main circle
    nodeSel.append('circle')
      .attr('r', d => NODE_RADIUS[d.type])
      .attr('fill', d => NODE_COLOR[d.type])
      .attr('stroke', '#0f172a')
      .attr('stroke-width', 2)

    // Label
    nodeSel.append('text')
      .text(d => d.label)
      .attr('dy', d => NODE_RADIUS[d.type] + 13)
      .attr('text-anchor', 'middle')
      .attr('font-size', 9)
      .attr('fill', '#94a3b8')
      .attr('pointer-events', 'none')

    // Tooltip on hover
    const tooltip = d3.select('body').selectAll<HTMLDivElement, unknown>('#d3-tooltip')
      .data([null])
      .join('div')
      .attr('id', 'd3-tooltip')
      .style('position', 'fixed')
      .style('pointer-events', 'none')
      .style('background', '#1e293b')
      .style('border', '1px solid #334155')
      .style('border-radius', '6px')
      .style('padding', '8px 12px')
      .style('font-size', '12px')
      .style('color', '#e2e8f0')
      .style('opacity', '0')
      .style('z-index', '9999')
      .style('transition', 'opacity 0.15s')

    nodeSel
      .on('mouseover', (event, d) => {
        tooltip
          .html(`<strong>${d.label}</strong><br/>Tipo: ${d.type}<br/>Risco: <span style="color:${riskColor(riskLevelFromScore(d.riskScore))}">${d.riskScore}</span>`)
          .style('opacity', '1')
          .style('left', `${event.clientX + 12}px`)
          .style('top',  `${event.clientY - 10}px`)
      })
      .on('mousemove', event => {
        tooltip.style('left', `${event.clientX + 12}px`).style('top', `${event.clientY - 10}px`)
      })
      .on('mouseout', () => tooltip.style('opacity', '0'))

    // ── Tick ──────────────────────────────────────────────────────────────
    sim.on('tick', () => {
      linkSel
        .attr('x1', d => ((d.source as unknown) as GraphNode).x ?? 0)
        .attr('y1', d => ((d.source as unknown) as GraphNode).y ?? 0)
        .attr('x2', d => ((d.target as unknown) as GraphNode).x ?? 0)
        .attr('y2', d => ((d.target as unknown) as GraphNode).y ?? 0)

      nodeSel.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    // Animate node entrance
    nodeSel.selectAll('circle')
      .attr('r', 0)
      .transition()
      .duration(500)
      .delay((_, i) => i * 15)
      .attr('r', (d: unknown) => {
        const node = d as GraphNode
        return NODE_RADIUS[node.type]
      })

    return () => { sim.stop() }
  }, [graph, width, height])

  useEffect(() => {
    const cleanup = draw()
    return () => {
      cleanup?.()
      simRef.current?.stop()
    }
  }, [draw])

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="rounded-xl bg-surface-900"
      style={{ display: 'block' }}
    />
  )
}
