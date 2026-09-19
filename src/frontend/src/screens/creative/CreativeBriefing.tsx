import { useEffect, useRef, useState } from 'react';
import { Printer, ArrowLeft, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { api, ApiError, preferredRenderer } from '../../api/client';
import { formatDate, formatMoney, formatPct, formatFraction } from '../../utils/format';
import type {
  BriefingApiResponse,
  BriefingBlock,
  EvidenceIndexEntry,
  FactsAction,
} from './types';
import {
  CLIENT_SECTION,
  PORTFOLIO_SECTION,
  targetLabelKey,
  type EvidenceTarget,
} from '../../lib/evidenceTarget';
import { useI18n, type MessageKey } from '../../i18n';
import './creative.css';

interface Props {
  clientRef: string;
  portfolioNr?: string | null;
  onBack: () => void;
  onPrint?: () => void;
  /** Opens the market search for an instrument the briefing talks about (its ISIN). */
  onOpenMarket?: (isin: string) => void;
  /** Open a metric where it lives: the violations tile into the client's violations, and so on. */
  onOpenEvidence?: (target: EvidenceTarget) => void;
}

type StageStatus = 'pending' | 'running' | 'done' | 'error';

/** What each metric tile shows, and where clicking it goes. A tile without a destination stays a
    plain figure: no screen holds a better answer than this page for it. */
const METRIC_LABELS = {
  return12m: 'creative.return12M',
  volume: 'creative.volume',
  topPosition: 'creative.topPosition',
  violations: 'creative.ruleViolations',
} as const satisfies Record<string, MessageKey>;

const TILE_TARGETS: Record<keyof typeof METRIC_LABELS, EvidenceTarget | null> = {
  // Both the return and the volume are the portfolio's own figures; the portfolio screen is where the
  // risk/return card and the value they belong to live.
  return12m: { kind: 'portfolio', section: PORTFOLIO_SECTION.allocation },
  volume: { kind: 'portfolio', section: PORTFOLIO_SECTION.allocation },
  topPosition: { kind: 'portfolio', section: PORTFOLIO_SECTION.positions },
  violations: { kind: 'client', section: CLIENT_SECTION.violations },
};

interface Stage {
  id: string;
  label: string;
  status: StageStatus;
  ms: number | null;
  note: string | null;
}

/**
 * B3 — Creative briefing format: three-act storyline with timeline spine.
 * Alternative rendering of R6's briefing payload, optimised for print and 60-second reading.
 */
export default function CreativeBriefing({
  clientRef,
  portfolioNr,
  onBack,
  onPrint,
  onOpenMarket,
  onOpenEvidence,
}: Props) {
  const { lang, t } = useI18n();
  const [data, setData] = useState<BriefingApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceIndexEntry[] | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    let cancelled = false;
    startTimeRef.current = Date.now();
    setElapsed(0);

    // Initialize stages as pending
    const stageIds = [
      { id: 'collect', label: t('briefing.stageCollect') },
      { id: 'analyse', label: t('briefing.stageAnalyse') },
      { id: 'rules', label: t('briefing.stageRules') },
      { id: 'market', label: t('briefing.stageMarket') },
      { id: 'house_view', label: t('briefing.stageHouseView') },
      { id: 'actions', label: t('briefing.stageActions') },
      { id: 'compose', label: t('briefing.stageCompose') },
    ];
    setStages(stageIds.map((s) => ({ ...s, status: 'pending', ms: null, note: null })));

    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);

    async function fetchBriefing() {
      setError(null);
      setData(null);

      try {
        const result = await api.briefing<BriefingApiResponse>(
          {
            client_ref: clientRef,
            portfolio_nr: portfolioNr ?? null,
            renderer: await preferredRenderer(lang),
            lang,
          },
          lang,
        );

        if (cancelled) return;

        setData(result);
        setStages(
          result.stages.map((s) => ({
            id: s.id,
            label: s.label,
            status: s.status === 'ok' ? 'done' : 'error',
            ms: s.ms,
            note: s.note,
          })),
        );
      } catch (err) {
        if (cancelled) return;
        
        // The server's own reason when it sent a plain string; a structured detail is never dumped.
        const apiError = err instanceof ApiError ? err : null;
        const errorMsg = apiError?.status
          ? t('briefing.failureHttp', { status: apiError.status }) +
            (apiError.detail ? ` — ${apiError.detail}` : '')
          : t('briefing.failureNetwork');

        setError(errorMsg);
        setStages((prev) =>
          prev.map((s) => (s.status === 'running' ? { ...s, status: 'error' } : s)),
        );
      }
    }

    fetchBriefing();

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [clientRef, portfolioNr, lang, t]);

  function handlePrint() {
    if (onPrint) {
      onPrint();
    } else {
      window.print();
    }
  }

  function handleEvidenceClick(refs: string[]) {
    if (!data) return;
    const entries = refs
      .map((ref) => data.briefing.evidence_index[ref])
      .filter((entry): entry is EvidenceIndexEntry => entry !== undefined);
    if (entries.length > 0) {
      setSelectedEvidence(entries);
    }
  }

  if (error) {
    return (
      <div className="uro-creative">
        <div className="uro-creative__error">
          <XCircle className="uro-creative__error-icon" size={48} />
          <div className="uro-creative__error-message">{error}</div>
          <button
            className="uro-creative__retry-btn"
            onClick={() => window.location.reload()}
          >
            {t('creative.retry')}
          </button>
          <button
            className="uro-creative__retry-btn"
            onClick={onBack}
            style={{ background: 'var(--text-secondary)' }}
          >
            {t('creative.back')}
          </button>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="uro-creative">
        <div className="uro-creative__loading">
          <div className="uro-creative__loading-title">{t('creative.creating')}</div>
          <div className="uro-creative__loading-subtitle">
            {t('briefing.elapsed', { seconds: elapsed })}
          </div>
          {stages.map((stage) => (
            <div key={stage.id} className="uro-creative__stage">
              <div
                className={`uro-creative__stage-icon uro-creative__stage-icon--${stage.status}`}
              >
                {stage.status === 'pending' && '○'}
                {stage.status === 'running' && <Loader2 size={14} />}
                {stage.status === 'done' && <CheckCircle size={14} />}
                {stage.status === 'error' && <XCircle size={14} />}
              </div>
              <div className="uro-creative__stage-label">{stage.label}</div>
              <div className="uro-creative__stage-status">
                {stage.status === 'done' && stage.ms !== null && `${stage.ms}ms`}
                {stage.status === 'running' && t('creative.loading')}
                {stage.status === 'pending' && t('briefing.waiting')}
                {stage.status === 'error' && t('creative.error')}
              </div>
            </div>
          ))}
          <button
            className="uro-creative__cancel-btn"
            onClick={onBack}
            style={{ marginTop: 'var(--space-3)' }}
          >
            {t('briefing.cancel')}
          </button>
        </div>
      </div>
    );
  }

  const { briefing, facts } = data;
  const portfolio = facts.portfolios[0];
  const violationCount = facts.violations.length;

  // Extract headline metrics from facts
  const return12m = portfolio?.return_12m_pct;
  const aum = portfolio?.aum ?? facts.client.aum;
  const currency = portfolio?.currency ?? facts.client.reporting_currency ?? 'CHF';

  // Use top_weight from portfolio contract (fraction 0-1, or null)
  const topWeight = portfolio?.top_weight ?? null;

  // The metric band, in one declaration: value, colour tone and destination key per tile.
  const metricTiles = [
    {
      key: 'return12m',
      value: return12m !== null ? formatPct(return12m) : '—',
      tone:
        return12m === null
          ? ''
          : return12m > 0
            ? 'uro-creative__metric-value--positive'
            : return12m < 0
              ? 'uro-creative__metric-value--negative'
              : '',
    },
    { key: 'volume', value: formatMoney(aum, currency, 0), tone: '' },
    { key: 'topPosition', value: topWeight !== null ? formatFraction(topWeight) : '—', tone: '' },
    {
      key: 'violations',
      value: String(violationCount),
      tone: violationCount > 0 ? 'uro-creative__metric-value--warning' : '',
    },
  ] as const satisfies readonly { key: keyof typeof METRIC_LABELS; value: string; tone: string }[];

  // Determine provenance
  const hasMock = facts.house_view.mock;
  const hasLive =
    facts.market_meta.queried &&
    !facts.market_meta.is_mock &&
    facts.market_meta.providers_used.length > 0;
  const hasSimulated = true; // Portfolio data is always simulated

  // Map sections to acts
  const actLabels = [
    { id: 'recent_development', label: t('creative.whatHappenedShort') },
    { id: 'health_check', label: t('creative.whereWeAreShort') },
    { id: 'outlook_actions', label: t('creative.whatToDoShort') },
  ];

  const printHeader = `${briefing.client_name} (${briefing.client_ref}) · ${t('creative.dataAsOf', {
    date: formatDate(briefing.generated_from.data_as_of),
  })}`;

  return (
    <div className="uro-creative" data-print-header={printHeader}>
      {/* Header */}
      <div className="uro-creative__header">
        <div className="uro-creative__header-left">
          <button
            onClick={onBack}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--primary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-1)',
              padding: 0,
              marginBottom: 'var(--space-2)',
              fontSize: 'var(--fs-body)',
            }}
          >
            <ArrowLeft size={16} />
            {t('creative.back')}
          </button>
          <h1 className="uro-creative__client-name">{briefing.client_name}</h1>
          <p className="uro-creative__client-ref">
            {briefing.client_ref}
            {portfolioNr ? ` · ${t('briefing.portfolioNr', { nr: portfolioNr })}` : ''}
          </p>
        </div>
        <div className="uro-creative__header-right">
          <div className="uro-creative__data-as-of">
            {t('creative.dataAsOf', { date: formatDate(briefing.generated_from.data_as_of) })}
          </div>
          <button className="uro-creative__print-btn" onClick={handlePrint}>
            <Printer size={16} />
            {t('creative.print')}
          </button>
        </div>
      </div>

      {/* Four questions strip */}
      <div className="uro-creative__questions">
        <div className="uro-creative__question">
          <div className="uro-creative__question-label">{t('creative.whatHappened')}</div>
          <div className="uro-creative__question-answer">
            {briefing.questions.what_happened}
          </div>
          {briefing.questions.what_happened_refs.length > 0 && (
            <button
              className="uro-creative__ref-chip"
              onClick={() => handleEvidenceClick(briefing.questions.what_happened_refs)}
            >
              {t('creative.evidenceCount', { count: briefing.questions.what_happened_refs.length })}
            </button>
          )}
        </div>
        <div className="uro-creative__question">
          <div className="uro-creative__question-label">{t('creative.whereWeAre')}</div>
          <div className="uro-creative__question-answer">{briefing.questions.situation}</div>
          {briefing.questions.situation_refs.length > 0 && (
            <button
              className="uro-creative__ref-chip"
              onClick={() => handleEvidenceClick(briefing.questions.situation_refs)}
            >
              {t('creative.evidenceCount', { count: briefing.questions.situation_refs.length })}
            </button>
          )}
        </div>
        <div className="uro-creative__question">
          <div className="uro-creative__question-label">{t('creative.whatComes')}</div>
          <div className="uro-creative__question-answer">{briefing.questions.next}</div>
          {briefing.questions.next_refs.length > 0 && (
            <button
              className="uro-creative__ref-chip"
              onClick={() => handleEvidenceClick(briefing.questions.next_refs)}
            >
              {t('creative.evidenceCount', { count: briefing.questions.next_refs.length })}
            </button>
          )}
        </div>
        <div className="uro-creative__question">
          <div className="uro-creative__question-label">{t('creative.whatToDo')}</div>
          <div className="uro-creative__question-answer">{briefing.questions.should_do}</div>
          {briefing.questions.should_do_refs.length > 0 && (
            <button
              className="uro-creative__ref-chip"
              onClick={() => handleEvidenceClick(briefing.questions.should_do_refs)}
            >
              {t('creative.evidenceCount', { count: briefing.questions.should_do_refs.length })}
            </button>
          )}
        </div>
      </div>

      {/* Metric band. The tiles are the briefing's briefest slices, so each one that has a screen
          behind it opens it — "21 rule violations" is only useful if the next click shows which. */}
      <div className="uro-creative__metrics">
        {metricTiles.map(({ key, value, tone }) => {
          const target = TILE_TARGETS[key];
          const body = (
            <>
              <div className={`uro-creative__metric-value ${tone}`}>{value}</div>
              <div className="uro-creative__metric-label">
                {t(METRIC_LABELS[key])}
                {target && onOpenEvidence ? (
                  <span className="uro-creative__metric-open">{t(targetLabelKey(target))} ↗</span>
                ) : null}
              </div>
            </>
          );
          if (!target || !onOpenEvidence) {
            return (
              <div key={key} className="uro-creative__metric">
                {body}
              </div>
            );
          }
          return (
            <button
              key={key}
              type="button"
              className="uro-creative__metric uro-creative__metric--action"
              onClick={() => onOpenEvidence(target)}
            >
              {body}
            </button>
          );
        })}
      </div>

      {/* Timeline with three acts */}
      <div className="uro-creative__timeline">
        <div className="uro-creative__spine">
          {actLabels.map((act, idx) => (
            <div key={act.id}>
              <div className="uro-creative__spine-dot">{idx + 1}</div>
              {idx < actLabels.length - 1 && <div className="uro-creative__spine-line" />}
            </div>
          ))}
        </div>
        <div className="uro-creative__acts">
          {briefing.sections.map((section, idx) => {
            const actLabel = actLabels.find((a) => a.id === section.id);
            return (
              <div key={section.id} className="uro-creative__act">
                <div className="uro-creative__act-header">
                  <h2 className="uro-creative__act-title">
                    {idx + 1} · {actLabel?.label ?? section.title}
                  </h2>
                </div>
                <div className="uro-creative__act-body">
                  {section.blocks.map((block, blockIdx) => (
                    <BlockView
                      key={blockIdx}
                      block={block}
                      onEvidenceClick={handleEvidenceClick}
                      onOpenMarket={onOpenMarket}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actions list */}
      {facts.actions.length > 0 && (
        <div className="uro-creative__act">
          <div className="uro-creative__act-header">
            <h2 className="uro-creative__act-title">{t('creative.actions')}</h2>
          </div>
          <div className="uro-creative__act-body">
            <div className="uro-creative__actions">
              {facts.actions.map((action, idx) => (
                <ActionView
                  key={action.id}
                  action={action}
                  number={idx + 1}
                  onEvidenceClick={handleEvidenceClick}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Gaps list */}
      {facts.meta.unavailable.length > 0 && (
        <div className="uro-creative__gaps">
          <div className="uro-creative__gaps-title">{t('creative.unavailableData')}</div>
          <ul className="uro-creative__gaps-list">
            {facts.meta.unavailable.map((gap, idx) => (
              <li key={idx}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Provenance line */}
      <div className="uro-creative__provenance">
        {hasLive && (
          <span className="uro-creative__provenance-tag uro-creative__provenance-tag--live">
            {t('creative.liveMarketData')}
          </span>
        )}
        {hasMock && (
          <span className="uro-creative__provenance-tag uro-creative__provenance-tag--mock">
            {t('creative.mockBankView')}
          </span>
        )}
        {hasSimulated && (
          <span className="uro-creative__provenance-tag uro-creative__provenance-tag--simulated">
            {t('creative.simulatedPortfolio')}
          </span>
        )}
      </div>

      {/* Evidence popover */}
      {selectedEvidence && (
        <>
          <div className="uro-creative__backdrop" onClick={() => setSelectedEvidence(null)} />
          <div className="uro-creative__evidence-popover">
            <div className="uro-creative__evidence-popover-header">
              <div className="uro-creative__evidence-popover-title">
                {selectedEvidence.length === 1
                  ? selectedEvidence[0].label
                  : t('creative.evidenceCount', { count: selectedEvidence.length })}
              </div>
              <button
                className="uro-creative__evidence-popover-close"
                onClick={() => setSelectedEvidence(null)}
              >
                ×
              </button>
            </div>
            {selectedEvidence.map((entry, idx) => (
              <div key={idx} className="uro-creative__evidence-item">
                <div className="uro-creative__evidence-label">{entry.label}</div>
                <div className="uro-creative__evidence-value">
                  {entry.value_text ?? (entry.value !== null ? String(entry.value) : '—')}
                </div>
                <div className="uro-creative__evidence-source">
                  {t('creative.source')}: {entry.source}
                  <br />
                  {t('creative.path')}: {entry.path}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function BlockView({
  block,
  onEvidenceClick,
  onOpenMarket,
}: {
  block: BriefingBlock;
  onEvidenceClick: (refs: string[]) => void;
  onOpenMarket?: (isin: string) => void;
}) {
  const { t } = useI18n();
  // Parse markdown-ish **bold** leads
  const parts = block.text.split(/(\*\*[^*]+\*\*)/g);
  const rendered = parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    }
    return <span key={idx}>{part}</span>;
  });

  const isGap = block.source_kind === 'gap' || block.evidence_refs.length === 0;

  const severityLabel = block.severity
    ? t(`severity.${block.severity}` as 'severity.high' | 'severity.medium' | 'severity.low')
    : null;

  const sourceKindLabel =
    block.source_kind === 'portfolio'
      ? t('briefing.sourcePortfolio')
      : block.source_kind === 'mock'
        ? t('briefing.sourceMock')
        : block.source_kind === 'external'
          ? t('briefing.sourceExternal')
          : t('briefing.sourceGap');

  return (
    <div className="uro-creative__block">
      <div
        className="uro-creative__block-text"
        style={isGap ? { color: 'var(--text-muted)', fontStyle: 'italic' } : undefined}
      >
        {rendered}
      </div>
      <div className="uro-creative__block-meta">
        {block.severity && severityLabel && (
          <span className={`uro-creative__severity uro-creative__severity--${block.severity}`}>
            {severityLabel}
          </span>
        )}
        <span className="uro-creative__source-kind">{sourceKindLabel}</span>
        {block.evidence_refs.length > 0 && (
          <button
            className="uro-creative__ref-chip"
            onClick={() => onEvidenceClick(block.evidence_refs)}
          >
            {t('creative.evidenceCount', { count: block.evidence_refs.length })}
          </button>
        )}
        {block.isin && onOpenMarket && (
          <button
            className="uro-creative__ref-chip"
            onClick={() => onOpenMarket(block.isin as string)}
          >
            {t('briefing.marketResults')}
          </button>
        )}
      </div>
    </div>
  );
}

function ActionView({
  action,
  number,
  onEvidenceClick,
}: {
  action: FactsAction;
  number: number;
  onEvidenceClick: (refs: string[]) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="uro-creative__action">
      <div className="uro-creative__action-number">{number}</div>
      <div className="uro-creative__action-content">
        <div className="uro-creative__action-text">{action.action}</div>
        <div className="uro-creative__action-rationale">{action.rationale}</div>
        {action.finding_refs.length > 0 && (
          <div className="uro-creative__action-refs">
            <button
              className="uro-creative__ref-chip"
              onClick={() => onEvidenceClick(action.finding_refs)}
            >
              {t('creative.evidenceCount', { count: action.finding_refs.length })}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
