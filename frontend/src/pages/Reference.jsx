import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { RegionSelect, SourceTag, useRef_ } from '../components/common.jsx'
import { date, money, quarterLabel } from '../format.js'

const KIND_LABEL = { prices: 'Цены', indexes: 'Индексы', analogs: 'Объекты-аналоги', resources: 'Классификатор ресурсов' }

export default function Reference() {
  const { meta, regions, reload, user } = useRef_()
  const [regionId, setRegionId] = useState(null)
  const [zoneId, setZoneId] = useState('')
  const [quarter, setQuarter] = useState('2026-Q3')
  const [rows, setRows] = useState(null)
  const [found, setFound] = useState(null)
  const [q, setQ] = useState('')
  const [applied, setApplied] = useState('')
  const [error, setError] = useState('')
  const [kind, setKind] = useState('prices')
  const [file, setFile] = useState(null)
  const [importMsg, setImportMsg] = useState(null)

  useEffect(() => { if (!regionId && regions.length) setRegionId(regions[0].id) }, [regions, regionId])
  const region = regions.find((r) => r.id === regionId)
  useEffect(() => { setZoneId(region?.zones?.[0]?.id ?? '') }, [regionId]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!regionId) return
    const p = new URLSearchParams({ region_id: regionId, quarter, limit: 100 })
    if (zoneId) p.set('zone_id', zoneId)
    if (applied) p.set('q', applied)
    setRows(null)
    api.prices(p).then((r) => { setRows(r.items); setFound(r) }).catch((e) => setError(e.message))
  }, [regionId, zoneId, quarter, applied])

  const upload = async (e) => {
    e.preventDefault()
    if (!file) return setImportMsg({ ok: false, text: 'Выберите CSV-файл' })
    const form = new FormData()
    form.append('kind', kind)
    form.append('file', file)
    try {
      const r = await api.importRef(form)
      setImportMsg({ ok: true, text: `Загружено записей: ${r.records}${r.version ? `, версия ${r.version}` : ''}` })
      reload()
    } catch (err) {
      setImportMsg({ ok: false, text: err.message })
    }
  }

  return (
    <div className="page">
      <h1>Справочники цен</h1>
      <div className="card section">
        <div className="grid-auto">
          <div className="field"><label htmlFor="r">Регион</label><RegionSelect id="r" value={regionId} onChange={setRegionId} regions={regions} /></div>
          <div className="field"><label htmlFor="z">Ценовая зона</label>
            <select id="z" className="select" value={zoneId} onChange={(e) => setZoneId(e.target.value ? Number(e.target.value) : '')}>
              {region?.zones?.length ? region.zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>) : <option value="">Зоны не загружены</option>}
            </select></div>
          <div className="field"><label htmlFor="q">Квартал</label>
            <select id="q" className="select" value={quarter} onChange={(e) => setQuarter(e.target.value)}>
              {(meta?.quarters ?? []).map((q) => <option key={q} value={q}>{quarterLabel(q)}</option>)}
            </select></div>
        </div>
        <form className="row" role="search" onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()) }}>
          <label htmlFor="rq" className="sr-only">Поиск ресурса</label>
          <input id="rq" type="search" className="input" style={{ flex: '1 1 320px', width: 'auto' }} placeholder="Код КСР или часть наименования: бетон, 08.4.03, кабель АВВГ"
            value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit" className="btn secondary">Найти</button>
        </form>
        <div className="hint">
          {found && <>Ресурсов с ценами в регионе: {found.total_region}; найдено: {found.found}{found.found > 100 ? ', показаны первые 100' : ''}. </>}
          Значение каждого источника приведено к выбранному кварталу индексом по сметным ценам ФГИС ЦС; ориентир — медиана источников.
          Сметные цены ФГИС ЦС — реальные, ЕИС и рынок — синтетические.
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="table-wrap">
          {rows && rows.length === 0 ? (
            <div className="section"><div className="note">{applied ? 'Ничего не найдено.' : `Для региона «${region?.name}» цены не загружены. Загрузите выгрузку ФГИС ЦС, контракты ЕИС или прайс-листы в формате CSV ниже.`}</div></div>
          ) : (
            <table className="data" style={{ minWidth: 860 }}>
              <thead><tr><th scope="col">Код</th><th scope="col">Ресурс</th><th scope="col">Ед.</th>
                <th scope="col" className="num">ФГИС ЦС, ₽<div><SourceTag synthetic={false} /></div></th><th scope="col" className="num">ЕИС, ₽<div><SourceTag synthetic /></div></th><th scope="col" className="num">Рынок, ₽<div><SourceTag synthetic /></div></th><th scope="col" className="num">Ориентир, ₽</th></tr></thead>
              <tbody>
                {!rows && <tr><td colSpan={7} className="muted">Загрузка…</td></tr>}
                {rows?.map((r) => (
                  <tr key={r.code}>
                    <td>{r.code}</td><td><div style={{ fontWeight: 600 }}>{r.name}</div><div className="xs muted">{r.group}</div></td><td>{r.unit}</td>
                    <td className="num">{money(r.sources.fgiscs?.value)}{r.sources.fgiscs && r.sources.fgiscs.quarter !== quarter && <div className="xs muted">из {r.sources.fgiscs.quarter}</div>}</td>
                    <td className="num">{money(r.sources.eis?.value)}{r.sources.eis && <div className="xs muted">медиана {r.sources.eis.count}</div>}</td>
                    <td className="num">{money(r.sources.market?.value)}{r.sources.market && <div className="xs muted">медиана {r.sources.market.count}</div>}</td>
                    <td className="num" style={{ fontWeight: 700 }}>{money(r.benchmark)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="cols">
        <section className="card section main">
          <h2>Загрузка справочника</h2>
          {user?.role !== 'admin' && <div className="note">Загрузка справочников доступна администратору справочников.</div>}
          <form onSubmit={upload} hidden={user?.role !== 'admin'} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="grid-auto">
              <div className="field"><label htmlFor="kind">Вид данных</label>
                <select id="kind" className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
                  {Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select></div>
              <div className="field"><label htmlFor="csv">CSV-файл (UTF-8, разделитель «,» или «;»)</label>
                <input id="csv" type="file" accept=".csv" className="input" style={{ paddingTop: 9 }} onChange={(e) => setFile(e.target.files[0])} /></div>
            </div>
            <div className="hint">
              {kind === 'prices' && 'Колонки: source (fgiscs, eis, market), ksr_code, region, zone, quarter (2026-Q3), price, doc_ref, doc_url; для нового ресурса — name и unit.'}
              {kind === 'indexes' && 'Колонки: region, group, quarter, value.'}
              {kind === 'analogs' && 'Колонки: region, object_type, name, capacity, ksr_code, consumption_per_m2, doc_ref.'}
              {kind === 'resources' && 'Колонки: ksr_code, name, unit, group, attributes.'}
              {' '}Каждая загрузка становится новой версией набора данных и записывается в последующие проверки.
            </div>
            {importMsg && <div className={importMsg.ok ? 'success' : 'error'} role="status">{importMsg.text}</div>}
            <div><button type="submit" className="btn">Загрузить</button></div>
          </form>
        </section>
        <section className="card section side" style={{ maxWidth: 420 }}>
          <h2>Версии наборов данных</h2>
          {(meta?.datasets ?? []).map((d) => (
            <div key={d.code} className="small" style={{ borderTop: '1px solid var(--line-soft)', paddingTop: 8 }}>
              <b>{d.code}</b> · {KIND_LABEL[d.kind]} · {d.records} записей{d.is_demo ? ' · демо' : ''}
              <div className="xs muted">{d.source_file} · {date(d.loaded_at)}</div>
              <div className="mono muted">{d.sha256}</div>
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}
