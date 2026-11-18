import { createContext, useContext, useEffect, useState } from 'react'
import { NavLink, Link, Outlet } from 'react-router-dom'
import { api } from '../api.js'
import { LEVELS, rub } from '../format.js'

const RefContext = createContext({ meta: null, regions: [] })
export const useRef_ = () => useContext(RefContext)

export function Layout() {
  const [meta, setMeta] = useState(null)
  const [regions, setRegions] = useState([])
  const [error, setError] = useState('')
  const reload = () => Promise.all([api.meta(), api.regions()])
    .then(([m, r]) => { setMeta(m); setRegions(r) })
    .catch((e) => setError(e.message))
  useEffect(() => { reload() }, [])

  return (
    <RefContext.Provider value={{ meta, regions, reload }}>
      <header className="header">
        <div className="header-inner">
          <Link to="/" className="brand">
            <b>Мониторинг ценовых рисков</b>
            <span>Закупки строительных материалов · прототип</span>
          </Link>
          <nav aria-label="Разделы" className="nav">
            <NavLink to="/" end>Проверки</NavLink>
            <NavLink to="/reference">Справочники цен</NavLink>
            <NavLink to="/analogs">Объекты-аналоги</NavLink>
            <NavLink to="/journal">Журнал решений</NavLink>
          </nav>
          <div className="user">Специалист · демо-доступ</div>
        </div>
      </header>
      {meta?.is_demo && (
        <div className="demo-banner" role="note">
          <div>Загружены демонстрационные справочники цен для Брянской и Томской областей. Результаты расчёта
            показывают работу системы и не являются данными о реальных ценах.</div>
        </div>
      )}
      {error && <div className="page"><div className="error">Сервер недоступен: {error}</div></div>}
      <Outlet />
    </RefContext.Provider>
  )
}

export function Badge({ level, children }) {
  return <span className={`badge ${level}`}>{children || LEVELS[level] || level}</span>
}

export function RegionSelect({ id, value, onChange, regions, allowAll = false }) {
  const pilot = regions.filter((r) => r.is_pilot)
  const byDistrict = {}
  regions.filter((r) => !r.is_pilot).forEach((r) => {
    (byDistrict[r.federal_district] ||= []).push(r)
  })
  return (
    <select id={id} className="select" value={value ?? ''} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      {allowAll && <option value="">Все регионы ({regions.length})</option>}
      {!allowAll && <option value="" disabled>Выберите регион</option>}
      <optgroup label="Пилотные регионы">
        {pilot.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
      </optgroup>
      {Object.keys(byDistrict).sort().map((d) => (
        <optgroup key={d} label={`${d} федеральный округ`}>
          {byDistrict[d].sort((a, b) => a.name.localeCompare(b.name, 'ru')).map((r) => (
            <option key={r.id} value={r.id}>{r.name}{r.has_prices ? '' : ' — нет цен'}</option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

export function Loading() {
  return <div className="page"><div className="muted">Загрузка…</div></div>
}

export function UploadIcon() {
  return (
    <svg aria-hidden="true" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0d4c8c" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 16V4" /><path d="M7 9l5-5 5 5" /><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  )
}

export function Amounts({ s }) {
  const lines = [
    ['Цена выше ориентира', s.overpay_price],
    ['Перерасход материалов', s.overpay_volume],
    ['Удорожание сверх индекса', s.overpay_escalation],
  ].filter(([, v]) => v > 0)
  if (!lines.length) return <><b className="money">0 ₽</b><span className="xs muted">превышений не выявлено</span></>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {lines.map(([l, v], i) => (
        <div key={l}><div className="xs muted">{l}</div><div className={i === 0 ? 'money' : ''} style={i ? { fontWeight: 700 } : undefined}>{rub(v)}</div></div>
      ))}
      {lines.length > 1 && <div className="xs muted">суммы не складываются: позиция может дать сигналы разных видов</div>}
    </div>
  )
}
