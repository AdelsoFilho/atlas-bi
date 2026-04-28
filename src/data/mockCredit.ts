import type { Associado, OperacaoCredito, Garantia, Segmento, TipoGarantia } from '../types/credit'
import { nivelFromDPD, PCLD_PCT } from '../utils/creditMetrics'

// ─── Seeded RNG (determinística) ─────────────────────────────────────────────
const mkRng = (seed: number) => {
  let s = seed
  return {
    f: (lo: number, hi: number) => { s = (s * 16807) % 2147483647; return lo + ((s - 1) / 2147483646) * (hi - lo) },
    i: (lo: number, hi: number) => { s = (s * 16807) % 2147483647; return lo + Math.floor(((s - 1) / 2147483646) * (hi - lo + 1)) },
    p: <T>(arr: T[]): T => { s = (s * 16807) % 2147483647; return arr[Math.floor(((s - 1) / 2147483646) * arr.length)] },
  }
}
const rng = mkRng(2026)

// ─── Dados de referência ─────────────────────────────────────────────────────
const NOMES_PF = ['João Augusto Fonseca','Maria das Graças Souza','Carlos Eduardo Lima',
  'Ana Paula Costa','Roberto Mendes Filho','Fernanda Ribeiro','Marcos Vinícius Alves',
  'Juliana Pereira','Sérgio Luiz Nunes','Adriana Fonseca','Alexandre Melo',
  'Patrícia Rocha','Leandro Gomes','Camila Vieira','Gustavo Henrique Silva',
  'Daniela Castro','Paulo Roberto Dias','Renata Xavier','Thiago Araújo',
  'Aline Moura','Rogério Santos','Vanessa Barros','Cristiane Lima','Fábio Carvalho']

const NOMES_PJ = ['Agro Cerrado Ltda','Fazenda Santa Fé','Distribuidora Central SA',
  'Pecuária Rio Verde ME','Supermercado Estrela Ltda','Soja Sul SA',
  'Laticínios Norte ME','Comércio União ME','Metalúrgica Boa Vista',
  'Transporte Expresso ME','Maquinas & Cia Ltda','Coop Agro Leste']

// ─── Associados (60) ─────────────────────────────────────────────────────────
const PERFIS = [
  { peso: 15, score_s: [780,950], score_c: [720,920], anos: [10,22], capital: [8000,40000], renda: [15000,60000] },
  { peso: 20, score_s: [620,780], score_c: [560,730], anos: [4,12],  capital: [3000,12000], renda: [6000,18000] },
  { peso: 13, score_s: [450,620], score_c: [380,580], anos: [2,7],   capital: [500,4000],   renda: [3500,9000]  },
  { peso: 8,  score_s: [300,500], score_c: [220,450], anos: [1,4],   capital: [200,2000],   renda: [2500,6000]  },
  { peso: 4,  score_s: [150,380], score_c: [100,320], anos: [0.5,3], capital: [100,1000],   renda: [2000,5000]  },
]

export const ASSOCIADOS: Associado[] = []
let ai = 1
for (const p of PERFIS) {
  for (let k = 0; k < p.peso; k++) {
    const ehPJ = p.peso === 15 && rng.f(0,1) < 0.35
    ASSOCIADOS.push({
      id:                  `ASC-${String(ai).padStart(4,'0')}`,
      nome:                ehPJ ? rng.p(NOMES_PJ) : rng.p(NOMES_PF),
      cpf_cnpj:            ehPJ
        ? `${rng.i(10,99)}.${rng.i(100,999)}.${rng.i(100,999)}/0001-${rng.i(10,99)}`
        : `${rng.i(100,999)}.${rng.i(100,999)}.${rng.i(100,999)}-${rng.i(10,99)}`,
      tipo:                ehPJ ? 'PJ' : 'PF',
      capital_integralizado: Math.round(rng.f(p.capital[0], p.capital[1])),
      score_cooperativo:     Math.round(rng.f(p.score_c[0], p.score_c[1])),
      score_serasa:          Math.round(rng.f(p.score_s[0], p.score_s[1])),
      anos_associado:        Math.round(rng.f(p.anos[0], p.anos[1]) * 10) / 10,
      renda_mensal:          Math.round(rng.f(p.renda[0], p.renda[1])),
    })
    ai++
  }
}

// ─── Operações + Garantias ────────────────────────────────────────────────────
type OpTemplate = {
  seg: Segmento; taxa: [number,number]; valor: [number,number]
  prazo: [number,number]; dpd: () => number; variavel: boolean
  garantia: TipoGarantia; cobertura: [number,number]
}

