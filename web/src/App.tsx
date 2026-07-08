import { useEffect, useState } from 'react'

// Em produção (Static Web Apps), defina VITE_API_URL apontando para o Container App
const API = import.meta.env.VITE_API_URL ?? '/api'

const UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT',
  'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
]

interface Previsao {
  preco_estimado: number
  preco_m2: number
  fatores_pct: Record<string, number>
  ajuste_uf: number
  // opcionais: durante um deploy, o front pode falar com uma API de versão anterior
  avisos?: string[]
  base_bairro?: { reconhecido: boolean; n_transacoes: number }
  metodologia: string
}

const brl = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })

const ROTULOS: Record<string, string> = {
  bairro: 'Bairro',
  area_m2: 'Área',
  idade_anos: 'Idade do imóvel',
  tipo: 'Tipo',
  ano: 'Ano de referência',
}

export default function App() {
  const [form, setForm] = useState({
    uf: 'SP',
    bairro: '',
    tipo: 'apartamento',
    area_m2: 70,
    idade_anos: 10,
  })
  const [bairros, setBairros] = useState<string[]>([])
  const [resultado, setResultado] = useState<Previsao | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/bairros`)
      .then((r) => r.json())
      .then(setBairros)
      .catch(() => {}) // autocomplete é opcional; API pode estar em cold start
  }, [])

  const set = (campo: string, valor: string | number) =>
    setForm((f) => ({ ...f, [campo]: valor }))

  async function prever(e: React.FormEvent) {
    e.preventDefault()
    setCarregando(true)
    setErro(null)
    try {
      const res = await fetch(`${API}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(`API respondeu ${res.status}`)
      setResultado(await res.json())
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro inesperado')
    } finally {
      setCarregando(false)
    }
  }

  return (
    <main className="container">
      <h1>Previsor de Imóveis</h1>
      <p className="subtitulo">
        Treinado em ~100 mil transações reais de compra e venda (ITBI São Paulo) e
        ajustado por estado com o índice do Banco Central.
      </p>

      <form onSubmit={prever} className="formulario">
        <label>
          Estado (UF)
          <select value={form.uf} onChange={(e) => set('uf', e.target.value)}>
            {UFS.map((u) => <option key={u}>{u}</option>)}
          </select>
        </label>
        <label>
          Tipo
          <select value={form.tipo} onChange={(e) => set('tipo', e.target.value)}>
            <option value="apartamento">apartamento</option>
            <option value="casa">casa</option>
          </select>
        </label>
        <label>
          Bairro
          <input list="bairros" value={form.bairro} placeholder="ex.: MOEMA"
            onChange={(e) => set('bairro', e.target.value)} />
          <datalist id="bairros">
            {bairros.map((b) => <option key={b} value={b} />)}
          </datalist>
        </label>
        <label>
          Área (m²)
          <input type="number" min={15} max={1000} value={form.area_m2}
            onChange={(e) => set('area_m2', Number(e.target.value))} />
        </label>
        <label>
          Idade do imóvel (anos)
          <input type="number" min={0} max={120} value={form.idade_anos}
            onChange={(e) => set('idade_anos', Number(e.target.value))} />
        </label>

        <button type="submit" disabled={carregando}>
          {carregando ? 'Calculando…' : 'Estimar preço'}
        </button>
      </form>

      {erro && <p className="erro">Erro: {erro}. A API pode estar em cold start — tente de novo em alguns segundos.</p>}

      {resultado && (
        <section className="resultado">
          <h2>{brl(resultado.preco_estimado)}</h2>
          <p>
            {brl(resultado.preco_m2)} / m²
            {resultado.ajuste_uf !== 1 && ` · ajuste ${form.uf}: ×${resultado.ajuste_uf.toFixed(2)}`}
            {resultado.base_bairro?.reconhecido &&
              ` · ${resultado.base_bairro.n_transacoes} transações reais no bairro`}
          </p>
          {(resultado.avisos ?? []).map((aviso) => (
            <p key={aviso} className="aviso">⚠️ {aviso}</p>
          ))}
          <h3>O que pesou na estimativa</h3>
          <ul>
            {Object.entries(resultado.fatores_pct).slice(0, 5).map(([fator, pct]) => (
              <li key={fator}>
                <span>{ROTULOS[fator] ?? fator}</span>
                <span className={pct >= 0 ? 'positivo' : 'negativo'}>
                  {pct >= 0 ? '+' : ''}{pct.toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
          <p className="metodologia">{resultado.metodologia}</p>
        </section>
      )}
    </main>
  )
}
