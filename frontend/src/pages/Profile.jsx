import { useState, useEffect } from 'react'
import axios from 'axios'

const BASE = 'http://localhost:8000/api'

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '8px',
  border: '1px solid #ddd',
  fontSize: '14px',
  boxSizing: 'border-box',
  outline: 'none',
  fontFamily: 'inherit',
}

const KEYWORD_SUGGESTIONS = [
  'importação', 'exportação', 'SISCOMEX', 'NCM', 'drawback',
  'Incoterms', 'supply chain', 'logística', 'ANVISA',
  'Receita Federal', 'despacho aduaneiro', 'licença de importação',
  'DI', 'LI', 'comércio exterior', 'freight', 'armazenagem',
  'compliance', 'cold chain', 'GLP', 'farmacêutico',
]

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: '32px' }}>
      <h2 style={{
        fontSize: '14px', fontWeight: 600, color: '#333',
        marginBottom: '16px', paddingBottom: '8px',
        borderBottom: '1px solid #eee',
      }}>
        {title}
      </h2>
      {children}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: '14px' }}>
      <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

function Row({ children }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
      {children}
    </div>
  )
}

export default function Profile() {
  const [form, setForm] = useState({
    name: '',
    target_role: '',
    experience_years: 0,
    location: 'São Paulo, SP',
    summary: '',
    keywords: [],
    languages: [],
    education: '',
    linkedin_url: '',
    telegram_chat_id: '',
    min_score_notify: 6.0,
  })
  const [cvFiles, setCvFiles] = useState([])
  const [activeCV, setActiveCV] = useState('')
  const [keywordInput, setKeywordInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    axios.get(`${BASE}/profile/`)
      .then(r => {
        const d = r.data
        setForm(f => ({
          ...f,
          name: d.name || '',
          target_role: d.target_role || '',
          experience_years: d.experience_years || 0,
          location: d.location || 'São Paulo, SP',
          summary: d.summary || '',
          keywords: Array.isArray(d.keywords) ? d.keywords : [],
          languages: Array.isArray(d.languages) ? d.languages : [],
          education: d.education || '',
          linkedin_url: d.linkedin_url || '',
          telegram_chat_id: d.telegram_chat_id || '',
          min_score_notify: d.min_score_notify || 6.0,
        }))
        if (d.cv_files) setCvFiles(d.cv_files)
        if (d.active_cv) setActiveCV(d.active_cv)
      })
      .catch(() => {})

    axios.get(`${BASE}/profile/cvs`)
      .then(r => {
        setCvFiles(r.data.files || [])
        setActiveCV(r.data.active || '')
      })
      .catch(() => {})
  }, [])

  const handleCVUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    if (!file.name.endsWith('.pdf')) {
      alert('Apenas arquivos PDF são aceitos')
      return
    }
    const formData = new FormData()
    formData.append('file', file)
    try {
      const r = await axios.post(`${BASE}/profile/upload-cv`, formData)
      if (r.data.success) {
        setCvFiles(prev => prev.includes(r.data.filename) ? prev : [...prev, r.data.filename])
        if (!activeCV) setActiveCV(r.data.filename)
      }
    } catch {
      alert('Erro ao enviar arquivo')
    }
    e.target.value = ''
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await axios.put(`${BASE}/profile/`, { ...form, active_cv: activeCV })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setError('Erro ao salvar perfil. Verifique se a API está rodando.')
    } finally {
      setSaving(false)
    }
  }

  const addKeyword = () => {
    const kw = keywordInput.trim()
    if (kw && !form.keywords.includes(kw)) {
      setForm(f => ({ ...f, keywords: [...f.keywords, kw] }))
    }
    setKeywordInput('')
  }

  const removeKeyword = (kw) => setForm(f => ({ ...f, keywords: f.keywords.filter(k => k !== kw) }))

  const toggleSuggestion = (kw) => {
    if (form.keywords.includes(kw)) {
      removeKeyword(kw)
    } else {
      setForm(f => ({ ...f, keywords: [...f.keywords, kw] }))
    }
  }

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '32px 24px' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 600, marginBottom: '8px' }}>Meu Perfil</h1>
      <p style={{ fontSize: '13px', color: '#666', marginBottom: '32px' }}>
        Suas informações são usadas para calcular o score de cada vaga e gerar cartas de apresentação personalizadas.
      </p>

      <Section title="Dados básicos">
        <Field label="Nome completo">
          <input style={inputStyle} value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Seu nome completo" />
        </Field>
        <Field label="Cargo alvo *">
          <input style={inputStyle} value={form.target_role}
            onChange={e => setForm(f => ({ ...f, target_role: e.target.value }))}
            placeholder="Ex: Analista de Importação Sênior" />
        </Field>
        <Row>
          <Field label="Anos de experiência">
            <input style={inputStyle} type="number" min="0" max="50"
              value={form.experience_years}
              onChange={e => setForm(f => ({ ...f, experience_years: parseInt(e.target.value) || 0 }))} />
          </Field>
          <Field label="Localização">
            <input style={inputStyle} value={form.location}
              onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
              placeholder="Ex: São Paulo, SP" />
          </Field>
        </Row>
        <Field label="Resumo profissional">
          <textarea style={{ ...inputStyle, resize: 'vertical' }} rows={3} value={form.summary}
            onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
            placeholder="Descreva sua experiência e objetivos em 2-3 frases..." />
        </Field>
      </Section>

      <Section title="Meus currículos">
        <p style={{ fontSize: '13px', color: '#666', marginBottom: '16px' }}>
          Suba diferentes versões do seu CV (PDF). O currículo ativo é usado para calcular o score e gerar cartas de apresentação.
        </p>

        {cvFiles.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            {cvFiles.map(cv => (
              <div key={cv} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '10px 14px', background: '#f9f9f9',
                borderRadius: '8px', marginBottom: '8px',
                border: activeCV === cv ? '2px solid #1D9E75' : '1px solid #eee',
              }}>
                <span style={{ fontSize: '18px' }}>PDF</span>
                <span style={{ flex: 1, fontSize: '13px' }}>{cv}</span>
                {activeCV === cv ? (
                  <span style={{
                    fontSize: '11px', background: '#E8F5E9', color: '#1D9E75',
                    padding: '2px 8px', borderRadius: '99px', fontWeight: 500,
                  }}>
                    Ativo
                  </span>
                ) : (
                  <button onClick={() => setActiveCV(cv)}
                    style={{
                      fontSize: '11px', background: 'transparent', border: '1px solid #ddd',
                      borderRadius: '6px', padding: '4px 10px', cursor: 'pointer',
                    }}>
                    Usar este
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        <label style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '12px 16px', border: '2px dashed #ddd',
          borderRadius: '8px', cursor: 'pointer', fontSize: '13px', color: '#666',
        }}>
          <span>Enviar novo curriculo (PDF)</span>
          <input type="file" accept=".pdf" onChange={handleCVUpload} style={{ display: 'none' }} />
        </label>
      </Section>

      <Section title="Habilidades e palavras-chave">
        <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
          Palavras-chave que aparecem na sua área. O agente usa isso para calcular o score de aderência de cada vaga.
        </p>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          <input
            style={{ ...inputStyle, flex: 1 }}
            value={keywordInput}
            onChange={e => setKeywordInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
            placeholder="Digite uma habilidade e pressione Enter"
          />
          <button onClick={addKeyword}
            style={{
              padding: '8px 16px', background: '#1D9E75', color: 'white',
              border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px',
            }}>
            + Add
          </button>
        </div>

        <div style={{ marginBottom: '12px' }}>
          <span style={{ fontSize: '11px', color: '#999', marginBottom: '6px', display: 'block' }}>
            Sugestões para sua área:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {KEYWORD_SUGGESTIONS.map(kw => (
              <span key={kw} onClick={() => toggleSuggestion(kw)}
                style={{
                  padding: '3px 10px', borderRadius: '99px', fontSize: '12px', cursor: 'pointer',
                  background: form.keywords.includes(kw) ? '#1D9E75' : '#f0f0f0',
                  color: form.keywords.includes(kw) ? 'white' : '#555',
                }}>
                {kw}
              </span>
            ))}
          </div>
        </div>

        {form.keywords.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {form.keywords.map(kw => (
              <span key={kw} style={{
                padding: '4px 10px', background: '#E8F5E9', color: '#1D9E75',
                borderRadius: '99px', fontSize: '12px',
                display: 'flex', alignItems: 'center', gap: '6px',
              }}>
                {kw}
                <span onClick={() => removeKeyword(kw)}
                  style={{ cursor: 'pointer', opacity: 0.7, fontWeight: 'bold' }}>x</span>
              </span>
            ))}
          </div>
        )}
      </Section>

      <Section title="Integracoes">
        <Field label="URL do LinkedIn">
          <input style={inputStyle} value={form.linkedin_url}
            onChange={e => setForm(f => ({ ...f, linkedin_url: e.target.value }))}
            placeholder="https://linkedin.com/in/seu-perfil" />
        </Field>
        <Field label="Chat ID do Telegram (para alertas)">
          <input style={inputStyle} value={form.telegram_chat_id}
            onChange={e => setForm(f => ({ ...f, telegram_chat_id: e.target.value }))}
            placeholder="Ex: 123456789" />
          <span style={{ fontSize: '11px', color: '#999', marginTop: '4px', display: 'block' }}>
            Para obter: abra o Telegram, busque @userinfobot e envie /start
          </span>
        </Field>
        <Field label={`Score minimo para notificar: ${form.min_score_notify}/10`}>
          <input type="range" min="4" max="9" step="0.5"
            value={form.min_score_notify}
            onChange={e => setForm(f => ({ ...f, min_score_notify: parseFloat(e.target.value) }))}
            style={{ width: '100%' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#999' }}>
            <span>4 — Mais vagas</span>
            <span>9 — So as melhores</span>
          </div>
        </Field>
      </Section>

      {error && (
        <div style={{ background: '#fff0f0', border: '1px solid #ffcccc', borderRadius: '8px', padding: '12px', marginBottom: '16px', fontSize: '13px', color: '#c00' }}>
          {error}
        </div>
      )}

      <button onClick={handleSave} disabled={saving}
        style={{
          width: '100%', padding: '14px', background: saving ? '#aaa' : saved ? '#0d7a5a' : '#1D9E75',
          color: 'white', border: 'none', borderRadius: '10px',
          fontSize: '15px', fontWeight: 500, cursor: saving ? 'not-allowed' : 'pointer',
          transition: 'background 0.2s',
        }}>
        {saving ? 'Salvando...' : saved ? 'Perfil salvo!' : 'Salvar perfil'}
      </button>
    </div>
  )
}
