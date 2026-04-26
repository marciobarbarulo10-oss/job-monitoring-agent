import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

const GRADE_STYLE = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-indigo-100 text-indigo-700',
  C: 'bg-yellow-100 text-yellow-700',
  D: 'bg-red-100 text-red-700',
  F: 'bg-gray-100 text-gray-500',
}

function CoverLetterModal({ jobId, titulo, empresa, onClose }) {
  const { data, isLoading } = useQuery({
    queryKey: ['cover-letter', jobId],
    queryFn: () => api.coverLetter(jobId),
  })

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-2xl w-full p-6 shadow-xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-gray-800">{titulo}</h3>
            <p className="text-sm text-gray-500">{empresa}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>
        {isLoading ? (
          <p className="text-gray-400">Gerando carta...</p>
        ) : data?.cover_letter ? (
          <>
            <pre className="flex-1 overflow-auto text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-4 font-sans">
              {data.cover_letter}
            </pre>
            <button
              onClick={() => navigator.clipboard.writeText(data.cover_letter)}
              className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700"
            >
              Copiar carta
            </button>
          </>
        ) : (
          <p className="text-red-500 text-sm">Carta nao disponivel para esta vaga.</p>
        )}
      </div>
    </div>
  )
}

export default function Jobs() {
  const [minScore, setMinScore] = useState(0)
  const [fonte, setFonte] = useState('')
  const [grade, setGrade] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [modal, setModal] = useState(null)

  const LIMIT = 20

  const { data, isLoading } = useQuery({
    queryKey: ['vagas', minScore, fonte, grade, search, page],
    queryFn: () => api.vagas({
      min_score: minScore || undefined,
      fonte: fonte || undefined,
      grade: grade || undefined,
      q: search || undefined,
      limit: LIMIT,
      offset: page * LIMIT,
    }),
  })

  const vagas = data?.vagas || []
  const total = data?.total || 0

  return (
    <div className="space-y-4">
      {modal && (
        <CoverLetterModal
          jobId={modal.id} titulo={modal.titulo} empresa={modal.empresa}
          onClose={() => setModal(null)}
        />
      )}

      <h1 className="text-2xl font-bold text-gray-800">Vagas</h1>

      {/* Filtros */}
      <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm flex flex-wrap gap-3 items-center">
        <input
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-48"
          placeholder="Buscar..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0) }}
        />
        <label className="flex items-center gap-2 text-sm text-gray-600">
          Score min:
          <input type="range" min={0} max={10} step={0.5} value={minScore}
            onChange={e => { setMinScore(Number(e.target.value)); setPage(0) }}
            className="w-24" />
          <span className="font-medium w-6">{minScore}</span>
        </label>
        <select
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
          value={grade}
          onChange={e => { setGrade(e.target.value); setPage(0) }}
        >
          <option value="">Todos grades</option>
          {['A','B','C','D','F'].map(g => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <select
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
          value={fonte}
          onChange={e => { setFonte(e.target.value); setPage(0) }}
        >
          <option value="">Todas fontes</option>
          {['linkedin','indeed','gupy','vagas.com'].map(f => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
        <span className="text-xs text-gray-400 ml-auto">{total} vagas</span>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-gray-400">Carregando...</div>
      ) : (
        <div className="space-y-2">
          {vagas.map(v => (
            <div key={v.id} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${GRADE_STYLE[v.grade] || GRADE_STYLE.F}`}>
                      {v.grade || '?'}
                    </span>
                    <span className="text-xs text-gray-400">{v.score?.toFixed(1)}/10</span>
                    {v.is_early && (
                      <span className="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full">Janela aberta</span>
                    )}
                    {v.has_cover_letter && (
                      <span className="text-xs bg-purple-100 text-purple-600 px-2 py-0.5 rounded-full">Carta pronta</span>
                    )}
                  </div>
                  <h3 className="font-semibold text-gray-800 mt-1 truncate">{v.titulo}</h3>
                  <p className="text-sm text-gray-500">{v.empresa} &bull; {v.localizacao} &bull; {v.fonte}</p>
                  {v.keywords?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {v.keywords.slice(0, 5).map((kw, i) => (
                        <span key={i} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{kw}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-col gap-1 shrink-0">
                  <a href={v.url} target="_blank" rel="noreferrer"
                    className="text-xs px-3 py-1 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-center">
                    Abrir
                  </a>
                  {v.has_cover_letter && (
                    <button
                      onClick={() => setModal(v)}
                      className="text-xs px-3 py-1 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200"
                    >
                      Ver carta
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Paginacao */}
      {total > LIMIT && (
        <div className="flex items-center justify-center gap-2">
          <button disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 text-sm bg-white border border-gray-200 rounded-lg disabled:opacity-40">
            Anterior
          </button>
          <span className="text-sm text-gray-500">
            {page + 1} / {Math.ceil(total / LIMIT)}
          </span>
          <button disabled={(page + 1) * LIMIT >= total}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 text-sm bg-white border border-gray-200 rounded-lg disabled:opacity-40">
            Proxima
          </button>
        </div>
      )}
    </div>
  )
}
