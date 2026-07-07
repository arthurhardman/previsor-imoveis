import { useState } from 'react'

// Em produção (Static Web Apps), defina VITE_API_URL apontando para o Container App
const API = import.meta.env.VITE_API_URL ?? '/api'

const BAIRROS = ['Centro', 'Jardins', 'Vila Nova', 'Boa Vista', 'Industrial', 'Beira Rio']
const TIPOS = ['apartamento', 'casa', 'kitnet', 'cobertura']

interface Previsao {
  preco_estimado: number
  preco_m2: number
  fatores: Record<string, number>
}

const brl = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })

export default function App() {
  const [form, setForm] = useState({
    bairro: 'Centro',
    tipo: 'apartamento',
    area_m2: 70,
    quartos: 2,
    banheiros: 1,
    vagas: 1,
    idade_anos: 10,
  })
  const [resultado, setResultado] = useState<Previsao | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

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
        Modelo XGBoost servido em Azure Container Apps — estimativa de preço com explicação dos fatores.
      </p>

      <form onSubmit={prever} className="formulario">
        <label>
          Bairro
          <select value={form.bairro} onChange={(e) => set('bairro', e.target.value)}>
            {BAIRROS.map((b) => <option key={b}>{b}</option>)}
          </select>
        </label>
        <label>
          Tipo
          <select value={form.tipo} onChange={(e) => set('tipo', e.target.value)}>
            {TIPOS.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label>
          Área (m²)
          <input type="number" min={15} max={1000} value={form.area_m2}
            onChange={(e) => set('area_m2', Number(e.target.value))} />
        </label>
        <label>
          Quartos
          <input type="number" min={1} max={8} value={form.quartos}
            onChange={(e) => set('quartos', Number(e.target.value))} />
        </label>
        <label>
          Banheiros
          <input type="number" min={1} max={8} value={form.banheiros}
            onChange={(e) => set('banheiros', Number(e.target.value))} />
        </label>
        <label>
          Vagas
          <input type="number" min={0} max={6} value={form.vagas}
            onChange={(e) => set('vagas', Number(e.target.value))} />
        </label>
        <label>
          Idade do imóvel (anos)
          <input type="number" min={0} max={80} value={form.idade_anos}
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
          <p>{brl(resultado.preco_m2)} / m²</p>
          <h3>O que puxou o preço</h3>
          <ul>
            {Object.entries(resultado.fatores).slice(0, 5).map(([fator, valor]) => (
              <li key={fator}>
                <span>{fator}</span>
                <span className={valor >= 0 ? 'positivo' : 'negativo'}>
                  {valor >= 0 ? '+' : ''}{brl(valor)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}
