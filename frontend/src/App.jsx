import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import axios from 'axios'

import { AuthContext } from './components/AuthContext'
import { Navbar } from './components/Navbar'
import Login from './pages/Login'
import Register from './pages/Register'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Applications from './pages/Applications'
import Profile from './pages/Profile'
import Insights from './pages/Insights'
import Status from './pages/Status'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30000 } },
})

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Spinner() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', gap: '12px', color: '#666', fontSize: '14px',
    }}>
      <div style={{
        width: '18px', height: '18px',
        border: '2px solid #eee', borderTop: '2px solid #1D9E75',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
      }} />
      Carregando...
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

function AppRouter() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const token = localStorage.getItem('job_agent_token')
    if (!token) {
      setLoading(false)
      return
    }
    axios.get(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: 5000,
    })
      .then(r => {
        setUser(r.data.user)
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      })
      .catch(() => {
        localStorage.removeItem('job_agent_token')
        delete axios.defaults.headers.common['Authorization']
      })
      .finally(() => setLoading(false))
  }, [])

  const login = (token, userData, nextStep) => {
    localStorage.setItem('job_agent_token', token)
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
    setUser(userData)
    navigate(nextStep === 'onboarding' ? '/onboarding' : '/vagas', { replace: true })
  }

  const logout = () => {
    axios.post(`${API}/auth/logout`).catch(() => {})
    localStorage.removeItem('job_agent_token')
    delete axios.defaults.headers.common['Authorization']
    setUser(null)
    navigate('/login', { replace: true })
  }

  if (loading) return <Spinner />

  const publicRoutes = ['/login', '/register']
  const isPublic = publicRoutes.includes(location.pathname)

  if (!user && !isPublic) {
    return <Navigate to="/login" replace />
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, api: API }}>
      <Routes>
        {/* Rotas públicas */}
        <Route path="/login"    element={user ? <Navigate to="/vagas" replace /> : <Login />} />
        <Route path="/register" element={user ? <Navigate to="/vagas" replace /> : <Register />} />

        {/* Onboarding — sem navbar */}
        <Route path="/onboarding" element={user ? <Onboarding /> : <Navigate to="/login" replace />} />

        {/* Rotas protegidas — com navbar */}
        <Route path="*" element={
          user ? (
            <div className="min-h-screen bg-gray-50">
              <Navbar onLogout={logout} userName={user.name} />
              <main className="max-w-6xl mx-auto px-6 py-6">
                <Routes>
                  <Route path="/vagas"        element={<Jobs />} />
                  <Route path="/candidaturas" element={<Applications />} />
                  <Route path="/dashboard"    element={<Dashboard />} />
                  <Route path="/perfil"       element={<Profile />} />
                  <Route path="/admin/insights" element={<Insights />} />
                  <Route path="/admin/status"   element={<Status />} />
                  <Route path="/"             element={<Navigate to="/vagas" replace />} />
                  <Route path="*"             element={<Navigate to="/vagas" replace />} />
                </Routes>
              </main>
            </div>
          ) : <Navigate to="/login" replace />
        } />
      </Routes>
    </AuthContext.Provider>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
