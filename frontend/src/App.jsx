import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Applications from './pages/Applications'
import Insights from './pages/Insights'
import Status from './pages/Status'
import Profile from './pages/Profile'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30000 } } })

const USER_TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'vagas', label: 'Vagas' },
  { id: 'candidaturas', label: 'Candidaturas' },
  { id: 'perfil', label: 'Meu Perfil' },
]

const isAdmin = new URLSearchParams(window.location.search).get('admin') === '1'

export default function App() {
  const [tab, setTab] = useState('dashboard')

  const visibleTabs = isAdmin
    ? [...USER_TABS, { id: 'insights', label: 'Insights' }, { id: 'status', label: 'Status' }]
    : USER_TABS

  return (
    <QueryClientProvider client={qc}>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6 shadow-sm">
          <span className="font-bold text-lg text-indigo-700">Job Agent</span>
          <div className="flex gap-1">
            {visibleTabs.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
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
