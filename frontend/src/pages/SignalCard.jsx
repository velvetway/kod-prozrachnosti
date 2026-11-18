import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, Loading, SourceTag, useRef_ } from '../components/common.jsx'
import { KINDS, date, money, num, pct, qty, quarterLabel } from '../format.js'

function PriceBlock({ s, item }) {
  const d = s.details
  return (
    <>
      <section className="card section">
        <h2>Расчёт отклонения цены</h2>
        <div className="formula">
          <div>Отклонение = (цена за ед. ресурса − ориентир) / ориентир × 100 %</div>
          <div style={{ fontWeight: 700 }}>{s.formula}</div>
          <div>Превышение по позиции: {d.overpay_formula}</div>
        </div>
        <div className="hint">
          Цена в документе {money(item.price)} ₽ за {item.unit}
          {item.match.unit_factor !== 1 && ` = ${money(s.actual)} ₽ за ${d.unit} (пересчёт единиц ×${item.match.unit_factor})`}.
          Ориентир {money(s.benchmark)} ₽ — {d.method}. Пороги: средний {d.thresholds[0]} %, высокий {d.thresholds[1]} %.
        </div>
        {d.notes?.map((n) => <div key={n} className="note">{n}</div>)}
      </section>
      <section className="card section">
        <h2>Источники цены</h2>
        <div className="table-wrap">
          <table className="data" style={{ minWidth: 640 }}>
            <thead>
              <tr><th scope="col">Источник</th><th scope="col">Документ</th><th scope="col">Квартал</th>
                <th scope="col" className="num">Цена, ₽</th><th scope="col" className="num">Индекс</th><th scope="col" className="num">К кварталу проверки, ₽</th></tr>
            </thead>
            <tbody>
              {d.sources.map((src) => src.rows.map((r, i) => (
                <tr key={`${src.source}-${i}`}>
                  <td>{i === 0 && <><div style={{ fontWeight: 600 }}>{src.title}</div><div className="xs muted">значение источника {money(src.value)} ₽{src.count > 1 ? `, медиана ${src.count}` : ''}</div><div style={{ marginTop: 4 }}><SourceTag synthetic={src.synthetic} /></div></>}</td>
                  <td>{r.doc_url ? <a href={r.doc_url} target="_blank" rel="noreferrer">{r.doc_ref}</a> : r.doc_ref}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>{r.quarter}</td>
                  <td className="num">{money(r.price)}</td>
                  <td className="num">{num(r.index, 4)}{r.index !== 1 && r.index_basis && <div className="xs muted" style={{ whiteSpace: 'normal', minWidth: 140 }}>{r.index_basis}</div>}</td>
                  <td className="num">{money(r.indexed)}</td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
        {d.sources.some((x) => x.note) && <div className="note">{d.sources.filter((x) => x.note).map((x) => `${x.title}: ${x.note}`).join('; ')}</div>}
      </section>
    </>
  )
}

function VolumeBlock({ s, check }) {
  const d = s.details
  return (
    <>
      <section className="card section">
        <h2>Расчёт отклонения расхода</h2>
        <div className="formula"><div style={{ fontWeight: 700 }}>{s.formula}</div><div>Стоимость перерасхода: {d.overpay_formula}</div></div>
        <div className="note">Удельные расходы объектов-аналогов в прототипе синтетические.</div>
        <div className="hint">Объект: {check.object_type}, {num(check.capacity, 0)} м². Медиана {num(d.median, 4)} {d.unit}/м², коридор {num(d.low, 4)}–{num(d.high, 4)}; {d.scope}. Пороги: {d.thresholds.join(' / ')} %.</div>
      </section>
      <section className="card section">
        <h2>Объекты-аналоги</h2>
        <div className="table-wrap">
          <table className="data" style={{ minWidth: 560 }}>
            <thead><tr><th scope="col">Объект</th><th scope="col">Реквизит</th><th scope="col" className="num">Мощность, м²</th><th scope="col" className="num">Расход на 1 м²</th></tr></thead>
            <tbody>{d.analogs.map((a) => (
              <tr key={a.doc_ref}><td>{a.name}</td><td className="muted">{a.doc_ref}</td><td className="num">{num(a.capacity, 0)}</td><td className="num">{num(a.per_m2, 4)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function EscalationBlock({ s, item }) {
  const d = s.details
  return (
    <section className="card section">
      <h2>Расчёт удорожания</h2>
      <div className="formula"><div style={{ fontWeight: 700 }}>{s.formula}</div><div>Сумма сверх индекса: {d.overpay_formula}</div></div>
      <div className="hint">Исходная цена {money(d.base_price)} ₽ ({quarterLabel(d.base_quarter)}), новая {money(item.price)} ₽. Индекс группы «{d.group}» за период {num(d.index, 4)}. Пороги: {d.thresholds.join(' / ')} %.</div>
    </section>
  )
}

export default function SignalCard() {
  const { id } = useParams()
  const { meta } = useRef_()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [outcome, setOutcome] = useState('')
  const [comment, setComment] = useState('')
  const [saved, setSaved] = useState('')

  const load = useCallback(() => api.signal(id).then((d) => { setData(d); setOutcome(d.signal.decisions.at(-1)?.outcome ?? '') }).catch((e) => setError(e.message)), [id])
  useEffect(() => { load() }, [load])

  if (error) return <div className="page"><div className="error">{error}</div></div>
  if (!data) return <Loading />
  const { signal: s, item, check } = data
  const m = item.match
  const other = item.signals.filter((x) => x.id !== s.id && !['nomatch', 'nodata'].includes(x.level))

  const save = async (e) => {
    e.preventDefault()
    if (!outcome) return setError('Выберите итог проверки сигнала')
    await api.decide(s.id, outcome, comment)
    setComment('')
    setSaved('Решение записано в журнал')
    load()
  }

  return (
    <div className="page">
      <div className="crumbs"><Link to="/">Реестр проверок</Link> / <Link to={`/checks/${check.id}`}>Проверка № {check.number}</Link> / {KINDS[s.kind]}</div>
      <div className="row" style={{ gap: 12 }}>
        <h1 style={{ fontSize: 24 }}>{item.name}</h1>
        <Badge level={s.level}>{KINDS[s.kind]}: {({ high: 'высокий сигнал', medium: 'средний сигнал', review: 'проверить сопоставление', none: 'в пределах порога' })[s.level]}{s.deviation_pct != null ? ` · ${pct(s.deviation_pct)}` : ''}</Badge>
      </div>
      <div className="small muted">
        Позиция {item.position} (строка {item.row} документа) · {qty(item.quantity)} {item.unit} по {money(item.price)} ₽ · {check.region}{check.zone ? `, зона ${check.zone.number}` : ''} · {quarterLabel(check.quarter)}
      </div>

      <div className="cols">
        <main className="main">
          {s.kind === 'price' && <PriceBlock s={s} item={item} />}
          {s.kind === 'volume' && <VolumeBlock s={s} check={check} />}
          {s.kind === 'escalation' && <EscalationBlock s={s} item={item} />}

          <section className="card section">
            <h2>Сопоставимость</h2>
            <div className="grid-auto">
              <div><div className="xs muted">Ресурс классификатора</div><div style={{ fontWeight: 600 }}>{m.resource.code} {m.resource.name}</div><div className="xs muted">ед. {m.resource.unit} · группа «{m.resource.group}»</div></div>
              <div><div className="xs muted">Сопоставимость</div><div style={{ fontWeight: 600 }}>{m.level}{m.method !== 'manual' ? ` (${num(m.score, 2)})` : ''}</div><div className="xs muted">{m.note}</div></div>
              <div><div className="xs muted">Версия ценовых данных</div><div style={{ fontWeight: 600 }}>{check.data_versions.prices?.code}</div><div className="xs muted">повторный расчёт на тех же данных даёт тот же результат</div></div>
            </div>
            {m.level === 'Низкая' && <div className="note">Сопоставимость низкая: перед решением убедитесь, что ресурс подобран верно. Уточнить сопоставление можно на странице проверки.</div>}
          </section>

          {other.length > 0 && (
            <section className="card section">
              <h2>Другие виды контроля по позиции</h2>
              <div className="row" style={{ gap: 16 }}>
                {other.map((o) => <Link key={o.id} to={`/signals/${o.id}`}>{KINDS[o.kind]}: {pct(o.deviation_pct)} <Badge level={o.level} /></Link>)}
              </div>
            </section>
          )}
        </main>

        <aside aria-label="Решение специалиста" className="card side section" style={{ maxWidth: 380 }}>
          <h2>Решение специалиста</h2>
          <form onSubmit={save} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <fieldset>
              <legend className="legend" style={{ paddingBottom: 6 }}>Итог проверки сигнала</legend>
              {(meta?.decisions ?? []).map((d) => (
                <label key={d} className="check"><input type="radio" name="outcome" checked={outcome === d} onChange={() => { setOutcome(d); setSaved('') }} /> {d}</label>
              ))}
            </fieldset>
            <div className="field">
              <label htmlFor="comment">Комментарий</label>
              <textarea id="comment" className="textarea" rows={4} placeholder="Основание решения, запрошенные документы" value={comment} onChange={(e) => setComment(e.target.value)} />
            </div>
            <button type="submit" className="btn" style={{ minHeight: 48 }}>Сохранить в журнал</button>
            {saved && <div className="success" role="status">{saved}</div>}
          </form>
          {s.decisions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="legend">История решений</div>
              {s.decisions.slice().reverse().map((d) => (
                <div key={d.id} className="small" style={{ borderTop: '1px solid var(--line-soft)', paddingTop: 8 }}>
                  <b>{d.outcome}</b><div className="xs muted">{date(d.at)} · {d.author}</div>{d.comment && <div>{d.comment}</div>}
                </div>
              ))}
            </div>
          )}
          <div className="note">Сигнал показывает позицию, требующую проверки. Вывод о нарушении и о действиях должностных лиц система не делает.</div>
        </aside>
      </div>
    </div>
  )
}
