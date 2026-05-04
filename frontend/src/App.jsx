import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import axios from 'axios'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Applications from './pages/Applications'
import Insights from './pages/Insights'
import Status from './pages/Status'
import Profile from './pages/Profile'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30000 } } })

const USER_TABS = [
  { id: 'vagas', label: 'Vagas' },
  { id: 'candidaturas', label: 'Candidaturas' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'perfil', label: 'Meu Perfil' },
]

const isAdmin = new URLSearchParams(window.location.search).get('admin') === '1'

const PATH_TO_TAB = {
  '/': 'dashboard',
  '/dashboard': 'dashboard',
  '/vagas': 'vagas',
  '/candidaturas': 'candidaturas',
  '/perfil': 'perfil',
  '/insights': 'insights',
  '/status': 'status',
}

const TAB_TO_PATH = {
  dashboard: '/',
  vagas: '/vagas',
  candidaturas: '/candidaturas',
  perfil: '/perfil',
  insights: '/insights',
  status: '/status',
}

function getTabFromPath() {
  return PATH_TO_TAB[window.location.pathname] || 'dashboard'
}

export default function App() {
  const [tab, setTab] = useState(getTabFromPath)
  const [profileChecking, setProfileChecking] = useState(
    // só verifica na rota raiz para não bloquear quem acessa /perfil direto
    window.location.pathname === '/' || window.location.pathname === '/dashboard'
  )

  useEffect(() => {
    const handler = () => setTab(getTabFromPath())
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [])

  useEffect(() => {
    if (!profileChecking) return
    axios.get('http://localhost:8000/api/profile/', { timeout: 5000 })
      .then(r => {
        const hasProfile = !!(r.data?.target_role || r.data?.name)
        if (!hasProfile) {
          setTab('perfil')
          history.pushState({}, '', '/perfil')
        } else if (window.location.pathname === '/' || window.location.pathname === '/dashboard') {
          // Tem perfil e está na raiz/dashboard → vai para vagas (mais útil)
          setTab('vagas')
          history.pushState({}, '', '/vagas')
        }
      })
      .catch(() => {
        // API offline — não bloqueia o usuário
      })
      .finally(() => setProfileChecking(false))
  }, [])

  const navigate = (newTab) => {
    setTab(newTab)
    history.pushState({}, '', TAB_TO_PATH[newTab] || '/')
  }

  const visibleTabs = isAdmin
    ? [...USER_TABS, { id: 'insights', label: 'Insights' }, { id: 'status', label: 'Status' }]
    : USER_TABS

  if (profileChecking) {
    return (
      <QueryClientProvider client={qc}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '100vh', gap: '12px', color: '#666', fontSize: '14px',
        }}>
          <div style={{
            width: '20px', height: '20px',
            border: '2px solid #eee', borderTop: '2px solid #1D9E75',
            borderRadius: '50%', animation: 'spin 1s linear infinite',
          }} />
          Carregando...
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      </QueryClientProvider>
    )
  }

  return (
    <QueryClientProvider client={qc}>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6 shadow-sm">
          <span className="font-bold text-lg text-indigo-700">Job Agent</span>
          <div className="flex gap-1">
            {visibleTabs.map(t => (
              <button
                key={t.id}
                onClick={() => navigate(t.id)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  tab === t.id
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-6">
          {tab === 'dashboard' && <Dashboard />}
          {tab === 'vagas' && <Jobs />}
          {tab === 'candidaturas' && <Applications />}
          {tab === 'perfil' && <Profile />}
          {tab === 'insights' && <Insights />}
          {tab === 'status' && <Status />}
        </main>
      </div>
    </QueryClientProvider>
  )
}
