import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const STATUS_COLOR = {
  ok: '#1D9E75',
  warning: '#BA7517',
  error: '#E24B4A',
}

const STATUS_LABEL = {
  ok: 'ok',
  warning: 'aviso',
  error: 'erro',
}

function Badge({ status }) {
  const color = STATUS_COLOR[status] || '#999'
  return (
    <span style={{
      padding: '2px 10px',
      borderRadius: 99,
      background: color + '22',
      color,
      fontSize: 12,
      fontWeight: 600,
    }}>
      {STATUS_LABEL[status] || status}
    </span>
  )
}

function CheckCard({ check }) {
  const color = STATUS_COLOR[check.status] || '#ccc'
  const details = check.details || {}
  const entries = Object.entries(details).filter(([, v]) => v !== null && v !== undefined)

  return (
    <div style={{
      background: '#fff',
      borderRadius: 8,
      padding: '14px 16px',
      borderLeft: `3px solid ${color}`,
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{check.check}</span>
        <Badge status={check.status} />
      </div>
      <div style={{ fontSize: 11, color: '#666', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {entries.slice(0, 3).map(([k, v]) => (
          <div key={k}>
            <span style={{ color: '#999' }}>{k}:</span>{' '}
            <strong>{String(v).slice(0, 50)}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Status() {
  const { data: qa, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['qa-status'],
    queryFn: () => axios.get(`${API_BASE}/health/qa`).then(r => r.data),
    refetchInterval: 120_000,
    retry: 1,
  })

  const { data: gitStatus } = useQuery({
    queryKey: ['git-status'],
    queryFn: () => axios.get(`${API_BASE}/health/git/status`).then(r => r.data),
    refetchInterval: 60_000,
    retry: 1,
  })

  const { data: webhookHealth } = useQuery({
    queryKey: ['webhook-health'],
    queryFn: () => axios.get(`${API_BASE}/webhooks/mailerlite/health`).then(r => r.data),
    refetchInterval: 60_000,
    retry: 1,
  })

  const overallColor = STATUS_COLOR[qa?.overall_status] || '#999'

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Cabeçalho */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Status do Sistema</h2>
        {qa && (
          <span style={{
            padding: '4px 14px',
            borderRadius: 99,
            background: overallColor + '22',
            color: overallColor,
            fontSize: 13,
            fontWeight: 600,
          }}>
            {qa.overall_status?.toUpperCase()}
          </span>
        )}
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          style={{
            marginLeft: 'auto',
            cursor: isFetching ? 'not-allowed' : 'pointer',
            padding: '6px 14px',
            borderRadius: 6,
            border: '1px solid #ddd',
            background: '#fff',
            fontSize: 12,
            opacity: isFetching ? 0.6 : 1,
          }}
        >
          {isFetching ? 'Verificando...' : 'Verificar agora'}
        </button>
      </div>

      {/* Loading / erro */}
      {isLoading && (
        <div style={{ color: '#666', fontSize: 14 }}>Carregando QA...</div>
      )}
      {isError && (
        <div style={{ color: '#E24B4A', fontSize: 14 }}>
          API nao respondendo em {API_BASE}/health/qa
        </div>
      )}

      {/* Grid de checks */}
      {qa?.checks && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 12,
          marginBottom: 20,
        }}>
          {qa.checks.map(c => <CheckCard key={c.check} check={c} />)}
        </div>
      )}

      {/* Rodapé QA */}
      {qa && (
        <div style={{ fontSize: 12, color: '#999', marginBottom: 32 }}>
          Ultima verificacao: {qa.timestamp ? new Date(qa.timestamp).toLocaleString('pt-BR') : '—'}
          {' · '}{qa.total_checks} checks em {qa.duration_seconds}s
          {' · '}{qa.passed}/{qa.total_checks} ok
        </div>
      )}

      {/* Status Git */}
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Repositorio Git</h3>
      {gitStatus ? (
        <div style={{
          background: '#fff',
          borderRadius: 8,
          padding: '14px 16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          fontSize: 13,
        }}>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div><span style={{ color: '#999' }}>Branch:</span> <strong>{gitStatus.branch}</strong></div>
            <div>
              <span style={{ color: '#999' }}>Mudancas:</span>{' '}
              <strong style={{ color: gitStatus.has_changes ? '#BA7517' : '#1D9E75' }}>
                {gitStatus.has_changes
                  ? `${gitStatus.changed_files?.length || 0} arquivo(s) pendente(s)`
                  : 'atualizado'}
              </strong>
            </div>
            {gitStatus.remote_url && (
              <div>
                <span style={{ color: '#999' }}>Remote:</span>{' '}
                <a href={gitStatus.remote_url} target="_blank" rel="noreferrer" style={{ color: '#4F6EF7' }}>
                  GitHub
                </a>
              </div>
            )}
          </div>

          {gitStatus.has_changes && gitStatus.changed_files?.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 11, color: '#666' }}>
              {gitStatus.changed_files.slice(0, 5).map((f, i) => (
                <div key={i}>{f.status} {f.file}</div>
              ))}
              {gitStatus.changed_files.length > 5 && (
                <div>...e mais {gitStatus.changed_files.length - 5} arquivo(s)</div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div style={{ fontSize: 13, color: '#999' }}>Git status indisponivel</div>
      )}

      {/* Webhooks MailerLite */}
      {webhookHealth && (
        <>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, marginTop: 32 }}>
            Webhooks MailerLite
          </h3>
          <div style={{
            background: '#fff',
            borderRadius: 8,
            padding: '14px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
              {(webhookHealth.endpoints || []).map(ep => (
                <span key={ep} style={{
                  background: '#E8F5E9',
                  color: '#2E7D32',
                  padding: '5px 12px',
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 500,
                }}>
                  {ep.replace('/webhooks/mailerlite/', '')}
                </span>
              ))}
            </div>
            <div style={{ fontSize: 11, color: '#999' }}>
              {webhookHealth.webhooks_configured} webhooks configurados
              {' · '}
              Ultimo check: {webhookHealth.timestamp
                ? new Date(webhookHealth.timestamp).toLocaleTimeString('pt-BR')
                : '—'}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
