import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, reportUrl } from '../api.js'
import { Amounts, Badge, Loading } from '../components/common.jsx'
import { KINDS, devClass, money, num, pct, qty, quarterLabel, rub } from '../format.js'

const sig = (item, kind) => item.signals.find((s) => s.kind === kind)

function MatchCell({ item, onPick }) {
  const m = item.match
  if (!m?.resource) {
    return (
      <>
        <div className="muted">не сопоставлено</div>
        <button type="button" className="btn link" style={{ minHeight: 32, padding: 0 }} onClick={() => onPick(item)}>Подобрать вручную</button>
      </>
    )
  }
  return (
    <>
      <div>{m.resource.code}</div>
      <div className="xs muted">{m.level}{m.method !== 'manual' ? ` · ${num(m.score, 2)}` : ''}</div>
      {(m.level === 'Низкая' || m.level === 'Средняя') && (
        <button type="button" className="btn link" style={{ minHeight: 32, padding: 0 }} onClick={() => onPick(item)}>Уточнить</button>
      )}
    </>
  )
}

function SignalLink({ s, label = 'Карточка' }) {
  if (!s || s.level === 'nomatch' || s.level === 'nodata') return null
  return <Link to={`/signals/${s.id}`} style={{ display: 'inline-flex', alignItems: 'center', minHeight: 44, fontWeight: 600 }}
    aria-label={`${label}: ${KINDS[s.kind]}`}>{['high', 'medium', 'review'].includes(s.level) ? 'Карточка' : 'Расчёт'}</Link>
}

