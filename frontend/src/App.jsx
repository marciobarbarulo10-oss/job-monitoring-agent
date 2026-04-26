import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Applications from './pages/Applications'
import Insights from './pages/Insights'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30000 } } })

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'jobs', label: 'Vagas' },
  { id: 'applications', label: 'Candidaturas' },
  { id: 'insights', label: 'Insights' },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')

  return (
    <QueryClientProvider client={qc}>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6 shadow-sm">
          <span className="font-bold text-lg text-indigo-700">Job Agent v3</span>
          <div className="flex gap-1">
            {TABS.map(t => (
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
          {tab === 'jobs' && <Jobs />}
          {tab === 'applications' && <Applications />}
          {tab === 'insights' && <Insights />}
        </main>
      </div>
    </QueryClientProvider>
  )
}
