export type NivelRisco = 'AA' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H'
export type Segmento  = 'agro' | 'varejo' | 'imobiliario' | 'pessoal' | 'consignado'
export type TipoGarantia = 'hipoteca' | 'penhor_safra' | 'alienacao_fid' | 'avalista' | 'sem_garantia'
export type TipoTaxa = 'fixa' | 'variavel'

export interface Associado {
  id: string
  nome: string
  cpf_cnpj: string
  tipo: 'PF' | 'PJ'
  capital_integralizado: number   // R$ — tamanho do nó no grafo
  score_cooperativo: number       // 0–1000
  score_serasa: number
  anos_associado: number
  renda_mensal: number
}

export interface OperacaoCredito {
  id: string
  associado_id: string
  segmento: Segmento
  tipo_taxa: TipoTaxa
  valor_contratado: number
  saldo_devedor: number           // tamanho do nó no grafo
  taxa_mensal_pct: number
  prazo_meses: number
  dias_atraso: number             // DPD
  renegociacoes: number
  nivel_risco: NivelRisco
  pcld: number                    // R$ provisão individual
  garantia_id: string | null
}

export interface Garantia {
  id: string
  operacao_id: string
  tipo: TipoGarantia
  valor: number
  ltv: number                     // saldo / valor garantia
}

// ─── Graph ────────────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string
  label: string
  type: 'associado' | 'operacao' | 'garantia'
  nivelRisco: NivelRisco
  value: number                   // saldo ou capital — determina raio do nó
  segmento?: Segmento
  meta: Record<string, string | number>
  x?: number; y?: number; vx?: number; vy?: number
  fx?: number | null; fy?: number | null
}

export interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  tipo: 'contrato' | 'garantia'   // associado→operacao | operacao→garantia
}

export interface CreditGraph {
  nodes: GraphNode[]
  links: GraphLink[]
}

// ─── KPIs ─────────────────────────────────────────────────────────────────────

export interface CreditKPIs {
  carteira_total: number
  operacoes_default: number       // DPD > 90
  pcld_total: number
  indice_basileia: number         // %
  npl_pct: number                 // carteira D–H / total
  total_operacoes: number
  total_associados: number
  cobertura_garantias_pct: number
}

// ─── Filtros ──────────────────────────────────────────────────────────────────

export interface FilterState {
  segmento: Segmento | 'all'
  nivelRisco: NivelRisco | 'all'
  scoreMin: number
  searchTerm: string
}