function PriceTable({ items, onPick }) {
  return (
    <table className="data" style={{ minWidth: 960 }}>
      <thead>
        <tr>
          <th scope="col">№</th><th scope="col" style={{ minWidth: 240 }}>Материал</th><th scope="col" className="num">Кол-во</th>
          <th scope="col" className="num">Цена в смете, ₽</th><th scope="col">Ресурс КСР</th>
          <th scope="col" className="num">Ориентир, ₽</th>
          <th scope="col" className="num">Отклонение</th><th scope="col">Сигнал</th><th scope="col"><span className="sr-only">Действие</span></th>
        </tr>
      </thead>
      <tbody>
        {items.map((it) => {
          const s = sig(it, 'price')
          const unitRes = it.match?.resource?.unit
          return (
            <tr key={it.id}>
              <td>{it.position}</td>
              <td><div style={{ fontWeight: 600 }}>{it.name}</div>{it.code && it.code !== it.match?.resource?.code && <div className="xs muted">код в документе {it.code}</div>}</td>
              <td className="num">{qty(it.quantity)} {it.unit}</td>
              <td className="num">{money(it.price)}
                {s?.actual != null && it.match.unit_factor !== 1 && <div className="xs muted">= {money(s.actual)} за {unitRes}</div>}</td>
              <td><MatchCell item={it} onPick={onPick} /></td>
              <td className="num">{money(s?.benchmark)}{s?.benchmark != null && <div className="xs muted">за {unitRes}</div>}</td>
              <td className={`num ${devClass(s?.level)}`}>{pct(s?.deviation_pct)}</td>
              <td><Badge level={s?.level ?? 'nodata'} /></td>
              <td><SignalLink s={s} /></td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function VolumeTable({ items, check }) {
  if (!check.object_type || !check.capacity) {
    return <div className="section"><div className="note">Контроль объёмов не выполнялся: при запуске проверки не указаны тип и мощность объекта.</div></div>
  }
  const rows = items.filter((it) => sig(it, 'volume'))
  return (
    <>
      <div className="section" style={{ paddingBottom: 0 }}>
        <div className="hint">{check.object_type}, {num(check.capacity, 0)} м². Расход позиции на 1 м² сравнивается с медианой объектов-аналогов того же типа.
          {rows.length < items.length && ` Для ${items.length - rows.length} поз. нет данных объектов-аналогов.`}</div>
      </div>
      <table className="data" style={{ minWidth: 900 }}>
        <thead>
          <tr>
            <th scope="col">№</th><th scope="col">Материал</th><th scope="col" className="num">Кол-во в ед. ресурса</th>
            <th scope="col" className="num">Расход на 1 м²</th><th scope="col" className="num">Медиана аналогов</th>
            <th scope="col" className="num">Коридор аналогов</th><th scope="col" className="num">Отклонение</th><th scope="col">Сигнал</th>
            <th scope="col"><span className="sr-only">Действие</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((it) => {
            const s = sig(it, 'volume')
            const u = it.match.resource.unit
            return (
              <tr key={it.id}>
                <td>{it.position}</td>
                <td style={{ fontWeight: 600 }}>{it.name}</td>
                <td className="num">{qty(it.quantity * it.match.unit_factor)} {u}</td>
                <td className="num">{num(s.actual, 4)}</td>
                <td className="num">{num(s.benchmark, 4)}</td>
                <td className="num">{s.corridor ? `${num(s.corridor[0], 4)}–${num(s.corridor[1], 4)}` : '—'}</td>
                <td className={`num ${devClass(s.level)}`}>{pct(s.deviation_pct)}</td>
                <td><Badge level={s.level} /></td>
                <td><SignalLink s={s} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </>
  )
}

function EscalationTable({ items, check }) {
  const rows = items.filter((it) => sig(it, 'escalation'))
  if (!check.base_quarter || !rows.length) {
    return <div className="section"><div className="note">Проверка удорожания не выполнялась: в документе нет колонки «Исходная цена» или не указан квартал исходных цен.</div></div>
  }
  return (
    <>
      <div className="section" style={{ paddingBottom: 0 }}>
        <div className="hint">Рост цены от исходной ({quarterLabel(check.base_quarter)}) сравнивается с индексом цен группы ресурсов за тот же период.</div>
      </div>
      <table className="data" style={{ minWidth: 900 }}>
        <thead>
          <tr>
            <th scope="col">№</th><th scope="col">Материал</th><th scope="col" className="num">Исходная цена, ₽</th>
            <th scope="col" className="num">Новая цена, ₽</th><th scope="col" className="num">Заявленный рост</th>
            <th scope="col" className="num">Рост по индексу</th><th scope="col" className="num">Сверх индекса</th><th scope="col">Сигнал</th>
            <th scope="col"><span className="sr-only">Действие</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((it) => {
            const s = sig(it, 'escalation')
            return (
              <tr key={it.id}>
                <td>{it.position}</td>
                <td style={{ fontWeight: 600 }}>{it.name}</td>
                <td className="num">{money(it.base_price)}</td>
                <td className="num">{money(it.price)}</td>
                <td className="num">{pct(s.actual)}</td>
                <td className="num">{pct(s.benchmark)}</td>
                <td className={`num ${devClass(s.level)}`}>{pct(s.deviation_pct)}</td>
                <td><Badge level={s.level} /></td>
                <td><SignalLink s={s} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </>
  )
}

function MatchDialog({ item, onClose, onDone }) {
  const [cands, setCands] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.candidates(item.id).then(setCands).catch((e) => setError(e.message)) }, [item.id])
  const choose = async (c) => {
    try { await api.setMatch(item.id, c.id); onDone() } catch (e) { setError(e.message) }
  }
  return (
    <div className="modal-back" role="presentation" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="mtitle" onClick={(e) => e.stopPropagation()}>
        <h2 id="mtitle">Сопоставление позиции</h2>
        <div><b>{item.name}</b> <span className="muted">· {item.unit}</span></div>
        <div className="hint">Кандидаты с совместимой единицей измерения, по убыванию сопоставимости. Выбор фиксируется как ручное сопоставление и попадает в отчёт.</div>
        {error && <div className="error">{error}</div>}
        {!cands && !error && <div className="muted">Загрузка…</div>}
        {cands?.length === 0 && <div className="note">Нет ресурсов с совместимой единицей измерения.</div>}
        <div>
          {cands?.map((c) => (
            <div key={c.id} className="cand">
              <div style={{ flex: '1 1 360px' }}>
                <div style={{ fontWeight: 600 }}>{c.code} {c.name}</div>
                <div className="xs muted">ед. {c.unit} · сопоставимость {num(c.score, 2)} ({c.level.toLowerCase()})</div>
              </div>
              <button type="button" className="btn secondary" onClick={() => choose(c)}>Выбрать</button>
            </div>
          ))}
        </div>
        <div><button type="button" className="btn link" onClick={onClose}>Закрыть</button></div>
      </div>
    </div>
  )
}

export default function Results() {
  const { id } = useParams()
  const location = useLocation()
  const [check, setCheck] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('price')
  const [picking, setPicking] = useState(null)
  const [rerun, setRerun] = useState(null)
  const warnings = location.state?.warnings ?? []

  const load = useCallback(() => api.check(id).then(setCheck).catch((e) => setError(e.message)), [id])
  useEffect(() => { load() }, [load])

  if (error) return <div className="page"><div className="error">{error}</div></div>
  if (!check) return <Loading />
  const s = check.summary
  const counts = (kind) => check.items.filter((it) => ['high', 'medium', 'review'].includes(sig(it, kind)?.level)).length

  return (
    <div className="page">
      <div className="crumbs"><Link to="/">Реестр проверок</Link> / Проверка № {check.number}</div>
      <div className="row between" style={{ alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 480px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <h1 style={{ fontSize: 24 }}>{check.title}</h1>
          <div className="small muted">
            {check.region}{check.zone ? ` · ${check.zone.name}` : ''} · цены {quarterLabel(check.quarter)}
            {check.object_type ? ` · ${check.object_type.toLowerCase()}, ${num(check.capacity, 0)} м²` : ''} · {check.file_name}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className="btn secondary" onClick={async () => setRerun(await api.rerun(check.id).then((r) => { load(); return r }))}>Повторить расчёт</button>
          <a className="btn" href={reportUrl(check.id)}>Скачать отчёт DOCX</a>
        </div>
      </div>

      {warnings.length > 0 && <div className="note"><b>При разборе документа:</b><ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>{warnings.map((w) => <li key={w}>{w}</li>)}</ul></div>}
      {rerun && (
        <div className={rerun.identical ? 'success' : 'error'} role="status">
          {rerun.identical ? 'Повторный расчёт дал идентичный результат: контрольная сумма совпала.' : 'Результат изменился: справочники или сопоставления обновились после первой проверки.'}
          <div className="mono" style={{ marginTop: 4 }}>{rerun.after}</div>
        </div>
      )}

      <div className="tiles">
        <div className="card tile"><span className="xs muted">Позиций в документе</span><b>{s.items}</b></div>
        <div className="card tile"><span className="xs muted">Сопоставлено с ориентиром</span><b>{s.matched} из {s.items}</b></div>
        <div className="card tile"><span className="xs muted">Сигналы</span><b>{s.high + s.medium + s.review}</b>
          <span className="xs muted">высоких {s.high}, средних {s.medium}{s.review ? `, проверить сопоставление ${s.review}` : ''}</span></div>
        <div className="card tile"><span className="xs muted">Суммы по сигналам</span><Amounts s={s} /></div>
      </div>

      <div className="card">
        <div role="tablist" aria-label="Виды контроля" className="tabs">
          {['price', 'volume', 'escalation'].map((k) => (
            <button key={k} type="button" role="tab" className="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
              {k === 'price' ? 'Цена позиций' : k === 'volume' ? 'Объёмы на 1 м²' : 'Удорожание по индексам'}
              {counts(k) > 0 && <span className="badge high" style={{ marginLeft: 8 }}>{counts(k)}</span>}
            </button>
          ))}
        </div>
        <div className="table-wrap" role="tabpanel">
          {tab === 'price' && <PriceTable items={check.items} onPick={setPicking} />}
          {tab === 'volume' && <VolumeTable items={check.items} check={check} />}
          {tab === 'escalation' && <EscalationTable items={check.items} check={check} />}
        </div>
      </div>

      <div className="hint">
        Ориентир — медиана значений источников ({check.params.sources.map((x) => ({ fgiscs: 'ФГИС ЦС', eis: 'ЕИС', market: 'рынок' })[x]).join(', ')}),
        приведённых к кварталу проверки индексом цен. Пороги цены {check.params.price_thresholds.join(' / ')} %. Сигнал указывает на позицию для проверки и не является выводом о нарушении.
      </div>

      <details className="card section">
        <summary>Версии данных и контрольные суммы</summary>
        <div className="small" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div>Документ: <span className="mono">{check.file_sha256}</span></div>
          {Object.entries(check.data_versions).map(([k, v]) => (
            <div key={k}>{({ prices: 'Цены', indexes: 'Индексы', analogs: 'Объекты-аналоги' })[k]}: {v.code}{v.is_demo ? ' (демо)' : ''} · <span className="mono">{v.sha256}</span></div>
          ))}
          <div>Результат: <span className="mono">{check.result_sha256}</span></div>
        </div>
      </details>

      {picking && <MatchDialog item={picking} onClose={() => setPicking(null)} onDone={() => { setPicking(null); load() }} />}
    </div>
  )
}

