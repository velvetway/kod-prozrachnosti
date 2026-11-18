async function request(path, options = {}) {
  const res = await fetch(path, { credentials: 'same-origin', ...options })
  if (res.status === 401 && path !== '/api/login') window.dispatchEvent(new Event('auth-required'))
  if (!res.ok) {
    let msg = `Ошибка ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* ответ не JSON */ }
    throw new Error(msg)
  }
  return res.json()
}

const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  me: () => request('/api/me'),
  login: (login, password) => request('/api/login', json({ login, password })),
  logout: () => request('/api/logout', { method: 'POST' }),
  audit: () => request('/api/audit'),
  meta: () => request('/api/meta'),
  regions: () => request('/api/regions'),
  checks: (params) => request('/api/checks?' + params.toString()),
  check: (id) => request(`/api/checks/${id}`),
  createCheck: (form) => request('/api/checks', { method: 'POST', body: form }),
  rerun: (id) => request(`/api/checks/${id}/rerun`, { method: 'POST' }),
  signal: (id) => request(`/api/signals/${id}`),
  decide: (id, outcome, comment) => request(`/api/signals/${id}/decision`, json({ outcome, comment })),
  candidates: (itemId) => request(`/api/items/${itemId}/candidates`),
  setMatch: (itemId, resourceId) => request(`/api/items/${itemId}/match`, json({ resource_id: resourceId })),
  journal: () => request('/api/journal'),
  prices: (params) => request('/api/reference/prices?' + params.toString()),
  analogs: (regionId) => request(`/api/reference/analogs?region_id=${regionId}`),
  importRef: (form) => request('/api/reference/import', { method: 'POST', body: form }),
  demo: () => request('/api/demo'),
}

export const reportUrl = (id) => `/api/checks/${id}/report.docx`
