import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../components/AuthContext'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || window.location.origin

function calcCompletion(form, cvFiles) {
  const checks = [
    !!form.name,
    !!form.target_role,
    form.experience_years > 0,
    form.keywords.length >= 5,
    cvFiles.length > 0,
    !!form.summary,
    !!form.linkedin_url,
  ]
  return Math.round((checks.filter(Boolean).length / checks.length) * 100)
}

const KEYWORD_SUGGESTIONS = [
  'importação', 'exportação', 'SISCOMEX', 'NCM', 'drawback',
  'Incoterms', 'supply chain', 'logística', 'ANVISA', 'DI', 'LI',
  'Receita Federal', 'despacho aduaneiro', 'licença de importação',
  'comércio exterior', 'freight', 'armazenagem', 'compliance',
  'cold chain', 'GLP', 'farmacêutico', 'SAP', 'Oracle',
]

export default function Profile() {
  const { user } = useAuth() || {}
  const navigate = useNavigate()
  const token = localStorage.getItem('job_agent_token')

  const [form, setForm] = useState({
    name: '', target_role: '', experience_years: 0,
    location: 'São Paulo, SP', summary: '',
    keywords: [], languages: ['Português'],
    education: '', linkedin_url: '',
    telegram_chat_id: '', min_score_notify: 6.0,
  })
  const [cvFiles, setCvFiles] = useState([])
  const [activeCV, setActiveCV] = useState('')
  const [keywordInput, setKeywordInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [uploadingCV, setUploadingCV] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [loading, setLoading] = useState(true)

  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/auth/me`, { headers, timeout: 8000 }),
      axios.get(`${API}/auth/cvs`, { headers, timeout: 8000 }),
    ])
      .then(([meRes, cvsRes]) => {
        const p = meRes.data.profile || {}
        setForm(f => ({
          ...f,
          name: meRes.data.user?.name || '',
          target_role: p.target_role || '',
          experience_years: p.experience_years || 0,
          location: p.location || 'São Paulo, SP',
          summary: p.summary || '',
          keywords: Array.isArray(p.keywords) ? p.keywords : [],
          languages: Array.isArray(p.languages) ? p.languages : ['Português'],
          education: p.education || '',
          linkedin_url: p.linkedin_url || '',
          telegram_chat_id: p.telegram_chat_id || '',
          min_score_notify: p.min_score_notify || 6.0,
        }))
        setCvFiles(cvsRes.data.files || [])
        setActiveCV(cvsRes.data.active || '')
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const isNewUser = !form.target_role && !loading
  const completion = calcCompletion(form, cvFiles)

  const handleSave = async () => {
    if (!form.target_role.trim()) {
      setSaveError('Preencha o cargo alvo antes de salvar.')
      return
    }
    setSaving(true)
    setSaveError('')
    try {
      await axios.put(`${API}/auth/profile`, { ...form, active_cv: activeCV }, { headers, timeout: 10000 })
      setSaved(true)
      setTimeout(() => {
        setSaved(false)
        if (isNewUser) navigate('/vagas')
      }, 1500)
    } catch (e) {
      setSaveError(
        e.code === 'ECONNABORTED'
          ? 'Tempo esgotado. Verifique a conexão.'
          : e.response?.data?.detail || 'Erro ao salvar. Tente novamente.'
      )
    } finally {
      setSaving(false)
    }
  }

  const handleCVUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadMsg('Apenas arquivos PDF são aceitos')
      return
    }
    setUploadingCV(true)
    setUploadMsg('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await axios.post(`${API}/auth/upload-cv`, fd, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      })
      const name = r.data.filename
      setCvFiles(prev => prev.includes(name) ? prev : [...prev, name])
      if (!activeCV) setActiveCV(name)
      setUploadMsg(`ok:${name} enviado com sucesso`)
      setTimeout(() => setUploadMsg(''), 4000)
    } catch (err) {
      setUploadMsg(`err:${err.response?.data?.detail || 'Erro ao enviar arquivo'}`)
    } finally {
      setUploadingCV(false)
      e.target.value = ''
    }
  }

  const addKeyword = (kw) => {
    const k = (kw || keywordInput).trim()
    if (k && !form.keywords.includes(k)) {
      setForm(f => ({ ...f, keywords: [...f.keywords, k] }))
    }
    if (!kw) setKeywordInput('')
  }

  const removeKeyword = (kw) =>
    setForm(f => ({ ...f, keywords: f.keywords.filter(k => k !== kw) }))

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '60vh', gap: '12px', color: '#888', fontSize: '14px' }}>
      <div style={{ width: '18px', height: '18px', border: '2px solid #eee',
        borderTop: '2px solid #1D9E75', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite' }} />
      Carregando perfil...
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )

  const uploadOk = uploadMsg.startsWith('ok:')
  const uploadErr = uploadMsg.startsWith('err:')
  const uploadText = uploadMsg.slice(3)

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '32px 20px 60px' }}>

      {isNewUser && (
        <div style={{
          background: 'linear-gradient(135deg,#1D9E75,#0d7a5a)',
          borderRadius: '12px', padding: '20px 24px', marginBottom: '28px', color: 'white',
        }}>
          <div style={{ fontSize: '20px', fontWeight: 500, marginBottom: '6px' }}>
            Bem-vindo ao Job Agent!
          </div>
          <div style={{ fontSize: '14px', opacity: 0.9, lineHeight: 1.6 }}>
            Configure seu perfil para que o agente encontre as vagas certas para você.
            Leva menos de 3 minutos e faz toda a diferença no score de cada vaga.
          </div>
        </div>
      )}

      {/* Header com barra de progresso */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: '10px' }}>
          <h1 style={{ fontSize: '22px', fontWeight: 500, margin: 0 }}>Meu Perfil</h1>
          <span style={{
            fontSize: '13px', fontWeight: 500,
            color: completion >= 80 ? '#1D9E75' : completion >= 50 ? '#BA7517' : '#888',
          }}>
            {completion}% completo
          </span>
        </div>
        <div style={{ height: '4px', background: '#eee', borderRadius: '2px' }}>
          <div style={{
            height: '100%', borderRadius: '2px',
            background: completion >= 80 ? '#1D9E75' : completion >= 50 ? '#F39C12' : '#ddd',
            width: `${completion}%`, transition: 'width 0.4s ease',
          }} />
        </div>
        {completion < 80 && (
          <div style={{ fontSize: '12px', color: '#999', marginTop: '6px' }}>
            {completion < 30
              ? 'Preencha os campos básicos para começar'
              : completion < 60
              ? 'Adicione mais keywords e suba seu currículo'
              : 'Quase lá — adicione seu LinkedIn e resumo profissional'}
          </div>
        )}
      </div>

      {/* SEÇÃO 1 — Dados básicos */}
      <Section title="Dados básicos" required>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <Field label="Nome completo">
            <Input value={form.name}
              onChange={v => setForm(f => ({ ...f, name: v }))}
              placeholder="Seu nome completo" />
          </Field>
          <Field label="Cargo alvo *">
            <Input value={form.target_role}
              onChange={v => setForm(f => ({ ...f, target_role: v }))}
              placeholder="Ex: Analista de Importação Sênior"
              highlight={!form.target_role} />
          </Field>
          <Field label="Anos de experiência">
            <Input type="number" min="0" max="50"
              value={form.experience_years}
              onChange={v => setForm(f => ({ ...f, experience_years: parseInt(v) || 0 }))}
              placeholder="0" />
          </Field>
          <Field label="Localização">
            <Input value={form.location}
              onChange={v => setForm(f => ({ ...f, location: v }))}
              placeholder="Ex: São Paulo, SP" />
          </Field>
        </div>
        <Field label="Resumo profissional">
          <textarea
            value={form.summary}
            onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
            placeholder="Descreva sua experiência e objetivos em 2-3 frases..."
            rows={3}
            style={{ width: '100%', padding: '10px 12px', borderRadius: '8px',
              border: '1px solid #ddd', fontSize: '14px', resize: 'vertical',
              boxSizing: 'border-box', fontFamily: 'inherit' }}
          />
        </Field>
      </Section>

      {/* SEÇÃO 2 — Currículo */}
      <Section title="Currículo (PDF)">
        <p style={{ fontSize: '13px', color: '#666', margin: '0 0 14px', lineHeight: 1.6 }}>
          O currículo ativo é usado para calcular o score de aderência e gerar
          cartas de apresentação personalizadas por vaga.
        </p>

        {cvFiles.map(cv => (
          <div key={cv} style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '10px 14px', marginBottom: '8px', borderRadius: '8px',
            border: activeCV === cv ? '1.5px solid #1D9E75' : '1px solid #eee',
            background: activeCV === cv ? '#f0faf6' : '#fafafa',
          }}>
            <span style={{ fontSize: '20px' }}>📄</span>
            <span style={{ flex: 1, fontSize: '13px', color: '#333' }}>{cv}</span>
            {activeCV === cv
              ? <span style={{ fontSize: '11px', background: '#1D9E75', color: 'white',
                  padding: '2px 8px', borderRadius: '99px', fontWeight: 500 }}>
                  ✓ Ativo
                </span>
              : <button onClick={() => setActiveCV(cv)}
                  style={{ fontSize: '11px', padding: '4px 10px', border: '1px solid #ddd',
                    borderRadius: '6px', background: 'white', cursor: 'pointer', color: '#555' }}>
                  Usar este
                </button>
            }
          </div>
        ))}

        <label style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '12px 16px',
          border: `2px dashed ${uploadingCV ? '#1D9E75' : '#ddd'}`,
          borderRadius: '8px',
          cursor: uploadingCV ? 'not-allowed' : 'pointer',
          fontSize: '13px',
          color: uploadingCV ? '#1D9E75' : '#888',
          background: uploadingCV ? '#f0faf6' : 'white',
          transition: 'all 0.2s',
        }}>
          <span style={{ fontSize: '20px' }}>{uploadingCV ? '⏳' : '⬆️'}</span>
          {uploadingCV ? 'Enviando...' : 'Clique para enviar um PDF'}
          <input type="file" accept=".pdf" onChange={handleCVUpload}
            disabled={uploadingCV} style={{ display: 'none' }} />
        </label>

        {uploadMsg && (
          <div style={{
            marginTop: '8px', fontSize: '12px', padding: '8px 12px', borderRadius: '6px',
            background: uploadOk ? '#f0faf6' : '#fff0f0',
            color: uploadOk ? '#1D9E75' : '#C0392B',
          }}>
            {uploadOk ? `✅ ${uploadText}` : `❌ ${uploadText}`}
          </div>
        )}
      </Section>

      {/* SEÇÃO 3 — Keywords */}
      <Section title="Habilidades e palavras-chave">
        <p style={{ fontSize: '13px', color: '#666', margin: '0 0 12px', lineHeight: 1.6 }}>
          O agente usa essas palavras para calcular o score de cada vaga.{' '}
          <strong>Quanto mais preciso, melhor o score.</strong>
          {form.keywords.length < 5 && (
            <span style={{ color: '#BA7517' }}> Adicione pelo menos 5.</span>
          )}
        </p>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          <input
            value={keywordInput}
            onChange={e => setKeywordInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
            placeholder="Digite uma habilidade e pressione Enter"
            style={{ flex: 1, padding: '10px 12px', borderRadius: '8px',
              border: '1px solid #ddd', fontSize: '14px' }}
          />
          <button onClick={() => addKeyword()}
            style={{ padding: '10px 18px', background: '#1D9E75', color: 'white',
              border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 500 }}>
            + Add
          </button>
        </div>

        <div style={{ marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#999', marginBottom: '8px' }}>
            Sugestões para sua área — clique para adicionar:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {KEYWORD_SUGGESTIONS.map(kw => {
              const selected = form.keywords.includes(kw)
              return (
                <span key={kw}
                  onClick={() => selected ? removeKeyword(kw) : addKeyword(kw)}
                  style={{
                    padding: '4px 12px', borderRadius: '99px', fontSize: '12px',
                    cursor: 'pointer', userSelect: 'none', transition: 'all 0.15s',
                    background: selected ? '#1D9E75' : '#f0f0f0',
                    color: selected ? 'white' : '#555',
                    fontWeight: selected ? 500 : 400,
                  }}>
                  {selected ? '✓ ' : ''}{kw}
                </span>
              )
            })}
          </div>
        </div>

        {form.keywords.length > 0 && (
          <>
            <div style={{ fontSize: '12px', color: '#1D9E75', fontWeight: 500, marginBottom: '8px' }}>
              {form.keywords.length} {form.keywords.length === 1 ? 'habilidade' : 'habilidades'} selecionadas
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {form.keywords.map(kw => (
                <span key={kw} style={{
                  padding: '4px 10px', background: '#E8F5E9', color: '#1D9E75',
                  borderRadius: '99px', fontSize: '12px',
                  display: 'flex', alignItems: 'center', gap: '6px',
                }}>
                  {kw}
                  <span onClick={() => removeKeyword(kw)}
                    style={{ cursor: 'pointer', opacity: 0.7, fontSize: '14px' }}>×</span>
                </span>
              ))}
            </div>
          </>
        )}
      </Section>

      {/* SEÇÃO 4 — Integrações */}
      <Section title="Integrações (opcional)">
        <Field label="LinkedIn">
          <Input value={form.linkedin_url}
            onChange={v => setForm(f => ({ ...f, linkedin_url: v }))}
            placeholder="https://linkedin.com/in/seu-perfil" />
        </Field>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <Field label="Chat ID do Telegram">
            <Input value={form.telegram_chat_id}
              onChange={v => setForm(f => ({ ...f, telegram_chat_id: v }))}
              placeholder="Ex: 123456789" />
            <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
              Busque @userinfobot no Telegram e envie /start
            </div>
          </Field>
          <Field label={`Score mínimo para alertas: ${form.min_score_notify}/10`}>
            <input type="range" min="4" max="9" step="0.5"
              value={form.min_score_notify}
              onChange={e => setForm(f => ({ ...f, min_score_notify: parseFloat(e.target.value) }))}
              style={{ width: '100%', marginTop: '8px' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between',
              fontSize: '11px', color: '#999', marginTop: '2px' }}>
              <span>4 — mais vagas</span><span>9 — só as melhores</span>
            </div>
          </Field>
        </div>
      </Section>

      {saveError && (
        <div style={{ padding: '12px 16px', background: '#fff0f0', color: '#C0392B',
          borderRadius: '8px', fontSize: '13px', marginBottom: '16px' }}>
          ⚠️ {saveError}
        </div>
      )}

      <button onClick={handleSave} disabled={saving}
        style={{
          width: '100%', padding: '14px',
          background: saved ? '#27AE60' : saving ? '#ccc' : '#1D9E75',
          color: 'white', border: 'none', borderRadius: '10px',
          fontSize: '15px', fontWeight: 500,
          cursor: saving ? 'not-allowed' : 'pointer',
          transition: 'background 0.2s',
        }}>
        {saving ? '⏳ Salvando...'
          : saved ? '✅ Perfil salvo!'
          : isNewUser ? '🚀 Salvar e começar a buscar vagas'
          : 'Salvar alterações'}
      </button>

      {!isNewUser && (
        <div style={{ textAlign: 'center', marginTop: '12px', fontSize: '12px', color: '#bbb' }}>
          Suas alterações serão aplicadas no próximo ciclo de coleta de vagas
        </div>
      )}
    </div>
  )
}

function Section({ title, children, required }) {
  return (
    <div style={{ marginBottom: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px',
        marginBottom: '16px', paddingBottom: '10px', borderBottom: '1px solid #eee' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 500, margin: 0, color: '#222' }}>
          {title}
        </h2>
        {required && (
          <span style={{ fontSize: '10px', background: '#fff3e0', color: '#E65100',
            padding: '2px 7px', borderRadius: '99px', fontWeight: 500 }}>
            Obrigatório
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: '14px' }}>
      <label style={{ fontSize: '13px', fontWeight: 500, color: '#444',
        display: 'block', marginBottom: '6px' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

function Input({ value, onChange, placeholder, type = 'text', highlight, ...rest }) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%', padding: '10px 12px', borderRadius: '8px',
        border: highlight ? '1.5px solid #F39C12' : '1px solid #ddd',
        fontSize: '14px', boxSizing: 'border-box',
        background: highlight ? '#FFFDE7' : 'white',
        outline: 'none',
      }}
      {...rest}
    />
  )
}
