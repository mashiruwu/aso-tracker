import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const Icon = ({ name, size = 18 }) => {
  const paths = {
    apps: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const text = await response.text()
  let body
  try {
    body = text ? JSON.parse(text) : {}
  } catch {
    if (text.trim().startsWith('<!doctype') || text.trim().startsWith('<html')) {
      throw new Error('The local server is out of date. Stop it and run python3 app.py again.')
    }
    throw new Error('The local server returned an invalid response.')
  }
  if (!response.ok) throw new Error(body.error || 'Something went wrong')
  return body
}

const countryFlag = country => ({ us: '🇺🇸', gb: '🇬🇧', br: '🇧🇷', ca: '🇨🇦', au: '🇦🇺', de: '🇩🇪', fr: '🇫🇷', es: '🇪🇸' }[country] || '🌐')

function timeAgo(value) {
  if (!value) return 'Never'
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value)
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  const days = Math.floor(seconds / 86400)
  return days === 1 ? 'Yesterday' : `${days} days ago`
}

const Modal = ({ title, children, onClose }) => (
  <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <header><div><span className="eyebrow">ASO Tracker</span><h2>{title}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><Icon name="close" /></button></header>
      {children}
    </section>
  </div>
)

const AppIcon = ({ app, small = false }) => app?.icon_url
  ? <img className={small ? 'app-icon small' : 'app-icon'} src={app.icon_url} alt="" />
  : <span className={small ? 'app-icon fallback small' : 'app-icon fallback'}>{app?.name?.[0] || 'A'}</span>

function Score({ value }) {
  if (value == null) return <span className="muted">—</span>
  const tone = value < 35 ? 'low' : value < 70 ? 'medium' : 'high'
  return <div className="score"><strong>{value}</strong><span className="bar"><i className={tone} style={{ width: `${value}%` }} /></span></div>
}

