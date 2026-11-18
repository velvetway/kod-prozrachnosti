import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Amounts, Badge, RegionSelect, useRef_ } from '../components/common.jsx'
import { MAX_LEVEL, date, quarterLabel } from '../format.js'

const LEVEL_FILTERS = [['high', 'Высокий'], ['medium', 'Средний'], ['review', 'Проверить сопоставление'], ['none', 'Без сигналов']]
const STATUS_FILTERS = ['Ожидает решения', 'Решение принято', 'Без сигналов']

export default function Registry() {
  const { regions } = useRef_()
  const [checks, setChecks] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [region, setRegion] = useState(null)
  const [levels, setLevels] = useState([])
  const [statuses, setStatuses] = useState([])

  useEffect(() => {
    const p = new URLSearchParams()
    if (applied) p.set('q', applied)
    if (region) p.set('region_id', region)
    levels.forEach((l) => p.append('level', l))
    statuses.forEach((s) => p.append('status', s))
    api.checks(p).then(setChecks).catch((e) => setError(e.message))
  }, [applied, region, levels, statuses])

  const toggle = (list, setList, value) => setList(list.includes(value) ? list.filter((x) => x !== value) : [...list, value])
  const filtered = applied || region || levels.length || statuses.length

  return (
    <>
      <div className="band">
        <div className="page" style={{ paddingBottom: 24 }}>
          <div className="row between">
            <h1>Реестр проверок</h1>
            <Link to="/checks/new" className="btn">Новая проверка</Link>
          </div>
          <form className="row" onSubmit={(e) => { e.preventDefault(); setApplied(query.trim()) }} role="search">
            <label htmlFor="q" className="sr-only">Поиск по проверкам</label>
            <input id="q" type="search" className="input" style={{ flex: '1 1 320px', width: 'auto' }}
              placeholder="Номер проверки, объект, материал или код КСР" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="btn secondary" type="submit">Найти</button>
          </form>
        </div>
      </div>

      <div className="page">
        <div className="cols">
          <aside aria-label="Фильтры" className="card side filters">
            <h2 style={{ fontSize: 16 }}>Параметры поиска</h2>
            <div className="field">
              <label htmlFor="region">Регион</label>
              <RegionSelect id="region" value={region} onChange={setRegion} regions={regions} allowAll />
            </div>
            <fieldset>
              <legend className="legend" style={{ paddingBottom: 6 }}>Уровень сигнала</legend>
              {LEVEL_FILTERS.map(([v, l]) => (
                <label key={v} className="check"><input type="checkbox" checked={levels.includes(v)} onChange={() => toggle(levels, setLevels, v)} /> {l}</label>
              ))}
            </fieldset>
            <fieldset>
              <legend className="legend" style={{ paddingBottom: 6 }}>Статус</legend>
              {STATUS_FILTERS.map((s) => (
                <label key={s} className="check"><input type="checkbox" checked={statuses.includes(s)} onChange={() => toggle(statuses, setStatuses, s)} /> {s}</label>
              ))}
            </fieldset>
            {filtered ? (
              <button type="button" className="btn secondary" onClick={() => { setRegion(null); setLevels([]); setStatuses([]); setQuery(''); setApplied('') }}>
                Сбросить фильтры
              </button>
            ) : null}
          </aside>

          <main className="main">
            {error && <div className="error">{error}</div>}
            {checks && (
              <div className="row between small muted">
                <div>Найдено проверок: {checks.length}</div>
                <div>Сначала новые</div>
              </div>
            )}
            {checks && checks.length === 0 && (
              <div className="card empty">
                <h2>{filtered ? 'По заданным условиям проверок нет' : 'Проверок пока нет'}</h2>
                <p className="muted" style={{ margin: 0 }}>
                  Загрузите смету или спецификацию. Для знакомства с системой на странице новой проверки есть три демо-сметы.
                </p>
                <Link to="/checks/new" className="btn">Новая проверка</Link>
              </div>
            )}
            {checks?.map((c) => {
              const [lvl, label] = MAX_LEVEL[c.summary.max_level]
              const s = c.summary
              return (
                <article key={c.id} className="card check-card">
                  <div className="body">
                    <div className="row xs muted" style={{ gap: 10 }}>
                      <span>Проверка № {c.number}</span>
                      <Badge level={lvl}>{label}</Badge>
                      {c.is_demo && <Badge level="gray">Демо-данные</Badge>}
                    </div>
                    <Link to={`/checks/${c.id}`} className="title">{c.title}</Link>
                    <div className="small muted">
                      {c.region}{c.zone ? `, зона ${c.zone.number}` : ''} · цены {quarterLabel(c.quarter)} · {date(c.created_at)}
                    </div>
                    <div className="small">
                      Позиций: {s.items} · сопоставлено: {s.matched} · сигналов: {s.high + s.medium + s.review}
                      {s.high + s.medium + s.review > 0 && ` · решений: ${s.decided}`}
                    </div>
                  </div>
                  <div className="aside">
                    <Amounts s={s} />
                    <div className="xs muted">Статус: {c.status.toLowerCase()}</div>
                  </div>
                </article>
              )
            })}
          </main>
        </div>
      </div>
    </>
  )
}
