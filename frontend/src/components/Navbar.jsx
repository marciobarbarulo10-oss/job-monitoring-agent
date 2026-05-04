import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { path: '/vagas', label: 'Vagas' },
  { path: '/candidaturas', label: 'Candidaturas' },
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/perfil', label: 'Meu Perfil' },
]

export function Navbar({ onLogout, userName }) {
  const location = useLocation()

  return (
    <nav style={{
      display: 'flex', alignItems: 'center', padding: '0 24px',
      height: '52px', borderBottom: '1px solid #eee',
      background: 'white', position: 'sticky', top: 0, zIndex: 100,
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <span style={{ fontWeight: 700, color: '#1D9E75', marginRight: '32px', fontSize: '15px' }}>
        Job Agent
      </span>

      <div style={{ display: 'flex', gap: '2px' }}>
        {LINKS.map(item => {
          const active = location.pathname === item.path
          return (
            <Link key={item.path} to={item.path}
              style={{
                padding: '6px 14px', borderRadius: '6px', fontSize: '14px',
                textDecoration: 'none',
                color: active ? '#1D9E75' : '#555',
                fontWeight: active ? 600 : 400,
                background: active ? '#f0faf6' : 'transparent',
                transition: 'all 0.15s',
              }}>
              {item.label}
            </Link>
          )
        })}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
        {userName && (
          <span style={{ fontSize: '13px', color: '#999' }}>{userName}</span>
        )}
        {onLogout && (
          <button onClick={onLogout}
            style={{
              fontSize: '12px', padding: '5px 14px',
              border: '1px solid #e0e0e0', borderRadius: '6px',
              background: 'white', cursor: 'pointer', color: '#555',
              transition: 'background 0.15s',
            }}>
            Sair
          </button>
        )}
      </div>
    </nav>
  )
}
