import { useEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError, preferredRenderer } from '../../api/client';
import { formatDate } from '../../utils/format';
import EvidencePanel from './EvidencePanel';
import type { EvidenceTarget } from '../../lib/evidenceTarget';
import QaPanel from './QaPanel';
import type {
  Briefing,
  BriefingBlock,
  BriefingResponse,
  Facts,
  PipelineStage,
} from './briefingTypes';
import { useI18n, type MessageKey } from '../../i18n';
import './briefing.css';

interface Props {
  clientRef: string;
  portfolioNr?: string | null;
  onBack: () => void;
  /** Opens the market search for an instrument the briefing talks about (its ISIN). */
  onOpenMarket?: (isin: string) => void;
  /** Open an evidence slice where it lives (violations, positions, allocation, notes, the web). */
  onOpenEvidence?: (target: EvidenceTarget) => void;
}

type ScreenState =
  | { kind: 'running'; stages: PipelineStage[] }
  | { kind: 'success'; data: BriefingResponse }
  | { kind: 'failure'; error: string }
  | { kind: 'empty' };

interface Provenance {
  hasLive: boolean;
  hasMock: boolean;
  hasSimulated: boolean;
  liveLabel: string;
  mockLabel: string;
  simulatedLabel: string;
}

interface LoadedProps {
  data: BriefingResponse;
  onBack: () => void;
  onOpenMarket: (isin: string) => void;
  onOpenEvidence?: (target: EvidenceTarget) => void;
  selectedRefs: string[] | null;
  selectedHeading: string | undefined;
  onSelectBlock: (refs: string[], heading?: string) => void;
  provenance: Provenance;
  stages: PipelineStage[];
}

const STAGE_KEYS: Record<string, MessageKey> = {
  collect: 'briefing.stageCollect',
  analyse: 'briefing.stageAnalyse',
  rules: 'briefing.stageRules',
  market: 'briefing.stageMarket',
  house_view: 'briefing.stageHouseView',
  actions: 'briefing.stageActions',
  compose: 'briefing.stageCompose',
};

const STAGE_ORDER = ['collect', 'analyse', 'rules', 'market', 'house_view', 'actions', 'compose'];

type QuestionRefsKey = 'what_happened_refs' | 'situation_refs' | 'next_refs' | 'should_do_refs';
const QUESTION_KEYS: { key: keyof Briefing['questions']; label: MessageKey; refsKey: QuestionRefsKey }[] = [
  { key: 'what_happened', label: 'briefing.whatHappened', refsKey: 'what_happened_refs' },
  { key: 'situation', label: 'briefing.situation', refsKey: 'situation_refs' },
  { key: 'next', label: 'briefing.next', refsKey: 'next_refs' },
  { key: 'should_do', label: 'briefing.shouldDo', refsKey: 'should_do_refs' },
];

