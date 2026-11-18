import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, useRef_ } from '../components/common.jsx'
import { KINDS, date, pct } from '../format.js'

export default function Journal() {
  const { user } = useRef_()
  const [rows, setRows] = useState(null)
  const [audit, setAudit] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.journal().then(setRows).catch((e) => setError(e.message)) }, [])
  useEffect(() => { if (user?.role === 'admin') api.audit().then(setAudit).catch(() => {}) }, [user])

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
      {audit && (
        <>
          <h2>Журнал аудита</h2>
          <div className="hint">Все действия пользователей: вход, проверки, повторные расчёты, ручные сопоставления, решения, загрузка справочников. Виден администратору.</div>
          <div className="card table-wrap">
            <table className="data" style={{ minWidth: 760 }}>
              <thead><tr><th scope="col">Время</th><th scope="col">Пользователь</th><th scope="col">Действие</th><th scope="col">Объект</th><th scope="col">Подробности</th></tr></thead>
              <tbody>{audit.map((e) => (
                <tr key={e.id}><td style={{ whiteSpace: 'nowrap' }}>{date(e.at)}</td><td>{e.user}</td><td>{e.action}</td><td>{e.object || '—'}</td>
                  <td className="xs muted">{Object.entries(e.details || {}).map(([k, v]) => `${k}: ${typeof v === 'string' && v.length > 24 ? v.slice(0, 12) + '…' : v}`).join('; ') || '—'}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