function RankChart({ item }) {
  const points = (item?.points || []).filter(point => point.rank != null)
  if (points.length < 2) return <div className="chart-empty">At least two ranking checks are needed for a chart.</div>
  const width = 920, height = 310, padX = 48, padY = 30
  const maxRank = Math.max(20, Math.ceil(Math.max(...points.map(point => point.rank)) / 20) * 20)
  const x = index => padX + index * ((width - padX * 2) / (points.length - 1))
  const y = rank => padY + (rank - 1) * ((height - padY * 2) / Math.max(1, maxRank - 1))
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${x(index)} ${y(point.rank)}`).join(' ')
  const area = `${path} L ${x(points.length - 1)} ${height - padY} L ${x(0)} ${height - padY} Z`
  const ticks = [1, Math.round(maxRank / 2), maxRank]
  return <div className="chart-scroll"><svg className="rank-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Ranking history for ${item.keyword}`}>
    <defs><linearGradient id="rankArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#7657ff" stopOpacity=".32"/><stop offset="1" stopColor="#7657ff" stopOpacity="0"/></linearGradient></defs>
    {ticks.map(tick => <g key={tick}><line x1={padX} x2={width-padX} y1={y(tick)} y2={y(tick)} className="chart-grid"/><text x={padX-12} y={y(tick)+4} textAnchor="end" className="chart-label">#{tick}</text></g>)}
    <path d={area} fill="url(#rankArea)"/><path d={path} className="chart-line"/>
    {points.map((point, index) => <g key={point.date}><circle cx={x(index)} cy={y(point.rank)} r={index === points.length-1 ? 5 : 3} className="chart-point"><title>{point.date}: #{point.rank}</title></circle>{(index === 0 || index === points.length-1) && <text x={x(index)} y={height-8} textAnchor={index === 0 ? 'start' : 'end'} className="chart-label">{new Date(`${point.date}T00:00:00`).toLocaleDateString(undefined, {month:'short', day:'numeric'})}</text>}</g>)}
  </svg></div>
}

function EvolutionDashboard({ history, range, onRangeChange }) {
  const available = (history?.series || []).filter(item => item.points.some(point => point.rank != null))
  const [keywordId, setKeywordId] = useState(null)
  useEffect(() => { setKeywordId(current => available.some(item => item.keyword_id === current) ? current : available[0]?.keyword_id || null) }, [history])
  const selected = available.find(item => item.keyword_id === keywordId)
  const ranked = (selected?.points || []).filter(point => point.rank != null)
  const first = ranked[0]?.rank
  const latest = ranked[ranked.length - 1]?.rank
  const best = ranked.length ? Math.min(...ranked.map(point => point.rank)) : null
  const change = first != null && latest != null ? first - latest : null
  return <div className="evolution">
    <div className="history-filters"><label><span>Keyword</span><select value={keywordId || ''} onChange={event => setKeywordId(Number(event.target.value))}>{available.map(item => <option key={item.keyword_id} value={item.keyword_id}>{item.keyword}</option>)}</select></label><label><span>Period</span><select value={range} onChange={event => onRangeChange(event.target.value)}><option value="7">Last 7 days</option><option value="15">Last 15 days</option><option value="30">Last 30 days</option><option value="version">Current version</option></select></label></div>
    {available.length ? <section className="chart-card simple-chart"><div className="chart-header"><div><span className="eyebrow">Position history</span><h2>{selected?.keyword}</h2></div><div className="chart-summary"><span>Latest <b>{latest ? `#${latest}` : '—'}</b></span><span>Best <b>{best ? `#${best}` : '—'}</b></span><span>Change <b className={change > 0 ? 'up' : change < 0 ? 'down' : ''}>{change == null ? '—' : change > 0 ? `↑ ${change}` : change < 0 ? `↓ ${Math.abs(change)}` : '± 0'}</b></span></div></div><RankChart item={selected}/></section> : <div className="empty evolution-empty"><h2>No history for this period</h2><p>Run the analyzer on at least two different days to see keyword evolution.</p></div>}
  </div>
}

function App() {
  const [apps, setApps] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [keywords, setKeywords] = useState([])
  const [history, setHistory] = useState(null)
  const [historyRange, setHistoryRange] = useState('30')
  const [view, setView] = useState('keywords')
  const [query, setQuery] = useState('')
  const [modal, setModal] = useState(null)
  const [status, setStatus] = useState({ running: false })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const selected = apps.find(app => app.id === selectedId)
  const loadApps = useCallback(async () => {
    const data = await api('/api/apps')
    setApps(data)
    setSelectedId(current => current && data.some(app => app.id === current) ? current : data[0]?.id || null)
  }, [])
  const loadKeywords = useCallback(async id => {
    if (!id) return setKeywords([])
    setKeywords(await api(`/api/apps/${id}/keywords`))
  }, [])
  const loadHistory = useCallback(async id => {
    if (!id) return setHistory(null)
    setHistory(await api(`/api/apps/${id}/history?range=${historyRange}`))
  }, [historyRange])

  useEffect(() => {
    loadApps().catch(error => setError(error.message)).finally(() => setLoading(false))
  }, [loadApps])
  useEffect(() => { Promise.all([loadKeywords(selectedId), loadHistory(selectedId)]).catch(error => setError(error.message)) }, [selectedId, loadKeywords, loadHistory])
  useEffect(() => {
    const check = async () => {
      try {
        const next = await api('/api/status')
        if (status.running && !next.running) {
          await Promise.all([loadApps(), loadKeywords(selectedId), loadHistory(selectedId)])
        }
        setStatus(next)
      } catch (error) { setError(error.message) }
    }
    check()
    const timer = setInterval(check, 2500)
    return () => clearInterval(timer)
  }, [status.running, selectedId, loadApps, loadKeywords, loadHistory])

  const visibleKeywords = useMemo(() => keywords.filter(item => item.keyword.includes(query.toLowerCase())), [keywords, query])

  const collect = async () => {
    setError('')
    try {
      await api('/api/collect', { method: 'POST', body: '{}' })
      setStatus(current => ({ ...current, running: true }))
    } catch (error) { setError(error.message) }
  }

  const removeKeyword = async item => {
    await api(`/api/keywords/${item.id}`, { method: 'DELETE' })
    setKeywords(current => current.filter(keyword => keyword.id !== item.id))
  }

  return <main className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Icon name="apps" size={17} /></span><span>ASO <b>Tracker</b></span></div>
      <div className="section-label"><span>Apps</span><span>{apps.length}</span></div>
      <div className="app-list">
        {apps.map(app => <button key={app.id} className={`app-card ${app.id === selectedId ? 'active' : ''}`} onClick={() => setSelectedId(app.id)}>
          <AppIcon app={app} />
          <span className="app-copy"><strong>{app.name}</strong><small>{countryFlag(app.country)} {app.country.toUpperCase()} · {app.keyword_count} keywords</small></span>
        </button>)}
        {!loading && !apps.length && <div className="sidebar-empty">Add your first App Store app to get started.</div>}
      </div>
      <button className="add-app" onClick={() => setModal('app')}><span>Add app</span><Icon name="plus" /></button>
    </aside>

    <section className="workspace">
      <header className="topbar">
        <div className="page-title"><span className="eyebrow">{view === 'keywords' ? 'Keyword tracking' : 'Ranking evolution'}</span><h1>{selected?.name || 'Your apps'}</h1></div>
        <div className="actions">
          {selected && <span className="country-pill">{countryFlag(selected.country)} {selected.country.toUpperCase()}</span>}
          <button className="button secondary" onClick={collect} disabled={status.running || !apps.length}><Icon name="refresh" />{status.running ? 'Analyzing…' : 'Analyze now'}</button>
          <button className="button primary" onClick={() => setModal('keywords')} disabled={!selected}><Icon name="plus" />Add keywords</button>
        </div>
      </header>

      {error && <div className="alert"><span>{error}</span><button onClick={() => setError('')}><Icon name="close" size={15}/></button></div>}

      <div className="toolbar">
        <div className="view-switch"><button className={view === 'keywords' ? 'active' : ''} onClick={() => setView('keywords')}>Keywords</button><button className={view === 'evolution' ? 'active' : ''} onClick={() => setView('evolution')}>Evolution</button></div>
        {view === 'keywords' ? <label className="search"><Icon name="search" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search keywords" /></label> : <div className="summary">{history?.scope_label || 'Ranking history'}</div>}
      </div>

      {view === 'keywords' ? <div className="table-wrap">
        <table>
          <thead><tr><th>Keyword</th><th>Last update</th><th>Store</th><th>Difficulty</th><th>Position</th><th>Trend</th><th>Apps in ranking</th><th></th></tr></thead>
          <tbody>
            {visibleKeywords.map(item => <tr key={item.id}>
              <td><strong className="keyword">{item.keyword}</strong></td>
              <td className="muted">{timeAgo(item.last_update)}</td>
              <td><span className="store">{countryFlag(selected.country)} {selected.country.toUpperCase()}</span></td>
              <td><Score value={item.difficulty} /></td>
              <td><strong className={item.rank ? '' : 'muted'}>{item.rank ? `#${item.rank}` : 'Not ranked'}</strong></td>
              <td><span className={`trend ${item.change > 0 ? 'up' : item.change < 0 ? 'down' : ''}`}>{item.change == null ? '—' : item.change > 0 ? `↑ ${item.change}` : item.change < 0 ? `↓ ${Math.abs(item.change)}` : '± 0'}</span></td>
              <td><div className="competitors">{item.competitors.slice(0, item.competitors.some(app => app.icon_url) ? 5 : 2).map((app, index) => app.icon_url
                ? <span className="competitor-icon" key={`${app.app_store_id}-${index}`} data-tooltip={`#${app.position} ${app.name}`}><img src={app.icon_url} alt={app.name} /></span>
                : <span className="competitor-name" key={`${app.app_store_id}-${index}`} title={app.name}><b>#{app.position}</b> {app.name}</span>)}</div></td>
              <td><button className="row-action" onClick={() => removeKeyword(item)} title="Remove keyword"><Icon name="trash" size={16} /></button></td>
            </tr>)}
          </tbody>
        </table>
        {!loading && selected && !visibleKeywords.length && <div className="empty"><span className="empty-mark"><Icon name={query ? 'search' : 'plus'} size={24}/></span><h2>{query ? 'No matching keywords' : 'Add keywords to start tracking'}</h2><p>{query ? 'Try a different search.' : 'The daily analyzer will save position, difficulty and competitors here.'}</p>{!query && <button className="button primary" onClick={() => setModal('keywords')}>Add keywords</button>}</div>}
        {!loading && !selected && <div className="empty"><span className="empty-mark"><Icon name="apps" size={24}/></span><h2>Add your first app</h2><p>Use its numeric App Store ID. We’ll fetch the name, icon and current version.</p><button className="button primary" onClick={() => setModal('app')}>Add app</button></div>}
      </div> : <EvolutionDashboard history={history} range={historyRange} onRangeChange={setHistoryRange} />}
      <footer><span><i className={status.running ? 'status-dot running' : 'status-dot'} /> {status.running ? 'Analysis in progress' : 'Ready'}</span><span>Data stays in your local SQLite database</span></footer>
    </section>

    {modal === 'app' && <AddAppModal onClose={() => setModal(null)} onSaved={async result => { await loadApps(); setSelectedId(result.apps[0]?.id || null); setModal(null) }} />}
    {modal === 'keywords' && <AddKeywordsModal app={selected} onClose={() => setModal(null)} onSaved={async () => { await Promise.all([loadApps(), loadKeywords(selectedId), loadHistory(selectedId)]); setModal(null) }} />}
  </main>
}

function AddAppModal({ onClose, onSaved }) {
  const [query, setQuery] = useState('')
  const [appStoreIds, setAppStoreIds] = useState('')
  const [country, setCountry] = useState('us')
  const [busy, setBusy] = useState(false)
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState([])
  const [error, setError] = useState('')
  const search = async event => {
    event.preventDefault(); setSearching(true); setError(''); setSelected([])
    try { setResults(await api(`/api/app-search?query=${encodeURIComponent(query)}&country=${country}`)) }
    catch (error) { setError(error.message); setResults([]) }
    finally { setSearching(false) }
  }
  const toggle = id => setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('')
    const exactIds = appStoreIds.split(/[\s,]+/).filter(Boolean)
    const ids = [...new Set([...selected, ...exactIds])]
    try { onSaved(await api('/api/apps', { method: 'POST', body: JSON.stringify({ appStoreIds: ids, country }) })) }
    catch (error) { setError(error.message); setBusy(false) }
  }
  return <Modal title="Add apps" onClose={onClose}><div className="app-finder">
    <p className="form-intro">Search the App Store, then select one or several apps.</p>
    <label className="field"><span>Storefront</span><select value={country} onChange={event => { setCountry(event.target.value); setResults([]); setSelected([]) }}><option value="us">🇺🇸 United States</option><option value="gb">🇬🇧 United Kingdom</option><option value="br">🇧🇷 Brazil</option><option value="ca">🇨🇦 Canada</option><option value="au">🇦🇺 Australia</option><option value="de">🇩🇪 Germany</option><option value="fr">🇫🇷 France</option><option value="es">🇪🇸 Spain</option></select></label>
    <form className="app-search-form" onSubmit={search}><label className="field"><span>App name</span><div className="search-input"><input autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by name" /><button className="button secondary" disabled={searching || query.trim().length < 2}>{searching ? 'Searching…' : 'Search'}</button></div></label></form>
    {results.length > 0 && <div className="search-results">{results.map(app => <button type="button" key={app.app_store_id} className={`search-result ${selected.includes(app.app_store_id) ? 'selected' : ''}`} onClick={() => toggle(app.app_store_id)}>
      <AppIcon app={app} small /><span><strong>{app.name}</strong><small>{app.developer}</small></span><i>{selected.includes(app.app_store_id) ? '✓' : '+'}</i>
    </button>)}</div>}
    {!searching && query && !results.length && !error && <p className="no-results">Search to see matching App Store apps.</p>}
    <details className="exact-id"><summary>Add by exact ID instead</summary><label className="field"><span>One or more App Store IDs</span><textarea value={appStoreIds} onChange={event => setAppStoreIds(event.target.value)} placeholder="6468444410" rows="2" /></label></details>
    {error && <p className="form-error">{error}</p>}<div className="form-actions"><small>{selected.length} selected</small><button type="button" className="button ghost" onClick={onClose}>Cancel</button><button className="button primary" onClick={submit} disabled={busy || (!selected.length && !appStoreIds.trim())}>{busy ? 'Adding…' : `Add ${selected.length > 1 ? `${selected.length} apps` : 'app'}`}</button></div>
  </div></Modal>
}

function AddKeywordsModal({ app, onClose, onSaved }) {
  const [keywords, setKeywords] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const count = keywords.split('\n').filter(value => value.trim()).length
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('')
    try { await api(`/api/apps/${app.id}/keywords`, { method: 'POST', body: JSON.stringify({ keywords }) }); onSaved() }
    catch (error) { setError(error.message); setBusy(false) }
  }
  return <Modal title="Add keywords" onClose={onClose}><form onSubmit={submit}>
    <p className="form-intro">Tracking for <strong>{app.name}</strong> in {countryFlag(app.country)} {app.country.toUpperCase()}.</p>
    <label className="field"><span>One keyword per line</span><textarea autoFocus value={keywords} onChange={event => setKeywords(event.target.value)} placeholder={'flashcards\nai study\nspaced repetition'} rows="7" /></label>
    {error && <p className="form-error">{error}</p>}<div className="form-actions"><small>{count} keyword{count === 1 ? '' : 's'}</small><button type="button" className="button ghost" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Add keywords'}</button></div>
  </form></Modal>
}

createRoot(document.getElementById('root')).render(<App />)
