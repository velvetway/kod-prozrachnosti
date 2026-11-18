import { createContext, useContext, useEffect, useState } from 'react'
import { NavLink, Link, Outlet } from 'react-router-dom'
import { api } from '../api.js'
import { LEVELS, rub } from '../format.js'

const RefContext = createContext({ meta: null, regions: [] })
export const useRef_ = () => useContext(RefContext)

function Login({ onDone }) {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try { onDone(await api.login(login, password)) } catch (err) { setError(err.message) }
  }
  return (
    <div className="page narrow" style={{ maxWidth: 460, paddingTop: 48 }}>
      <form className="card section" onSubmit={submit}>
        <h1 style={{ fontSize: 22 }}>Вход в систему</h1>
        <div className="field"><label htmlFor="login">Логин</label>
          <input id="login" className="input" autoComplete="username" value={login} onChange={(e) => setLogin(e.target.value)} /></div>
        <div className="field"><label htmlFor="password">Пароль</label>
          <input id="password" type="password" className="input" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        {error && <div className="error" role="alert">{error}</div>}
        <button type="submit" className="btn">Войти</button>
        <div className="hint">Учётные записи прототипа: specialist / specialist — специалист по профилактике; admin / admin — администратор справочников. В рабочей установке задаются переменной APP_USERS.</div>
      </form>
    </div>
  )
}

export function Layout() {
  const [user, setUser] = useState(undefined)
  const [meta, setMeta] = useState(null)
  const [regions, setRegions] = useState([])
  const [error, setError] = useState('')
  const reload = () => Promise.all([api.meta(), api.regions()])
    .then(([m, r]) => { setMeta(m); setRegions(r) })
    .catch((e) => setError(e.message))
  useEffect(() => {
    api.me().then((u) => { setUser(u); reload() }).catch(() => setUser(null))
    const onAuth = () => setUser(null)
    window.addEventListener('auth-required', onAuth)
    return () => window.removeEventListener('auth-required', onAuth)
  }, [])
  const logout = async () => { await api.logout().catch(() => {}); setUser(null) }

  return (
    <RefContext.Provider value={{ meta, regions, reload, user }}>
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
          {user && (
            <div className="user row" style={{ gap: 8, flexWrap: 'nowrap' }}>
              <span title={user.name}>{user.role_title} ({user.login})</span>
              <button type="button" className="btn link" style={{ color: '#fff', minHeight: 32, padding: '0 4px' }} onClick={logout}>Выйти</button>
            </div>
          )}
        </div>
      </header>
      {user && meta?.is_demo && (
        <div className="demo-banner" role="note">
          <div><b>Данные прототипа.</b> Сметные цены ФГИС ЦС — реальные, выгружены с портала fgiscs.minstroyrf.ru
            (Брянская и Томская области, IV кв. 2024 — III кв. 2026). Контракты ЕИС, рыночные предложения,
            объекты-аналоги и демо-сметы — синтетические: выводы по ним не являются подтверждёнными.</div>
        </div>
      )}
      {user === null && <Login onDone={(u) => { setUser(u); setError(''); reload() }} />}
      {user && error && <div className="page"><div className="error">Сервер недоступен: {error}</div></div>}
      {user && <Outlet />}
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

export function SourceTag({ synthetic }) {
  return synthetic
    ? <span className="badge gray" title="Сгенерированы для демонстрации">синтетические</span>
    : <span className="badge ok" title="Выгружены с портала ФГИС ЦС">реальные данные</span>
}
