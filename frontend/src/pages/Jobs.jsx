import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { api } from '../api'

const BASE = 'http://localhost:8000/api'

const GRADE_STYLE = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-indigo-100 text-indigo-700',
  C: 'bg-yellow-100 text-yellow-700',
  D: 'bg-red-100 text-red-700',
  F: 'bg-gray-100 text-gray-500',
}

function parseBreakdown(scoreAnalysis) {
  if (!scoreAnalysis) return null
  try {
    return JSON.parse(scoreAnalysis)
  } catch {
    return { reasoning: scoreAnalysis }
  }
}

function JobDetailModal({ job, onClose }) {
  const [coverLetter, setCoverLetter] = useState(job.cover_letter || '')
  const [loadingLetter, setLoadingLetter] = useState(false)
  const [copied, setCopied] = useState(false)

  const loadLetter = async () => {
    if (coverLetter) return
    setLoadingLetter(true)
    try {
      const r = await axios.get(`${BASE}/vagas/${job.id}/cover-letter`)
      setCoverLetter(r.data.cover_letter || '')
    } catch {
      setCoverLetter('Carta nao disponivel. Configure ANTHROPIC_API_KEY para gerar automaticamente.')
    } finally {
      setLoadingLetter(false)
    }
  }

  useEffect(() => { loadLetter() }, [])

  const breakdown = parseBreakdown(job.score_analysis)

  const copyLetter = () => {
    navigator.clipboard.writeText(coverLetter)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '20px',
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: 'white', borderRadius: '16px', padding: '28px',
        width: '100%', maxWidth: '620px', maxHeight: '85vh',
        overflow: 'auto', position: 'relative',
      }}>
        <button onClick={onClose} style={{
          position: 'absolute', top: '16px', right: '16px',
          background: 'none', border: 'none', fontSize: '22px',
          cursor: 'pointer', color: '#999', lineHeight: 1,
        }}>&times;</button>

        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '13px', color: '#1D9E75', fontWeight: 500, marginBottom: '4px' }}>
            {job.fonte} &bull; Score {job.score?.toFixed(1)}/10
            {job.grade && (
              <span style={{ marginLeft: '8px', fontWeight: 700 }}>({job.grade})</span>
            )}
          </div>
          <h2 style={{ fontSize: '18px', margin: '0 0 4px', fontWeight: 600 }}>{job.titulo}</h2>
          <div style={{ fontSize: '14px', color: '#666' }}>
            {job.empresa} &bull; {job.localizacao}
          </div>
        </div>

        {breakdown && (
          <div style={{
            background: '#f0faf6', borderRadius: '10px', padding: '14px',
            marginBottom: '20px', fontSize: '13px',
          }}>
            <div style={{ fontWeight: 500, marginBottom: '8px' }}>Por que este score?</div>
            {breakdown.reasoning && (
              <div style={{ color: '#444', lineHeight: 1.6, marginBottom: '6px' }}>
                {breakdown.reasoning}
              </div>
            )}
            {breakdown.strengths?.length > 0 && (
              <div style={{ marginTop: '6px' }}>
                <span style={{ color: '#1D9E75', fontWeight: 500 }}>Pontos fortes: </span>
                {breakdown.strengths.join(', ')}
              </div>
            )}
            {breakdown.gaps?.length > 0 && (
              <div style={{ marginTop: '4px' }}>
                <span style={{ color: '#BA7517', fontWeight: 500 }}>Lacunas: </span>
                {breakdown.gaps.join(', ')}
              </div>
            )}
          </div>
        )}

        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ fontSize: '14px', fontWeight: 500 }}>Carta de apresentacao</div>
            {coverLetter && !loadingLetter && (
              <button onClick={copyLetter} style={{
                fontSize: '12px', padding: '4px 12px', border: '1px solid #ddd',
                borderRadius: '6px', background: 'white', cursor: 'pointer',
              }}>
                {copied ? 'Copiada!' : 'Copiar'}
              </button>
            )}
          </div>

          {loadingLetter ? (
            <div style={{ color: '#999', fontSize: '13px', padding: '16px 0' }}>
              Carregando carta...
            </div>
          ) : (
            <div style={{
              background: '#f9f9f9', borderRadius: '8px', padding: '14px',
              fontSize: '13px', lineHeight: 1.7, whiteSpace: 'pre-wrap', color: '#333',
              maxHeight: '260px', overflow: 'auto',
            }}>
              {coverLetter || 'Nenhuma carta gerada para esta vaga.'}
            </div>
          )}
        </div>

        <a href={job.url} target="_blank" rel="noreferrer"
          style={{
            display: 'block', padding: '12px', background: '#1D9E75', color: 'white',
            borderRadius: '8px', textDecoration: 'none', textAlign: 'center',
            fontSize: '14px', fontWeight: 500,
          }}>
          Abrir vaga
        </a>
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
  const [selectedJob, setSelectedJob] = useState(null)

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
      {selectedJob && (
        <JobDetailModal job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}

      <h1 className="text-2xl font-bold text-gray-800">Vagas</h1>

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
          {['A', 'B', 'C', 'D', 'F'].map(g => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <select
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
          value={fonte}
          onChange={e => { setFonte(e.target.value); setPage(0) }}
        >
          <option value="">Todas fontes</option>
          {['linkedin', 'indeed', 'gupy', 'vagas.com'].map(f => (
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
            <div
              key={v.id}
              className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setSelectedJob(v)}
            >
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
                <div className="shrink-0">
                  <a
                    href={v.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="text-xs px-3 py-1 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-center block"
                  >
                    Abrir
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

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
