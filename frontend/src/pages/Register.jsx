import { useState, useContext } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { AuthContext } from '../components/AuthContext'

const API = import.meta.env.VITE_API_URL || window.location.origin

const inputStyle = {
  width: '100%', padding: '10px 12px', borderRadius: '8px',
  border: '1px solid #ddd', fontSize: '14px', boxSizing: 'border-box',
  outline: 'none', fontFamily: 'inherit',
}

export default function Register() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useContext(AuthContext)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 6) {
      setError('Senha deve ter pelo menos 6 caracteres')
      return
    }
    setLoading(true)
    try {
      const r = await axios.post(`${API}/auth/register`, { name, email, password }, { timeout: 10000 })
      login(r.data.token, r.data.user, r.data.next_step)
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao criar conta. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #f0faf6 0%, #f8f9fa 100%)',
    }}>
      <div style={{
        background: 'white', borderRadius: '16px', padding: '40px 44px',
        width: '100%', maxWidth: '400px',
        boxShadow: '0 4px 32px rgba(0,0,0,0.08)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ fontSize: '30px', fontWeight: 700, color: '#1D9E75' }}>Job Agent</div>
          <div style={{ fontSize: '14px', color: '#888', marginTop: '6px' }}>
            Crie sua conta grátis
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
              Nome completo
            </label>
            <input
              style={inputStyle}
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Seu nome"
              required
              autoFocus
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
              E-mail
            </label>
            <input
              style={inputStyle}
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="seu@email.com"
              required
            />
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
              Senha
            </label>
            <input
              style={inputStyle}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Mínimo 6 caracteres"
              required
            />
          </div>

          {error && (
            <div style={{
              marginBottom: '16px', padding: '10px 14px',
              background: '#FFF0F0', color: '#C0392B',
              borderRadius: '8px', fontSize: '13px',
            }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading}
            style={{
              width: '100%', padding: '12px',
              background: loading ? '#a8d5c4' : '#1D9E75',
              color: 'white', border: 'none', borderRadius: '10px',
              fontSize: '15px', fontWeight: 500,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}>
            {loading ? 'Criando conta...' : 'Criar conta'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '24px', fontSize: '13px', color: '#888' }}>
          Já tem conta?{' '}
          <Link to="/login" style={{ color: '#1D9E75', textDecoration: 'none', fontWeight: 600 }}>
            Entrar
          </Link>
        </div>
      </div>
    </div>
  )
}
