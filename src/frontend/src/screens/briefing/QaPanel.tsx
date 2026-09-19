import { useState } from 'react';
import { api, ApiError, errorMessage } from '../../api/client';
import EvidencePanel from './EvidencePanel';
import type { EvidenceTarget } from '../../lib/evidenceTarget';
import { useI18n } from '../../i18n';
import type { EvidenceIndex, QaResponse } from './briefingTypes';

interface QaPanelProps {
  clientRef: string;
  portfolioNr?: string | null;
  /** Pass the briefing's evidence_index so Q&A evidence can resolve the same visual language. */
  evidenceIndex: EvidenceIndex;
  /** Open an evidence slice where it lives (violations, positions, allocation, notes, the web). */
  onOpenEvidence?: (target: EvidenceTarget) => void;
}

export default function QaPanel({ clientRef, portfolioNr, evidenceIndex, onOpenEvidence }: QaPanelProps) {
  const { lang, t } = useI18n();
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<QaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const data = await api.post<QaResponse>('/api/qa', {
        client_ref: clientRef,
        portfolio_nr: portfolioNr ?? null,
        question: question.trim(),
        lang,
      }, lang);
      setAnswer(data);
    } catch (err) {
      if (err instanceof ApiError && err.status) {
        setError(`${t('qa.error')} (HTTP ${err.status})${err.detail ? ` — ${err.detail}` : ''}`);
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="qa-panel">
      <div className="qa-title">{t('qa.title')}</div>
      <form className="qa-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="qa-input"
          placeholder={t('qa.placeholder')}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="qa-submit" disabled={loading || !question.trim()}>
          {loading ? '…' : t('qa.ask')}
        </button>
      </form>

      {loading ? <div className="qa-loading">{t('qa.creating')}</div> : null}

      {error ? <div className="qa-error">{error}</div> : null}

      {answer ? (
        <>
          {answer.source_kind === 'web' ? (
            <div className="qa-web-chip">{t('qa.webSource')}</div>
          ) : answer.answered_by === 'llm' ? (
            <div className="qa-web-chip">{t('qa.answeredByLlm')}</div>
          ) : null}

          <div className="qa-answer">
            {answer.answer.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
              part.startsWith('**') && part.endsWith('**') ? (
                <strong key={i}>{part.slice(2, -2)}</strong>
              ) : (
                <span key={i}>{part}</span>
              ),
            )}
          </div>

          {answer.sources.length > 0 ? (
            <div className="qa-sources">
              <div className="qa-sources-title">{t('qa.webSources')}</div>
              <ul style={{ margin: 0, paddingLeft: 'var(--space-4)' }}>
                {answer.sources.map((source, i) => (
                  <li key={i}>
                    {source.url ? (
                      <a href={source.url} target="_blank" rel="noopener noreferrer">
                        {source.title || source.url}
                      </a>
                    ) : (
                      source.title
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {answer.unavailable.length > 0 ? (
            <div className="qa-unavailable">
              <div className="qa-unavailable-title">{t('qa.notAvailable')}</div>
              <ul style={{ margin: 0, paddingLeft: 'var(--space-4)' }}>
                {answer.unavailable.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {answer.evidence.length > 0 ? (
            <EvidencePanel
              refs={[]}
              index={evidenceIndex}
              heading={t('qa.evidence')}
              inline={answer.evidence}
              onOpen={onOpenEvidence}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
