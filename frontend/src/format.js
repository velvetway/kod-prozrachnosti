const nf = (digits) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const money = (v) => (v == null ? '—' : nf(2).format(v))
export const rub = (v) => (v == null ? '—' : `${nf(0).format(Math.round(v))} ₽`)
export const num = (v, d = 2) => (v == null ? '—' : nf(d).format(v))
export const qty = (v) => (v == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 }).format(v))
export const pct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${nf(1).format(v)} %`)
export const date = (iso) => new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

export const quarterLabel = (q) => {
  if (!q) return '—'
  const [y, n] = q.split('-Q')
  return `${['I', 'II', 'III', 'IV'][Number(n) - 1]} квартал ${y}`
}

export const LEVELS = {
  high: 'Высокий',
  medium: 'Средний',
  review: 'Проверить сопоставление',
  none: 'В пределах порога',
  nomatch: 'Нет ориентира',
  nodata: 'Нет данных',
}

export const KINDS = { price: 'Цена', volume: 'Объём на 1 м²', escalation: 'Удорожание' }

export const MAX_LEVEL = {
  high: ['high', 'Высокий сигнал'],
  medium: ['medium', 'Средний сигнал'],
  review: ['review', 'Проверить сопоставление'],
  none: ['none', 'Без сигналов'],
}

export const devClass = (level) => (level === 'high' ? 'dev-high' : level === 'medium' ? 'dev-medium' : '')
