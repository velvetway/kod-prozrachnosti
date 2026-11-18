import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { RegionSelect, useRef_ } from '../components/common.jsx'
import { num } from '../format.js'

export default function Analogs() {
  const { regions } = useRef_()
  const [regionId, setRegionId] = useState(null)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { if (!regionId && regions.length) setRegionId(regions[0].id) }, [regions, regionId])
  useEffect(() => { if (regionId) { setRows(null); api.analogs(regionId).then(setRows).catch((e) => setError(e.message)) } }, [regionId])

  const types = [...new Set((rows ?? []).map((r) => r.object_type))]
  return (
    <div className="page">
      <h1>Объекты-аналоги</h1>
      <div className="card section">
        <div className="field" style={{ maxWidth: 420 }}><label htmlFor="r">Регион</label><RegionSelect id="r" value={regionId} onChange={setRegionId} regions={regions} /></div>
        <div className="hint">Удельный расход материалов на 1 м² мощности объекта. По этим данным строится коридор при контроле объёмов.</div>
      </div>
      {error && <div className="error">{error}</div>}
      {rows && rows.length === 0 && <div className="card section"><div className="note">Для региона объекты-аналоги не загружены (раздел «Справочники цен» → вид данных «Объекты-аналоги»).</div></div>}
      {types.map((t) => {
        const objs = rows.filter((r) => r.object_type === t)
        const codes = [...new Map(objs.flatMap((o) => o.consumption.map((c) => [c.code, c]))).values()]
        return (
          <section key={t} className="card">
            <div className="section" style={{ paddingBottom: 0 }}><h2>{t}</h2></div>
            <div className="table-wrap">
              <table className="data" style={{ minWidth: 300 + objs.length * 150 }}>
                <thead><tr><th scope="col">Материал, на 1 м²</th>{objs.map((o) => <th key={o.id} scope="col" className="num">{o.doc_ref.replace('Объект-аналог ', '')}<div className="xs" style={{ fontWeight: 400 }}>{num(o.capacity, 0)} м²</div></th>)}</tr></thead>
                <tbody>
                  {codes.map((c) => (
                    <tr key={c.code}><td><div style={{ fontWeight: 600 }}>{c.name}</div><div className="xs muted">{c.code} · {c.unit}</div></td>
                      {objs.map((o) => <td key={o.id} className="num">{num(o.consumption.find((x) => x.code === c.code)?.per_m2, 4)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )
      })}
    </div>
  )
}
