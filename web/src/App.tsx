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
  area_m2: 'Área construída',
  idade_anos: 'Idade do imóvel',
  tipo: 'Tipo do imóvel',
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
    <main className="folha">
      <header className="cabecalho">
        <div className="selo" aria-hidden="true">
          <span>ITBI-SP</span>
          <span>+</span>
          <span>BCB</span>
        </div>
        <p className="sobrelinha">Estimativa fundamentada em registros públicos</p>
        <h1>
          Previsor de<br />Imóveis
        </h1>
        <p className="lede">
          Preço estimado a partir de <strong>~100 mil transações reais</strong> de compra e
          venda (ITBI São Paulo, 2024–2026), ajustado por estado com o índice de avaliação
          do Banco Central. Sem anúncio inflado: valor de guia paga.
        </p>
      </header>

      <form onSubmit={prever} className="guia" aria-label="Dados do imóvel">
        <p className="guia-titulo">Declaração do imóvel</p>

        <div className="campos">
          <label>
            <span className="rotulo">Estado</span>
            <select value={form.uf} onChange={(e) => set('uf', e.target.value)}>
              {UFS.map((u) => <option key={u}>{u}</option>)}
            </select>
          </label>
          <label>
            <span className="rotulo">Tipo</span>
            <select value={form.tipo} onChange={(e) => set('tipo', e.target.value)}>
              <option value="apartamento">Apartamento</option>
              <option value="casa">Casa</option>
            </select>
          </label>
          <label className="campo-largo">
            <span className="rotulo">Bairro <em>(referência: São Paulo capital)</em></span>
            <input list="bairros" value={form.bairro} placeholder="MOEMA"
              onChange={(e) => set('bairro', e.target.value)} />
            <datalist id="bairros">
              {bairros.map((b) => <option key={b} value={b} />)}
            </datalist>
          </label>
          <label>
            <span className="rotulo">Área construída</span>
            <span className="com-unidade">
              <input type="number" min={15} max={1000} value={form.area_m2}
                onChange={(e) => set('area_m2', Number(e.target.value))} />
              <span className="unidade">m²</span>
            </span>
          </label>
          <label>
            <span className="rotulo">Idade do imóvel</span>
            <span className="com-unidade">
              <input type="number" min={0} max={120} value={form.idade_anos}
                onChange={(e) => set('idade_anos', Number(e.target.value))} />
              <span className="unidade">anos</span>
            </span>
          </label>
        </div>

        <button type="submit" disabled={carregando}>
          {carregando ? 'Consultando registros…' : 'Estimar preço'}
        </button>
      </form>

      {erro && (
        <p className="erro" role="alert">
          {erro}. A API hiberna quando ociosa (custo zero) — tente novamente em alguns segundos.
        </p>
      )}

      {resultado && (
        <section className="laudo" aria-label="Resultado da estimativa">
          <div className="laudo-topo">
            <p className="guia-titulo">Valor estimado</p>
            {resultado.base_bairro?.reconhecido && (
              <p className="lastro">
                lastreado em <strong>{resultado.base_bairro.n_transacoes}</strong> transações
                do bairro
              </p>
            )}
          </div>

          <p className="preco">{brl(resultado.preco_estimado)}</p>
          <p className="preco-m2">
            {brl(resultado.preco_m2)}<span> / m²</span>
            {resultado.ajuste_uf !== 1 && (
              <span className="ajuste"> · ajuste {form.uf} ×{resultado.ajuste_uf.toFixed(2)}</span>
            )}
          </p>

          {(resultado.avisos ?? []).map((aviso) => (
            <p key={aviso} className="aviso">{aviso}</p>
          ))}

          <h2>Composição da estimativa</h2>
          <ul className="razao">
            {Object.entries(resultado.fatores_pct).slice(0, 5).map(([fator, pct]) => (
              <li key={fator}>
                <span className="fator">{ROTULOS[fator] ?? fator}</span>
                <span className="pontilhado" aria-hidden="true" />
                <span className={`efeito ${pct >= 0 ? 'positivo' : 'negativo'}`}>
                  {pct >= 0 ? '+' : '−'}{Math.abs(pct).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>

          <p className="metodologia">{resultado.metodologia}</p>
        </section>
      )}

      <footer className="rodape">
        <p>
          Projeto de portfólio — pipeline completo de ML na Azure ·{' '}
          <a href="https://github.com/arthurhardman/previsor-imoveis">código no GitHub</a>
        </p>
      </footer>
    </main>
  )
}
