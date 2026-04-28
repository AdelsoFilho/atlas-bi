import { useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'
import type { CreditGraph, GraphNode } from '../types/credit'
import { nivelColor } from '../utils/creditMetrics'

interface Props { graph: CreditGraph; width: number; height: number }

// Tamanho base por tipo — escala logarítmica depois
const BASE_R: Record<GraphNode['type'], number> = { associado: 14, operacao: 10, garantia: 8 }
const NODE_COLOR: Record<GraphNode['type'], string> = {
  associado: '#818cf8',   // roxo
  operacao:  '#38bdf8',   // azul claro
  garantia:  '#fb923c',   // laranja
}

// Raio proporcional ao valor (saldo / capital), com limites
const nodeRadius = (d: GraphNode): number => {
  const base = BASE_R[d.type]
  if (d.value <= 0) return base
  const scale = Math.sqrt(d.value / 50_000)
  return Math.max(base * 0.6, Math.min(base * 2.5, base * scale))
}

export const CreditNetworkGraph = ({ graph, width, height }: Props) => {
  const svgRef = useRef<SVGSVGElement>(null)

  const draw = useCallback(() => {
    const svg = d3.select(svgRef.current!)
    svg.selectAll('*').remove()
    d3.selectAll('#credit-tooltip').remove()

    const { nodes, links } = graph
    const nodesCopy: GraphNode[] = nodes.map(n => ({ ...n }))
    const linksCopy = links.map(l => ({
      ...l,
      source: typeof l.source === 'string' ? l.source : (l.source as GraphNode).id,
      target: typeof l.target === 'string' ? l.target : (l.target as GraphNode).id,
    }))

    // ── Defs ──────────────────────────────────────────────────────────────
    const defs = svg.append('defs')
    const glow = defs.append('filter').attr('id', 'glow-credit')
    glow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur')
    const fm = glow.append('feMerge')
    fm.append('feMergeNode').attr('in', 'coloredBlur')
    fm.append('feMergeNode').attr('in', 'SourceGraphic')

    // ── Grupos de cluster por segmento (forças posicionais) ───────────────
    const segmentoCentros: Record<string, [number, number]> = {
      agro:        [width * 0.25, height * 0.28],
      varejo:      [width * 0.72, height * 0.30],
      imobiliario: [width * 0.50, height * 0.72],
      pessoal:     [width * 0.20, height * 0.68],
      consignado:  [width * 0.78, height * 0.68],
    }

    // ── Zoom ──────────────────────────────────────────────────────────────
    const g = svg.append('g')
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.25, 5])
        .on('zoom', e => g.attr('transform', e.transform))
    )

    // ── Simulação ─────────────────────────────────────────────────────────
    const sim = d3.forceSimulation<GraphNode>(nodesCopy)
      .force('link', d3.forceLink<GraphNode, typeof linksCopy[0]>(linksCopy as any)
        .id(d => d.id).distance(d => d.tipo === 'contrato' ? 70 : 45).strength(0.7))
      .force('charge',    d3.forceManyBody().strength(-120))
      .force('center',    d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<GraphNode>(d => nodeRadius(d) + 6))
      // Força de cluster por segmento
      .force('cluster_x', d3.forceX<GraphNode>(d => {
        const seg = d.segmento ?? (d.type === 'associado' ? 'pessoal' : undefined)
        return seg && segmentoCentros[seg] ? segmentoCentros[seg][0] : width / 2
      }).strength(0.06))
      .force('cluster_y', d3.forceY<GraphNode>(d => {
        const seg = d.segmento ?? (d.type === 'associado' ? 'pessoal' : undefined)
        return seg && segmentoCentros[seg] ? segmentoCentros[seg][1] : height / 2
      }).strength(0.06))

    // ── Links ─────────────────────────────────────────────────────────────
    const linkSel = g.append('g').selectAll('line')
      .data(linksCopy).join('line')
      .attr('stroke', d => d.tipo === 'contrato' ? '#4f46e5' : '#d97706')
      .attr('stroke-opacity', 0.45)
      .attr('stroke-width', d => d.tipo === 'contrato' ? 1.5 : 1)
      .attr('stroke-dasharray', d => d.tipo === 'garantia' ? '4 3' : null)

    // ── Nós ───────────────────────────────────────────────────────────────
    const nodeSel = g.append('g').selectAll<SVGGElement, GraphNode>('g')
      .data(nodesCopy).join('g').attr('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, GraphNode>()
          .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
          .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y })
          .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      )

    // Anel de risco (cor = nível BCB para operações, cor do tipo para demais)
    nodeSel.append('circle')
      .attr('r', d => nodeRadius(d) + 5)
      .attr('fill', 'none')
      .attr('stroke', d => d.type === 'operacao' ? nivelColor(d.nivelRisco) : NODE_COLOR[d.type])
      .attr('stroke-width', 2.5)
      .attr('opacity', 0.55)
      .attr('filter', 'url(#glow-credit)')

    // Círculo principal
    nodeSel.append('circle')
      .attr('r', d => nodeRadius(d))
      .attr('fill', d => NODE_COLOR[d.type])
      .attr('stroke', '#0a0f1e')
      .attr('stroke-width', 1.5)

    // Label
    nodeSel.append('text')
      .text(d => d.label)
      .attr('dy', d => nodeRadius(d) + 12)
      .attr('text-anchor', 'middle')
      .attr('font-size', 8)
      .attr('fill', '#94a3b8')
      .attr('pointer-events', 'none')

    // ── Tooltip ───────────────────────────────────────────────────────────
    const tooltip = d3.select('body').selectAll<HTMLDivElement, unknown>('#credit-tooltip')
      .data([null]).join('div').attr('id', 'credit-tooltip')
      .style('position', 'fixed').style('pointer-events', 'none')
      .style('background', '#1e293b').style('border', '1px solid #334155')
      .style('border-radius', '8px').style('padding', '10px 14px')
      .style('font-size', '12px').style('color', '#e2e8f0')
      .style('opacity', '0').style('z-index', '9999')
      .style('transition', 'opacity 0.15s').style('max-width', '220px')
      .style('line-height', '1.6')

    nodeSel
      .on('mouseover', (event, d) => {
        const typeLabel = { associado: 'Associado', operacao: 'Operação', garantia: 'Garantia' }[d.type]
        const cor = d.type === 'operacao' ? nivelColor(d.nivelRisco) : NODE_COLOR[d.type]
        let html = `<div style="font-weight:600;color:${cor};margin-bottom:4px">${typeLabel}: ${d.label}</div>`
        for (const [k, v] of Object.entries(d.meta)) {
          html += `<div><span style="color:#64748b">${k}:</span> ${v}</div>`
        }
        tooltip.html(html).style('opacity', '1')
          .style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
      })
      .on('mousemove', e => tooltip.style('left', `${e.clientX + 14}px`).style('top', `${e.clientY - 10}px`))
      .on('mouseout',  () => tooltip.style('opacity', '0'))

    // ── Tick ──────────────────────────────────────────────────────────────
    sim.on('tick', () => {
      linkSel
        .attr('x1', d => ((d.source as unknown) as GraphNode).x ?? 0)
        .attr('y1', d => ((d.source as unknown) as GraphNode).y ?? 0)
        .attr('x2', d => ((d.target as unknown) as GraphNode).x ?? 0)
        .attr('y2', d => ((d.target as unknown) as GraphNode).y ?? 0)
      nodeSel.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    // Entrada animada
    nodeSel.selectAll('circle').attr('r', 0)
      .transition().duration(500).delay((_, i) => i * 10)
      .attr('r', (d: unknown) => nodeRadius(d as GraphNode))

    return () => sim.stop()
  }, [graph, width, height])

  useEffect(() => {
    const cleanup = draw()
    return () => { cleanup?.(); d3.selectAll('#credit-tooltip').remove() }
  }, [draw])

  return (
    <svg ref={svgRef} width={width} height={height}
      className="rounded-xl bg-surface-900" style={{ display: 'block' }} />
  )
}