/** Render `**bold**` leads as real <strong> tags; pass everything else through. */
function renderRich(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function blockClassName(block: BriefingBlock): string {
  const base = 'briefing-block';
  if (block.source_kind === 'gap') return `${base} briefing-block--gap`;
  if (block.source_kind === 'mock') return `${base} briefing-block--mock`;
  if (block.source_kind === 'external') return `${base} briefing-block--external`;
  if (block.severity === 'high') return `${base} briefing-block--high`;
  if (block.severity === 'medium') return `${base} briefing-block--medium`;
  if (block.severity === 'low') return `${base} briefing-block--low`;
  return base;
}

function sourceKindLabel(kind: BriefingBlock['source_kind'], t: (key: MessageKey) => string): string | null {
  if (kind === 'mock') return t('briefing.sourceMock');
  if (kind === 'external') return t('briefing.sourceExternal');
  if (kind === 'gap') return t('briefing.sourceGap');
  return null;
}

type T = (key: MessageKey, vars?: Record<string, string | number>) => string;

function buildProvenance(facts: Facts, t: T): Provenance {
  const hasLive =
    facts.market_meta.queried &&
    !facts.market_meta.is_mock &&
    facts.market_meta.providers_used.length > 0;
  const hasMock = facts.house_view.mock === true;
  const hasSimulated = facts.portfolios.length > 0;

  const liveLabel = hasLive
    ? `${t('briefing.marketData')} (${facts.market_meta.providers_used.join(', ')})`
    : t('briefing.marketData');
  const mockLabel = hasMock
    ? `${t('briefing.bankView')} (${facts.house_view.source || t('briefing.mockSource')})`
    : t('briefing.bankView');
  const simulatedLabel = hasSimulated
    ? t('briefing.portfolioDataFromBank', { count: facts.portfolios.length })
    : t('briefing.portfolioData');

  return { hasLive, hasMock, hasSimulated, liveLabel, mockLabel, simulatedLabel };
}

export default function BriefingScreen({
  clientRef,
  portfolioNr,
  onBack,
  onOpenMarket,
  onOpenEvidence,
}: Props) {
  const { lang, t } = useI18n();
  const [state, setState] = useState<ScreenState>({ kind: 'running', stages: [] });
  const [selectedRefs, setSelectedRefs] = useState<string[] | null>(null);
  const [selectedHeading, setSelectedHeading] = useState<string | undefined>(undefined);
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef<number>(Date.now());
  useEffect(() => {
    let cancelled = false;
    startTimeRef.current = Date.now();
    setElapsed(0);
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);

    const run = async () => {
      try {
        const data = await api.briefing<BriefingResponse>(
          {
            client_ref: clientRef,
            portfolio_nr: portfolioNr ?? null,
            renderer: await preferredRenderer(lang),
            lang,
          },
          lang,
        );

        if (cancelled) return;

        if (!data.briefing.sections || data.briefing.sections.length === 0) {
          setState({ kind: 'empty' });
        } else {
          setState({ kind: 'success', data });
        }
      } catch (err) {
        if (cancelled) return;
        
        // The server's own reason when it sent a plain string ("Unknown client CASE-NOPE"); a
        // structured detail is never dumped at the advisor.
        const apiError = err instanceof ApiError ? err : null;
        const errorMsg = apiError?.status
          ? t('briefing.failureHttp', { status: apiError.status }) +
            (apiError.detail ? ` — ${apiError.detail}` : '')
          : t('briefing.failureNetwork');

        setState({ kind: 'failure', error: errorMsg });
      }
    };

    run();
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [clientRef, portfolioNr, lang, t]);

  const handleSelectBlock = (refs: string[], heading?: string) => {
    setSelectedRefs(refs);
    setSelectedHeading(heading);
  };

  const handleCancel = () => {
    onBack();
  };

  if (state.kind === 'running') {
    return (
      <div className="briefing-shell">
        <div className="briefing-topbar">
          <button type="button" className="briefing-back" onClick={onBack}>
            ← {t('briefing.back')}
          </button>
        </div>
        <div className="briefing-running">
          <div className="briefing-running-title">{t('briefing.creating')}</div>
          <div className="briefing-running-sub">
            {t('briefing.pipelineFor', { client: clientRef })}
            {portfolioNr ? ` · ${t('briefing.portfolioNr', { nr: portfolioNr })}` : ''}
          </div>
          <div className="briefing-running-sub" style={{ marginTop: 'var(--space-1)' }}>
            {t('briefing.elapsed', { seconds: elapsed })}
          </div>
          <div className="briefing-stages">
            {STAGE_ORDER.map((id) => {
              const reported = state.stages.find((s) => s.id === id);
              return (
                <div
                  key={id}
                  className={`briefing-stage ${
                    reported ? `briefing-stage--${reported.status}` : 'briefing-stage--pending'
                  }`}
                >
                  <span className="briefing-stage-dot" />
                  <span className="briefing-stage-label">
                    {reported?.label ?? t(STAGE_KEYS[id] ?? 'briefing.pipeline')}
                  </span>
                  {reported ? (
                    <span className="briefing-stage-ms">{reported.ms} ms</span>
                  ) : (
                    <span className="briefing-stage-ms">{t('briefing.waiting')}</span>
                  )}
                </div>
              );
            })}
          </div>
          <button
            type="button"
            className="briefing-back"
            style={{ marginTop: 'var(--space-3)' }}
            onClick={handleCancel}
          >
            {t('briefing.cancel')}
          </button>
        </div>
      </div>
    );
  }

  if (state.kind === 'failure') {
    return (
      <div className="briefing-shell">
        <div className="briefing-topbar">
          <button type="button" className="briefing-back" onClick={onBack}>
            ← {t('briefing.back')}
          </button>
        </div>
        <div className="screen-error">
          <div style={{ fontWeight: 700, marginBottom: 4 }}>{t('briefing.couldNotCreate')}</div>
          <div>{state.error}</div>
          <button
            type="button"
            className="briefing-back"
            style={{ marginTop: 'var(--space-3)' }}
            onClick={() => setState({ kind: 'running', stages: [] })}
          >
            {t('briefing.retry')}
          </button>
        </div>
      </div>
    );
  }

  if (state.kind === 'empty') {
    return (
      <div className="briefing-shell">
        <div className="briefing-topbar">
          <button type="button" className="briefing-back" onClick={onBack}>
            ← {t('briefing.back')}
          </button>
        </div>
        <div className="screen-error" style={{ borderColor: 'var(--warning)' }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>{t('briefing.noSections')}</div>
          <div>
            {t('briefing.noContentFound', { client: clientRef })}
            {portfolioNr ? ` (${t('briefing.portfolioNr', { nr: portfolioNr })})` : ''}
          </div>
          <button
            type="button"
            className="briefing-back"
            style={{ marginTop: 'var(--space-3)' }}
            onClick={() => setState({ kind: 'running', stages: [] })}
          >
            {t('briefing.retry')}
          </button>
        </div>
      </div>
    );
  }

  const { data } = state;
  const { facts, stages } = data;
  const provenance = buildProvenance(facts, t);

  return (
    <BriefingLoaded
      data={data}
      onBack={onBack}
      onOpenMarket={onOpenMarket ?? (() => {})}
      onOpenEvidence={onOpenEvidence}
      selectedRefs={selectedRefs}
      selectedHeading={selectedHeading}
      onSelectBlock={handleSelectBlock}
      provenance={provenance}
      stages={stages}
    />
  );
}

function BriefingLoaded({
  data,
  onBack,
  onOpenMarket,
  onOpenEvidence,
  selectedRefs,
  selectedHeading,
  onSelectBlock,
  provenance,
  stages,
}: LoadedProps) {
  const { t } = useI18n();
  const { briefing, facts } = data;

  const unavailable = facts.meta.unavailable;
  const actions = useMemo(() => [...facts.actions].sort((a, b) => a.priority - b.priority), [facts.actions]);

  return (
    <div className="briefing-shell">
      <div className="briefing-topbar">
        <button type="button" className="briefing-back" onClick={onBack}>
          ← {t('briefing.back')}
        </button>
      </div>

      <div className="briefing-header">
        <div className="briefing-title">
          {briefing.client_name}{' '}
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· {briefing.client_ref}</span>
        </div>
        <div className="briefing-meta">
          <span>{t('briefing.dataAsOf', { date: formatDate(facts.meta.data_as_of) })}</span>
          <span className="briefing-meta-sep">·</span>
          <span>{t('briefing.readTime', { seconds: briefing.read_seconds_estimate })}</span>
          <span className="briefing-meta-sep">·</span>
          <span>{t('briefing.wordCount', { count: briefing.word_count })}</span>
        </div>
      </div>

      <div className="briefing-provenance">
        <span style={{ fontWeight: 600 }}>{t('briefing.provenance')}</span>
        {provenance.hasSimulated ? (
          <span className="provenance-chip provenance-chip--simulated">
            {t('briefing.simulated')} · {provenance.simulatedLabel}
          </span>
        ) : null}
        {provenance.hasLive ? (
          <span className="provenance-chip provenance-chip--live">
            {t('briefing.live')} · {provenance.liveLabel}
          </span>
        ) : (
          <span className="provenance-chip provenance-chip--simulated">
            {t('briefing.simulated')} · {provenance.liveLabel}
          </span>
        )}
        {provenance.hasMock ? (
          <span className="provenance-chip provenance-chip--mock">
            {t('briefing.mock')} · {provenance.mockLabel}
          </span>
        ) : null}
      </div>

      <div className="briefing-grid">
        <div className="briefing-main">
          {briefing.sections.map((section) => (
            <div key={section.id} className="briefing-section">
              <div className="briefing-section-title">{section.title}</div>
              {section.blocks.length === 0 ? (
                <div className="briefing-block briefing-block--note">
                  {t('briefing.noInfoForSection')}
                </div>
              ) : (
                section.blocks.map((block, i) => {
                  const isNote = block.evidence_refs.length === 0;
                  const tag = sourceKindLabel(block.source_kind, t);
                  return (
                    <div key={i} className={isNote ? 'briefing-block briefing-block--note' : blockClassName(block)}>
                      {tag && !isNote ? <span className="briefing-block-tag">{tag}</span> : null}
                      <div className="briefing-block-text">{renderRich(block.text)}</div>
                      {!isNote ? (
                        <button
                          type="button"
                          className={`briefing-trace-btn ${
                            selectedRefs === block.evidence_refs ? 'briefing-trace-btn--active' : ''
                          }`}
                          onClick={() =>
                            onSelectBlock(
                              block.evidence_refs,
                              `${section.title} · ${t('briefing.block', { n: i + 1 })}`,
                            )
                          }
                        >
                          <TraceIcon /> {t('briefing.evidenceCount', { count: block.evidence_refs.length })}
                        </button>
                      ) : null}
                      {!isNote && block.isin ? (
                        <button
                          type="button"
                          className="briefing-market-btn"
                          onClick={() => onOpenMarket(block.isin as string)}
                        >
                          <MarketIcon /> {t('briefing.marketResults')}
                        </button>
                      ) : null}
                    </div>
                  );
                })
              )}
            </div>
          ))}

          <div className="briefing-section">
            <div className="briefing-section-title">{t('briefing.fourQuestions')}</div>
            <div className="briefing-questions">
              {QUESTION_KEYS.map(({ key, label, refsKey }) => {
                const text = briefing.questions[key];
                if (typeof text !== 'string') return null;
                const refs = briefing.questions[refsKey] as string[];
                return (
                  <div key={key} className="briefing-q">
                    <div className="briefing-q-label">{t(label)}</div>
                    <div className="briefing-q-text">{renderRich(text)}</div>
                    {refs.length > 0 ? (
                      <button
                        type="button"
                        className={`briefing-trace-btn ${
                          selectedRefs === refs ? 'briefing-trace-btn--active' : ''
                        }`}
                        style={{ alignSelf: 'flex-start', marginTop: 'var(--space-1)' }}
                        onClick={() => onSelectBlock(refs, t(label))}
                      >
                        <TraceIcon /> {t('briefing.evidenceCount', { count: refs.length })}
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>

          {briefing.client_questions.length > 0 ? (
            <div className="briefing-section">
              <div className="briefing-section-title">{t('briefing.clientQuestions')}</div>
              <div className="briefing-questions">
                {briefing.client_questions.map((item, i) => (
                  <div key={i} className="briefing-q">
                    <div className="briefing-q-text">{renderRich(item.question)}</div>
                    {item.evidence_refs.length > 0 ? (
                      <button
                        type="button"
                        className="briefing-trace-btn"
                        style={{ alignSelf: 'flex-start', marginTop: 'var(--space-1)' }}
                        onClick={() =>
                          onSelectBlock(item.evidence_refs, t('briefing.clientQuestion', { n: i + 1 }))
                        }
                      >
                        <TraceIcon /> {t('briefing.evidenceCount', { count: item.evidence_refs.length })}
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {actions.length > 0 ? (
            <div className="briefing-section">
              <div className="briefing-section-title">{t('briefing.actions')}</div>
              <div className="briefing-actions">
                {actions.map((action) => (
                  <div key={action.id} className="briefing-action">
                    <div className="briefing-action-prio">{action.priority}</div>
                    <div className="briefing-action-body">
                      <div className="briefing-action-text">{action.action}</div>
                      <div className="briefing-action-rationale">{action.rationale}</div>
                      {action.finding_refs.length > 0 ? (
                        <div className="briefing-action-finding">
                          {t('briefing.from')} {action.finding_refs.join(', ')}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {unavailable.length > 0 ? (
            <div className="briefing-gaps">
              <div className="briefing-gaps-title">{t('briefing.unavailableData')}</div>
              <ul>
                {unavailable.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="briefing-side">
          {/* First in the rail: it is the one interactive block here. Evidence fills only after a
              block is clicked and the pipeline timings are diagnostics, so both belong below it —
              at the bottom the assistant was below the fold on a laptop. */}
          <QaPanel
            clientRef={briefing.client_ref}
            portfolioNr={facts.meta.scope.portfolio_nr}
            evidenceIndex={briefing.evidence_index}
            onOpenEvidence={onOpenEvidence}
          />

          <div className="evidence-panel">
            <div className="evidence-panel-title">{selectedHeading ?? t('briefing.evidence')}</div>
            {selectedRefs === null ? (
              <div className="evidence-panel-empty">
                {t('briefing.selectBlockForEvidence')}
              </div>
            ) : (
              <EvidencePanel
                refs={selectedRefs}
                index={briefing.evidence_index}
                onOpen={onOpenEvidence}
                findingTypeOf={(ref) => {
                  const id = ref.split('#')[0].replace('finding:', '');
                  // `facts.findings` is untyped in the payload contract; the id and type are what the
                  // index refs are built from, so only those two fields are read here.
                  const found = (facts.findings as { id?: string; type?: string }[]).find(
                    (f) => f.id === id,
                  );
                  return found?.type ?? null;
                }}
              />
            )}
          </div>

          <div className="evidence-panel">
            <div className="evidence-panel-title">{t('briefing.pipeline')}</div>
            <div className="briefing-stages">
              {stages.map((stage) => (
                <div key={stage.id} className={`briefing-stage briefing-stage--${stage.status}`}>
                  <span className="briefing-stage-dot" />
                  <span className="briefing-stage-label">{stage.label}</span>
                  <span className="briefing-stage-ms">{stage.ms} ms</span>
                  {stage.note ? <span className="briefing-stage-note">{stage.note}</span> : null}
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function TraceIcon() {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6.5 14.5h-3a1 1 0 0 1-1-1v-3l7-7 4 4-7 7Z" />
      <path d="m9.5 5.5 4 4" />
    </svg>
  );
}

function MarketIcon() {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="7" cy="7" r="4.5" />
      <path d="m10.5 10.5 3.5 3.5" />
    </svg>
  );
}
