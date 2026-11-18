import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { RegionSelect, UploadIcon, useRef_ } from '../components/common.jsx'
import { quarterLabel } from '../format.js'

const SOURCES = [['fgiscs', 'Сметные цены ФГИС ЦС'], ['eis', 'Контракты-аналоги ЕИС'], ['market', 'Рыночные предложения']]

export default function NewCheck() {
  const { meta, regions, reload } = useRef_()
  const navigate = useNavigate()
  const fileInput = useRef(null)
  const pendingZone = useRef(null)
  const [file, setFile] = useState(null)
  const [over, setOver] = useState(false)
  const [regionId, setRegionId] = useState(null)
  const [zoneId, setZoneId] = useState('')
  const [quarter, setQuarter] = useState('2026-Q3')
  const [objectType, setObjectType] = useState('')
  const [capacity, setCapacity] = useState('')
  const [baseQuarter, setBaseQuarter] = useState('')
  const [sources, setSources] = useState(['fgiscs', 'eis', 'market'])
  const [thr, setThr] = useState({ p1: '15', p2: '30', v1: '25', v2: '50', e1: '10', e2: '20' })
  const [demo, setDemo] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.demo().then(setDemo).catch(() => {}) }, [])
  useEffect(() => {
    if (!regionId && regions.length) setRegionId(regions.find((r) => r.name === 'Брянская область')?.id ?? regions[0].id)
  }, [regions, regionId])

  const region = regions.find((r) => r.id === regionId)
  useEffect(() => {
    setZoneId(pendingZone.current ?? region?.zones?.[0]?.id ?? '')
    pendingZone.current = null
  }, [regionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const pickDemo = async (d) => {
    setError('')
    const res = await fetch(`/api/demo/${d.file}`)
    const blob = await res.blob()
    setFile(new File([blob], d.file, { type: blob.type }))
    pendingZone.current = d.zone_id ?? ''
    setZoneId(d.zone_id ?? '')
    setRegionId(d.region_id)
    setQuarter(d.quarter)
    setObjectType(d.object_type || '')
    setCapacity(d.capacity ? String(d.capacity) : '')
    setBaseQuarter(d.base_quarter || '')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!file) return setError('Выберите файл сметы или спецификации')
    if (!regionId) return setError('Выберите регион')
    if (!sources.length) return setError('Выберите хотя бы один источник ориентиров')
    const form = new FormData()
    form.append('file', file)
    form.append('region_id', regionId)
    if (zoneId) form.append('zone_id', zoneId)
    form.append('quarter', quarter)
    if (objectType) form.append('object_type', objectType)
    if (capacity) form.append('capacity', capacity.replace(/\s/g, '').replace(',', '.'))
    if (baseQuarter) form.append('base_quarter', baseQuarter)
    form.append('sources', JSON.stringify(sources))
    const n = (v) => Number(String(v).replace(',', '.'))
    form.append('price_thresholds', JSON.stringify([n(thr.p1), n(thr.p2)]))
    form.append('volume_thresholds', JSON.stringify([n(thr.v1), n(thr.v2)]))
    form.append('escalation_thresholds', JSON.stringify([n(thr.e1), n(thr.e2)]))
    setBusy(true)
    try {
      const res = await api.createCheck(form)
      reload()
      navigate(`/checks/${res.id}`, { state: { warnings: res.warnings } })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const quarters = meta?.quarters ?? []
  const noPrices = region && !region.has_prices

  return (
    <div className="page narrow">
      <div className="crumbs"><Link to="/">Реестр проверок</Link> / Новая проверка</div>
      <h1>Новая проверка</h1>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <section className="card section">
          <h2>1. Документ</h2>
          <div className={`drop ${over ? 'over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]) }}>
            <UploadIcon />
            {file ? (
              <div><b>{file.name}</b> <span className="muted">· {(file.size / 1024).toFixed(0)} КБ</span></div>
            ) : (
              <div style={{ fontWeight: 600 }}>Перетащите смету или спецификацию сюда</div>
            )}
            <div className="hint">XLSX или CSV: колонки «Наименование», «Ед. изм.», «Количество», «Цена»; «Код КСР» и «Исходная цена» — по желанию</div>
            <input ref={fileInput} type="file" accept=".xlsx,.csv" className="sr-only" id="file"
              onChange={(e) => e.target.files[0] && setFile(e.target.files[0])} />
            <label htmlFor="file" className="btn secondary">{file ? 'Выбрать другой файл' : 'Выбрать файл'}</label>
          </div>
          <div className="hint">Файл обрабатывается на сервере организации; в отчёт записывается его контрольная сумма.</div>
          {demo.length > 0 && (
            <details>
              <summary>Демо-сметы с заранее известными отклонениями (документы синтетические, ресурсы и цены — из ФГИС ЦС)</summary>
              <div className="demo-list" style={{ marginTop: 10 }}>
                {demo.map((d) => (
                  <div key={d.file} className="demo-item">
                    <div style={{ flex: '1 1 380px' }}>
                      <div style={{ fontWeight: 600 }}>{d.title}</div>
                      <div className="xs muted">{regions.find((r) => r.id === d.region_id)?.name} · {quarterLabel(d.quarter)} · {d.object_type}, {d.capacity} м²{d.base_quarter ? ` · исходные цены ${quarterLabel(d.base_quarter)}` : ''}</div>
                    </div>
                    <div className="row" style={{ gap: 4 }}>
                      <a className="btn link" href={`/api/demo/${d.file}`} download>Скачать</a>
                      <button type="button" className="btn secondary" onClick={() => pickDemo(d)}>Подставить</button>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>

        <section className="card section">
          <h2>2. Параметры объекта</h2>
          <div className="grid-auto">
            <div className="field">
              <label htmlFor="region">Регион (все {regions.length} субъектов РФ)</label>
              <RegionSelect id="region" value={regionId} onChange={setRegionId} regions={regions} />
            </div>
            <div className="field">
              <label htmlFor="zone">Ценовая зона</label>
              <select id="zone" className="select" value={zoneId} onChange={(e) => setZoneId(e.target.value ? Number(e.target.value) : '')}>
                {region?.zones?.length ? region.zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)
                  : <option value="">Зоны не загружены</option>}
              </select>
            </div>
            <div className="field">
              <label htmlFor="quarter">Уровень цен</label>
              <select id="quarter" className="select" value={quarter} onChange={(e) => setQuarter(e.target.value)}>
                {quarters.map((q) => <option key={q} value={q}>{quarterLabel(q)}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="otype">Тип объекта</label>
              <select id="otype" className="select" value={objectType} onChange={(e) => setObjectType(e.target.value)}>
                <option value="">Не указан</option>
                {(meta?.object_types ?? []).map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="cap">Мощность объекта, м²</label>
              <input id="cap" className="input" inputMode="decimal" placeholder="Например, 4 200" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="bq">Квартал исходных цен (для удорожания)</label>
              <select id="bq" className="select" value={baseQuarter} onChange={(e) => setBaseQuarter(e.target.value)}>
                <option value="">Не проверять удорожание</option>
                {quarters.map((q) => <option key={q} value={q}>{quarterLabel(q)}</option>)}
              </select>
            </div>
          </div>
          {noPrices && <div className="note">Для этого региона ценовые справочники ещё не загружены: позиции будут извлечены, но ориентиров не будет. Загрузите выгрузку в разделе «Справочники цен».</div>}
          <div className="hint">Тип и мощность нужны для контроля объёмов: расход материала на 1 м² сравнивается с объектами-аналогами. Исходная цена берётся из колонки «Исходная цена» документа.</div>
        </section>

        <section className="card section">
          <h2>3. Ориентиры и пороги</h2>
          <fieldset className="row" style={{ gap: '4px 28px' }}>
            <legend className="legend" style={{ paddingBottom: 6 }}>Источники ценовых ориентиров</legend>
            {SOURCES.map(([v, l]) => {
              const st = meta?.source_status?.[v]
              return (
                <label key={v} className="check">
                  <input type="checkbox" checked={sources.includes(v)}
                    onChange={() => setSources(sources.includes(v) ? sources.filter((x) => x !== v) : [...sources, v])} /> {l}
                  {st && <span className="xs muted">({st === 'real' ? 'реальные' : st === 'synthetic' ? 'синтетические' : 'реальные и синтетические'})</span>}
                </label>
              )
            })}
          </fieldset>
          <div className="grid-auto">
            {[['p', 'Цена'], ['v', 'Объём на 1 м²'], ['e', 'Удорожание сверх индекса']].map(([k, l]) => (
              <fieldset key={k} className="field">
                <legend className="legend" style={{ paddingBottom: 6 }}>{l}: средний / высокий, %</legend>
                <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
                  <label className="sr-only" htmlFor={`${k}1`}>{l}, порог среднего сигнала</label>
                  <input id={`${k}1`} className="input" inputMode="decimal" value={thr[`${k}1`]} onChange={(e) => setThr({ ...thr, [`${k}1`]: e.target.value })} />
                  <label className="sr-only" htmlFor={`${k}2`}>{l}, порог высокого сигнала</label>
                  <input id={`${k}2`} className="input" inputMode="decimal" value={thr[`${k}2`]} onChange={(e) => setThr({ ...thr, [`${k}2`]: e.target.value })} />
                </div>
              </fieldset>
            ))}
          </div>
          <div className="hint">Чтобы считать только по реальным данным, оставьте один источник — ФГИС ЦС. Пороги — рабочие значения прототипа, уточняются на пилоте; они записываются в отчёт вместе с версиями справочников.</div>
        </section>

        {error && <div className="error" role="alert">{error}</div>}
        <div className="row">
          <button type="submit" className="btn" disabled={busy} style={{ minHeight: 48, padding: '0 28px' }}>
            {busy ? 'Проверяю…' : 'Запустить проверку'}
          </button>
          <Link to="/" className="btn link">Отмена</Link>
        </div>
      </form>
    </div>
  )
}
