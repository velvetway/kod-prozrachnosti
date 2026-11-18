import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Badge } from '../components/common.jsx'
import { KINDS, date, pct } from '../format.js'

export default function Journal() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.journal().then(setRows).catch((e) => setError(e.message)) }, [])

  return (
    <div className="page">
      <h1>Журнал решений</h1>
      <div className="hint">Все решения специалистов по сигналам. Записи не редактируются: новое решение по тому же сигналу добавляется отдельной строкой.</div>
      {error && <div className="error">{error}</div>}
      <div className="card">
        {rows && rows.length === 0 ? (
          <div className="empty"><h2>Решений пока нет</h2><p className="muted" style={{ margin: 0 }}>Откройте карточку сигнала в любой проверке и зафиксируйте решение.</p></div>
        ) : (
          <div className="table-wrap">
            <table className="data" style={{ minWidth: 920 }}>
              <thead><tr><th scope="col">Дата</th><th scope="col">Проверка</th><th scope="col">Позиция и сигнал</th><th scope="col">Решение</th><th scope="col">Комментарий</th><th scope="col">Автор</th></tr></thead>
              <tbody>
                {!rows && <tr><td colSpan={6} className="muted">Загрузка…</td></tr>}
                {rows?.map((r) => (
                  <tr key={r.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{date(r.at)}</td>
                    <td><Link to={`/checks/${r.check_id}`}>{r.check_number}</Link><div className="xs muted">{r.region}</div></td>
                    <td><Link to={`/signals/${r.signal_id}`}>{r.item}</Link><div className="xs">{KINDS[r.kind]} {pct(r.deviation_pct)} <Badge level={r.level} /></div></td>
                    <td style={{ fontWeight: 600 }}>{r.outcome}</td>
                    <td>{r.comment || <span className="muted">—</span>}</td>
                    <td className="xs muted">{r.author}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
