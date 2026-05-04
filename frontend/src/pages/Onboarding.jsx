import { useState, useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { AuthContext } from '../components/AuthContext'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const KEYWORD_SUGGESTIONS = [
  'importação', 'exportação', 'SISCOMEX', 'NCM', 'drawback',
  'Incoterms', 'supply chain', 'logística', 'ANVISA',
  'Receita Federal', 'despacho aduaneiro', 'licença de importação',
  'DI', 'LI', 'comércio exterior', 'freight', 'armazenagem',
  'compliance', 'cold chain', 'GLP', 'farmacêutico',
]

const inputStyle = {
  width: '100%', padding: '10px 12px', borderRadius: '8px',
  border: '1px solid #ddd', fontSize: '14px', boxSizing: 'border-box',
  outline: 'none', fontFamily: 'inherit',
}

const STEPS = ['Cargo alvo', 'Experiência', 'Habilidades', 'Notificações']

export default function Onboarding() {
  const navigate = useNavigate()
  const { api: ctxApi } = useContext(AuthContext) || {}
  const baseApi = ctxApi || API

  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    target_role: '',
    experience_years: 0,
    location: 'São Paulo, SP',
    summary: '',
    keywords: [],
    telegram_chat_id: '',
    min_score_notify: 6.0,
  })

  const [keywordInput, setKeywordInput] = useState('')

  const update = (field, value) => setForm(f => ({ ...f, [field]: value }))

  const addKeyword = () => {
    const kw = keywordInput.trim()
    if (kw && !form.keywords.includes(kw)) {
      update('keywords', [...form.keywords, kw])
    }
    setKeywordInput('')
  }

  const toggleSuggestion = (kw) => {
    if (form.keywords.includes(kw)) {
      update('keywords', form.keywords.filter(k => k !== kw))
    } else {
      update('keywords', [...form.keywords, kw])
    }
  }

  const next = () => {
    if (step === 0 && !form.target_role.trim()) {
      setError('Informe o cargo que você busca para continuar.')
      return
    }
    setError('')
    setStep(s => s + 1)
  }

  const finish = async () => {
    setSaving(true)
    setError('')
    try {
      await axios.post(`${baseApi}/auth/onboarding/complete`, form, { timeout: 10000 })
      navigate('/vagas')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao salvar. Tente novamente.')
    } finally {
      setSaving(false)
    }
  }

  const progress = ((step + 1) / STEPS.length) * 100

  return (
    <div style={{
      minHeight: '100vh', background: '#f8f9fa',
      display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      paddingTop: '48px', paddingBottom: '48px',
    }}>
      <div style={{
        background: 'white', borderRadius: '16px', padding: '40px 44px',
        width: '100%', maxWidth: '520px',
        boxShadow: '0 4px 32px rgba(0,0,0,0.08)',
      }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '13px', color: '#888' }}>
              Passo {step + 1} de {STEPS.length} — {STEPS[step]}
            </span>
            <span style={{ fontSize: '13px', color: '#1D9E75', fontWeight: 500 }}>
              {Math.round(progress)}%
            </span>
          </div>
          <div style={{ height: '4px', background: '#eee', borderRadius: '99px' }}>
            <div style={{
              height: '4px', background: '#1D9E75', borderRadius: '99px',
              width: `${progress}%`, transition: 'width 0.3s ease',
            }} />
          </div>
        </div>

        {/* Step 0 — Cargo alvo */}
        {step === 0 && (
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>
              Qual cargo você busca?
            </h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '24px' }}>
              Esse é o campo mais importante — o agente usa para encontrar vagas compatíveis.
            </p>
            <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
              Cargo alvo *
            </label>
            <input
              style={{ ...inputStyle, fontSize: '15px' }}
              value={form.target_role}
              onChange={e => update('target_role', e.target.value)}
              placeholder="Ex: Analista de Importação Sênior"
              autoFocus
            />
          </div>
        )}

        {/* Step 1 — Experiência */}
        {step === 1 && (
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>
              Sua experiência
            </h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '24px' }}>
              Usado para filtrar vagas por nível de senioridade.
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
                Anos de experiência: {form.experience_years}
              </label>
              <input type="range" min="0" max="20" step="1"
                value={form.experience_years}
                onChange={e => update('experience_years', parseInt(e.target.value))}
                style={{ width: '100%' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#999', marginTop: '4px' }}>
                <span>0 — Estágio</span>
                <span>5 — Pleno</span>
                <span>10 — Sênior</span>
                <span>20+</span>
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
                Localização
              </label>
              <input
                style={inputStyle}
                value={form.location}
                onChange={e => update('location', e.target.value)}
                placeholder="Ex: São Paulo, SP"
              />
            </div>

            <div>
              <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
                Resumo profissional (opcional)
              </label>
              <textarea
                style={{ ...inputStyle, resize: 'vertical' }}
                rows={3}
                value={form.summary}
                onChange={e => update('summary', e.target.value)}
                placeholder="Descreva sua experiência em 2-3 frases..."
              />
            </div>
          </div>
        )}

        {/* Step 2 — Habilidades */}
        {step === 2 && (
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>
              Suas habilidades
            </h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '20px' }}>
              Selecione palavras-chave da sua área. O agente usa para calcular o score de cada vaga.
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

            <div style={{ marginBottom: '16px' }}>
              <span style={{ fontSize: '11px', color: '#999', marginBottom: '8px', display: 'block' }}>
                Sugestões — clique para selecionar:
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {KEYWORD_SUGGESTIONS.map(kw => {
                  const sel = form.keywords.includes(kw)
                  return (
                    <span key={kw} onClick={() => toggleSuggestion(kw)}
                      style={{
                        padding: '5px 12px', borderRadius: '99px', fontSize: '12px',
                        cursor: 'pointer', userSelect: 'none',
                        background: sel ? '#1D9E75' : '#f0f0f0',
                        color: sel ? 'white' : '#555',
                        border: sel ? '2px solid #1D9E75' : '2px solid transparent',
                        fontWeight: sel ? 500 : 400,
                        transition: 'all 0.15s',
                      }}>
                      {sel ? '✓ ' : ''}{kw}
                    </span>
                  )
                })}
              </div>
            </div>

            {form.keywords.length > 0 && (
              <div style={{ fontSize: '12px', color: '#1D9E75', fontWeight: 500 }}>
                {form.keywords.length} {form.keywords.length === 1 ? 'habilidade selecionada' : 'habilidades selecionadas'}
              </div>
            )}
          </div>
        )}

        {/* Step 3 — Notificações */}
        {step === 3 && (
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>
              Alertas por Telegram
            </h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '24px' }}>
              Receba notificações quando uma vaga com bom score aparecer. Você pode pular por agora.
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
                Chat ID do Telegram (opcional)
              </label>
              <input
                style={inputStyle}
                value={form.telegram_chat_id}
                onChange={e => update('telegram_chat_id', e.target.value)}
                placeholder="Ex: 123456789"
              />
              <span style={{ fontSize: '11px', color: '#999', marginTop: '4px', display: 'block' }}>
                Para obter: no Telegram, busque @userinfobot e envie /start
              </span>
            </div>

            <div>
              <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '6px', color: '#444' }}>
                Score mínimo para notificar: {form.min_score_notify}/10
              </label>
              <input type="range" min="4" max="9" step="0.5"
                value={form.min_score_notify}
                onChange={e => update('min_score_notify', parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#999' }}>
                <span>4 — Mais vagas</span>
                <span>9 — Só as melhores</span>
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            marginTop: '16px', padding: '10px 14px',
            background: '#FFF0F0', color: '#C0392B',
            borderRadius: '8px', fontSize: '13px',
          }}>
            {error}
          </div>
        )}

        {/* Navigation */}
        <div style={{ display: 'flex', gap: '12px', marginTop: '32px' }}>
          {step > 0 && (
            <button onClick={() => setStep(s => s - 1)}
              style={{
                flex: 1, padding: '12px',
                background: 'white', color: '#555',
                border: '1px solid #ddd', borderRadius: '10px',
                fontSize: '14px', cursor: 'pointer',
              }}>
              Voltar
            </button>
          )}

          {step < STEPS.length - 1 ? (
            <button onClick={next}
              style={{
                flex: 2, padding: '12px',
                background: '#1D9E75', color: 'white',
                border: 'none', borderRadius: '10px',
                fontSize: '15px', fontWeight: 500, cursor: 'pointer',
              }}>
              Continuar
            </button>
          ) : (
            <button onClick={finish} disabled={saving}
              style={{
                flex: 2, padding: '12px',
                background: saving ? '#a8d5c4' : '#1D9E75',
                color: 'white', border: 'none', borderRadius: '10px',
                fontSize: '15px', fontWeight: 500,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}>
              {saving ? 'Salvando...' : 'Iniciar — ver vagas'}
            </button>
          )}
        </div>

        {step === STEPS.length - 1 && (
          <button onClick={() => navigate('/vagas')}
            style={{
              width: '100%', marginTop: '10px', padding: '8px',
              background: 'none', border: 'none', color: '#aaa',
              fontSize: '12px', cursor: 'pointer', textDecoration: 'underline',
            }}>
            Pular por enquanto
          </button>
        )}
      </div>
    </div>
  )
}
