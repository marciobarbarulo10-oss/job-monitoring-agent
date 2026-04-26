import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

const STAGES = [
  { key: 'aplicada', label: 'Candidatada', color: 'bg-blue-50 border-blue-200' },
  { key: 'em_analise', label: 'Em analise', color: 'bg-yellow-50 border-yellow-200' },
  { key: 'entrevista', label: 'Entrevista', color: 'bg-purple-50 border-purple-200' },
  { key: 'proposta', label: 'Oferta', color: 'bg-green-50 border-green-200' },
  { key: 'rejeitada', label: 'Rejeitada', color: 'bg-red-50 border-red-200' },
]

const STATUS_NEXT = {
  aplicada: 'em_analise',
  em_analise: 'entrevista',
  entrevista: 'proposta',
}

export default function Applications() {
  const qc = useQueryClient()
  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['candidaturas'],
    queryFn: api.candidaturas,
    refetchInterval: 15000,
  })

  const mutStatus = useMutation({
    mutationFn: ({ id, status }) => api.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries(['candidaturas']),
  })

  if (isLoading) return <div className="text-center py-8 text-gray-400">Carregando candidaturas...</div>

  const grouped = STAGES.reduce((acc, s) => {
    acc[s.key] = apps.filter(a => a.status === s.key)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-800">Candidaturas</h1>
      <p className="text-sm text-gray-500">{apps.length} candidatura(s) no total</p>

      <div className="overflow-x-auto">
        <div className="flex gap-4 min-w-max pb-4">
          {STAGES.map(stage => (
            <div key={stage.key} className={`w-64 rounded-xl border p-3 ${stage.color}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-gray-700">{stage.label}</span>
                <span className="text-xs bg-white border border-gray-200 rounded-full px-2 py-0.5 text-gray-600">
                  {grouped[stage.key]?.length || 0}
                </span>
              </div>
              <div className="space-y-2">
                {(grouped[stage.key] || []).map(app => (
                  <div key={app.id} className="bg-white rounded-lg p-3 shadow-sm border border-gray-100">
                    <p className="text-xs font-semibold text-gray-800 truncate">{app.titulo}</p>
                    <p className="text-xs text-gray-500 truncate">{app.empresa}</p>
                    <p className="text-xs text-gray-400 mt-1">{app.data_aplicacao}</p>
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {STATUS_NEXT[app.status] && (
                        <button
                          onClick={() => mutStatus.mutate({ id: app.id, status: STATUS_NEXT[app.status] })}
                          className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200"
                        >
                          Avancar
                        </button>
                      )}
                      {app.status !== 'rejeitada' && app.status !== 'proposta' && (
                        <button
                          onClick={() => mutStatus.mutate({ id: app.id, status: 'rejeitada' })}
                          className="text-xs px-2 py-0.5 bg-red-100 text-red-600 rounded hover:bg-red-200"
                        >
                          Rejeitar
                        </button>
                      )}
                      <a href={app.url} target="_blank" rel="noreferrer"
                        className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded hover:bg-gray-200">
                        Link
                      </a>
                    </div>
                  </div>
                ))}
                {(!grouped[stage.key] || grouped[stage.key].length === 0) && (
                  <div className="text-xs text-gray-400 text-center py-4 italic">vazio</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