const TEMPLATES: OpTemplate[] = [
  // Agro bom
  { seg:'agro',        taxa:[1.20,1.80], valor:[80000,400000],  prazo:[12,18],   dpd:()=>0,              variavel:false, garantia:'penhor_safra',  cobertura:[0.85,1.20] },
  { seg:'agro',        taxa:[0.95,1.40], valor:[150000,800000], prazo:[36,84],   dpd:()=>rng.i(0,8),    variavel:false, garantia:'hipoteca',      cobertura:[1.10,1.50] },
  // Agro problemático
  { seg:'agro',        taxa:[1.30,2.00], valor:[50000,250000],  prazo:[12,24],   dpd:()=>rng.i(60,200), variavel:false, garantia:'penhor_safra',  cobertura:[0.60,0.90] },
  // Varejo bom
  { seg:'varejo',      taxa:[1.60,2.20], valor:[30000,200000],  prazo:[12,36],   dpd:()=>0,              variavel:true,  garantia:'avalista',      cobertura:[0.70,1.00] },
  { seg:'varejo',      taxa:[1.40,1.90], valor:[50000,350000],  prazo:[12,48],   dpd:()=>rng.i(0,10),   variavel:true,  garantia:'alienacao_fid', cobertura:[0.80,1.10] },
  // Varejo problemático
  { seg:'varejo',      taxa:[2.00,2.80], valor:[20000,100000],  prazo:[12,24],   dpd:()=>rng.i(45,180), variavel:true,  garantia:'avalista',      cobertura:[0.50,0.80] },
  // Pessoal bom
  { seg:'pessoal',     taxa:[1.20,1.70], valor:[10000,80000],   prazo:[24,72],   dpd:()=>0,              variavel:false, garantia:'avalista',      cobertura:[0.60,0.90] },
  { seg:'consignado',  taxa:[0.90,1.30], valor:[15000,100000],  prazo:[36,84],   dpd:()=>0,              variavel:false, garantia:'sem_garantia',  cobertura:[0,0]       },
  // Pessoal problemático
  { seg:'pessoal',     taxa:[2.20,3.50], valor:[3000,20000],    prazo:[12,36],   dpd:()=>rng.i(30,200), variavel:false, garantia:'sem_garantia',  cobertura:[0,0]       },
  // Imobiliário
  { seg:'imobiliario', taxa:[0.75,1.10], valor:[150000,600000], prazo:[120,240], dpd:()=>0,              variavel:false, garantia:'hipoteca',      cobertura:[1.10,1.50] },
  { seg:'imobiliario', taxa:[0.85,1.20], valor:[200000,900000], prazo:[120,180], dpd:()=>rng.i(0,20),   variavel:false, garantia:'hipoteca',      cobertura:[1.00,1.40] },
]

// Distribui perfis de associado por segmento
const assocByPerfil = (minScore: number, maxScore: number) =>
  ASSOCIADOS.filter(a => a.score_cooperativo >= minScore && a.score_cooperativo <= maxScore)

const distrib: Array<{ tplIdx: number; qtd: number; assocs: Associado[] }> = [
  { tplIdx:0,  qtd:12, assocs: assocByPerfil(600,999) },
  { tplIdx:1,  qtd:10, assocs: assocByPerfil(650,999) },
  { tplIdx:2,  qtd:6,  assocs: assocByPerfil(100,500) },
  { tplIdx:3,  qtd:12, assocs: assocByPerfil(550,999) },
  { tplIdx:4,  qtd:10, assocs: assocByPerfil(500,800) },
  { tplIdx:5,  qtd:6,  assocs: assocByPerfil(100,480) },
  { tplIdx:6,  qtd:8,  assocs: assocByPerfil(400,900) },
  { tplIdx:7,  qtd:8,  assocs: assocByPerfil(600,999) },
  { tplIdx:8,  qtd:6,  assocs: assocByPerfil(100,450) },
  { tplIdx:9,  qtd:8,  assocs: assocByPerfil(600,999) },
  { tplIdx:10, qtd:4,  assocs: assocByPerfil(400,750) },
]

export const OPERACOES: OperacaoCredito[] = []
export const GARANTIAS: Garantia[] = []

let oi = 1, gi = 1
for (const { tplIdx, qtd, assocs } of distrib) {
  if (assocs.length === 0) continue
  const tpl = TEMPLATES[tplIdx]
  for (let k = 0; k < qtd; k++) {
    const assoc   = rng.p(assocs)
    const opId    = `OP-${String(oi).padStart(4,'0')}`
    const valor   = Math.round(rng.f(tpl.valor[0], tpl.valor[1]) / 100) * 100
    const taxa    = Math.round(rng.f(tpl.taxa[0], tpl.taxa[1]) * 100) / 100
    const prazo   = rng.i(tpl.prazo[0], tpl.prazo[1])
    const pago    = rng.i(1, Math.max(prazo - 1, 1))
    const dpd     = tpl.dpd()
    const renegs  = dpd > 30 ? rng.i(0,2) : 0
    const nivel   = nivelFromDPD(dpd, renegs)

    // Saldo devedor (amortização Price simplificada)
    const r = taxa / 100
    const saldo = r > 0
      ? Math.round(valor * ((1+r)**prazo - (1+r)**pago) / ((1+r)**prazo - 1))
      : Math.round(valor * (prazo - pago) / prazo)

    const pcld = Math.round(saldo * PCLD_PCT[nivel] / 100)

    // Garantia
    let gid: string | null = null
    if (tpl.garantia !== 'sem_garantia' && tpl.cobertura[1] > 0) {
      gid = `GAR-${String(gi).padStart(4,'0')}`
      const cobertura = rng.f(tpl.cobertura[0], tpl.cobertura[1])
      GARANTIAS.push({
        id:          gid,
        operacao_id: opId,
        tipo:        tpl.garantia,
        valor:       Math.round(saldo * cobertura),
        ltv:         Math.round((saldo / Math.max(saldo * cobertura, 1)) * 1000) / 1000,
      })
      gi++
    }

    OPERACOES.push({
      id:               opId,
      associado_id:     assoc.id,
      segmento:         tpl.seg,
      tipo_taxa:        tpl.variavel ? 'variavel' : 'fixa',
      valor_contratado: valor,
      saldo_devedor:    Math.max(saldo, 0),
      taxa_mensal_pct:  taxa,
      prazo_meses:      prazo,
      dias_atraso:      dpd,
      renegociacoes:    renegs,
      nivel_risco:      nivel,
      pcld,
      garantia_id:      gid,
    })
    oi++
  }
}
