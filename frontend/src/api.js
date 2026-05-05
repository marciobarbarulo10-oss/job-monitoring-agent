import axios from 'axios'

const BASE = `${import.meta.env.VITE_API_URL || window.location.origin}/api`

export const api = {
  dashboard: () => axios.get(`${BASE}/dashboard/summary`).then(r => r.data),
  vagas: (params = {}) => axios.get(`${BASE}/vagas/`, { params }).then(r => r.data),
  vaga: (id) => axios.get(`${BASE}/vagas/${id}`).then(r => r.data),
  coverLetter: (id) => axios.get(`${BASE}/vagas/${id}/cover-letter`).then(r => r.data),
  candidaturas: () => axios.get(`${BASE}/candidaturas/`).then(r => r.data),
  updateStatus: (id, status, notas = '') =>
    axios.post(`${BASE}/candidaturas/${id}/status`, { status, notas }).then(r => r.data),
  history: (id) => axios.get(`${BASE}/candidaturas/${id}/history`).then(r => r.data),
  marketReport: () => axios.get(`${BASE}/insights/market`).then(r => r.data),
  agentLogs: () => axios.get(`${BASE}/insights/agent-logs`).then(r => r.data),
  profile: () => axios.get(`${BASE}/profile/`).then(r => r.data),
  health: () => axios.get(`${import.meta.env.VITE_API_URL || window.location.origin}/health/`).then(r => r.data),
  marketingStats: () => axios.get(`${BASE}/dashboard/marketing-stats`).then(r => r.data),
  growthStats: () => axios.get(`${BASE}/dashboard/growth-stats`).then(r => r.data),
}
