import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../api'

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

export default function Insights() {
  const { data: report, isLoading: loadingReport } = useQuery({
    queryKey: ['market-report'],
    queryFn: api.marketReport,
  })

  const topKws = (report?.top_keywords || []).slice(0, 10)
  const topEmpresas = (report?.top_empresas || []).slice(0, 8)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Insights de Mercado</h1>

      {loadingReport ? (
        <div className="text-center py-8 text-gray-400">Carregando relatorio...</div>
      ) : !report || report.message ? (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-700 text-sm">
          Nenhum relatorio disponivel. O relatorio semanal e gerado automaticamente todo domingo as 18h.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Vagas na semana', value: report.total_vagas },
              { label: 'Score medio', value: `${report.score_medio}/10` },
              { label: 'Variacao', value: `${report.variacao_semana_pct > 0 ? '+' : ''}${report.variacao_semana_pct}%` },
              { label: 'Semana', value: report.semana },
            ].map(m => (
              <div key={m.label} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
                <div className="text-xs text-gray-500">{m.label}</div>
                <div className="text-xl font-bold text-indigo-700 mt-1">{m.value}</div>
              </div>
            ))}
          </div>

          {report.insights_narrative && (
            <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
              <p className="text-sm font-semibold text-indigo-700 mb-1">Analise inteligente</p>
              <p className="text-sm text-indigo-900">{report.insights_narrative}</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {topKws.length > 0 && (
              <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Keywords em alta</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={topKws} layout="vertical">
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="keyword" type="category" width={120} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {topEmpresas.length > 0 && (
              <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Empresas mais ativas</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={topEmpresas} layout="vertical">
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="empresa" type="category" width={120} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="vagas" radius={[0, 4, 4, 0]}>
                      {topEmpresas.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
