import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line,
  PieChart, Pie, Cell, ResponsiveContainer,
} from 'recharts'
import { api } from '../api'

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6']
const GRADE_COLOR = { A: '#10b981', B: '#6366f1', C: '#f59e0b', D: '#ef4444', F: '#9ca3af' }

function MetricCard({ label, value, sub, color = '#6366f1' }) {
  return (
    <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold" style={{ color }}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    refetchInterval: 30000,
    retry: 1,
    retryDelay: 2000,
  })

  if (isLoading) return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '60vh', gap: '12px', color: '#666', fontSize: '14px',
    }}>
      <div className="w-5 h-5 border-2 border-gray-200 border-t-[#1D9E75] rounded-full animate-spin" />
      Conectando ao servidor...
    </div>
  )

  if (isError) return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '60vh', gap: '16px', textAlign: 'center',
    }}>
      <div style={{ fontSize: '40px', color: '#BA7517' }}>!</div>
      <div style={{ fontSize: '18px', fontWeight: 500, color: '#333' }}>
        Sistema temporariamente indisponivel
      </div>
      <div style={{ fontSize: '14px', color: '#666', maxWidth: '420px' }}>
        Nao foi possivel conectar com o servidor. Verifique se o backend esta rodando na porta 8000.
      </div>
      <button onClick={() => refetch()} style={{
        padding: '10px 24px', background: '#1D9E75', color: 'white',
        border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px',
      }}>
        Tentar novamente
      </button>
      <div style={{ fontSize: '12px', color: '#bbb' }}>
        Comando: python -m uvicorn api.main:app --reload --port 8000
      </div>
    </div>
  )

  const f = data?.funnel || {}
  const funnelData = [
    { name: 'Encontradas', value: f.total_found || 0, fill: '#6366f1' },
    { name: 'Score Alto', value: f.high_score || 0, fill: '#10b981' },
    { name: 'Notificadas', value: f.notified || 0, fill: '#f59e0b' },
    { name: 'Candidatadas', value: f.applied || 0, fill: '#8b5cf6' },
    { name: 'Entrevistas', value: f.interview || 0, fill: '#14b8a6' },
    { name: 'Ofertas', value: f.offer || 0, fill: '#ef4444' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Vagas encontradas" value={f.total_found || 0} color="#6366f1" />
        <MetricCard label="Score medio" value={`${data?.avg_score || 0}/10`} color="#10b981" />
        <MetricCard label="Candidaturas ativas" value={f.applied || 0} color="#8b5cf6" />
        <MetricCard label="Entrevistas" value={f.interview || 0} color="#14b8a6"
          sub={f.offer ? `${f.offer} oferta(s)` : ''} />
      </div>

      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h2 className="text-base font-semibold text-gray-700 mb-4">Funil de candidaturas</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={funnelData} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {funnelData.map((e, i) => (
                <Cell key={i} fill={e.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h2 className="text-base font-semibold text-gray-700 mb-4">Vagas por dia (7 dias)</h2>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data?.daily_trend || []}>
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h2 className="text-base font-semibold text-gray-700 mb-4">Por plataforma</h2>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={data?.by_source || []} dataKey="count" nameKey="fonte" cx="50%" cy="50%" outerRadius={70}
                label={({ fonte, percent }) => `${fonte} ${(percent * 100).toFixed(0)}%`}>
                {(data?.by_source || []).map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {data?.top_today?.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h2 className="text-base font-semibold text-gray-700 mb-3">Top vagas de hoje</h2>
          <div className="space-y-2">
            {data.top_today.map(v => (
              <div key={v.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <span className="font-medium text-sm text-gray-800">{v.titulo}</span>
                  <span className="text-xs text-gray-400 ml-2">@ {v.empresa}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full"
                    style={{ background: GRADE_COLOR[v.grade] + '20', color: GRADE_COLOR[v.grade] }}>
                    {v.grade}
                  </span>
                  <span className="text-xs text-gray-500">{v.score?.toFixed(1)}</span>
                  <a href={v.url} target="_blank" rel="noreferrer"
                    className="text-xs text-indigo-600 hover:underline">Ver</a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
