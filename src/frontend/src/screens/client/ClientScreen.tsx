import { useEffect, useMemo, useState } from 'react';

import { api, errorMessage } from '../../api/client';
import type {
  ClientDetailResponse,
  PortfolioSummary,
  ProposalRow,
  Violation,
} from '../../types';
import { formatDate, formatFraction, formatMoney, formatPct } from '../../utils/format';
import { useI18n, type MessageKey } from '../../i18n';

import MetaBand from '../../components/MetaBand';
import { ViolationIcon, WarningIcon } from '../../components';

interface Props {
  clientRef: string;
  onOpenPortfolio: (portfolioNr: string) => void;
  onOpenFremdbanken?: () => void;
  onBriefing?: (portfolioNr?: string) => void;
  /** Section id to scroll to once data has landed (nav deep-link within the screen). */
  initialScroll?: string | null;
}
export default function ClientScreen({ clientRef, onOpenPortfolio, onOpenFremdbanken, onBriefing, initialScroll }: Props) {
  const { lang, t } = useI18n();
  const [data, setData] = useState<ClientDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);


  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .client(clientRef, lang)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientRef, lang]);

  // Hooks must run before any early return. React counts hooks per render, so a useMemo placed after
  // an `if (loading) return` throws "Rendered more hooks than during the previous render" on the next
  // render — which unmounts the whole app instead of showing an error.
  const violationsByPortfolio = useMemo(() => {
    const map = new Map<number, Violation[]>();
    for (const violation of data?.violations ?? []) {
      const list = map.get(violation.portfolio_id) ?? [];
      list.push(violation);
      map.set(violation.portfolio_id, list);
    }
    return map;
  }, [data]);

  useEffect(() => {
    if (!data || !initialScroll) return;
    document.getElementById(initialScroll)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [data, initialScroll]);

  const collapsedNotes = useMemo(
    () => (data?.notes ?? []).filter((note) => note.duplicate_of === null),
    [data],
  );

  if (loading) {
    return (
      <div className="screen">
        <MetaBand pairs={[{ label: t('client.title'), value: clientRef }]} />
        <div style={{ padding: 24 }}>{t('client.loading')}</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="screen">
        <MetaBand pairs={[{ label: t('client.title'), value: clientRef }]} />
        <div className="screen-error">{error ?? t('client.unknownError')}</div>
      </div>
    );
  }

  const { client, portfolios, proposals, violations, tags, data_gaps } = data;

  const displayName = client.display_name || `${client.first_name ?? ''} ${client.last_name ?? ''}`.trim() || client.ref;
  const riskProfileName = client.risk_profile?.name ?? t('client.notAvailable');

  return (
    <div className="screen" id="client-top">
      <MetaBand
        left={
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <strong style={{ fontSize: 'var(--fs-name)' }}>{displayName} ({client.ref})</strong>
          </div>
        }
        right={
          <div style={{ fontSize: 'var(--fs-total)', fontWeight: 600 }}>
            {formatMoney(client.aum, client.reporting_currency ?? 'CHF')}
          </div>
        }
        pairs={[
          { label: t('client.clientType'), value: client.type ?? '—' },
          { label: t('client.clientProfile'), value: riskProfileName },
        ]}
      />

      <div style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {/* Briefing button */}
        {onBriefing && (
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn-primary"
              onClick={() => onBriefing()}
              style={{
                background: 'var(--primary)',
                color: '#fff',
                border: 'none',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              {t('client.createBriefing')}
            </button>
          </div>
        )}

        {/* Portfolio cards */}
        <section id="client-portfolios">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
            <h3 style={{ fontSize: 'var(--fs-card-title)', margin: 0 }}>{t('client.portfolios')}</h3>
            <span
              style={{
                padding: '2px 8px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--primary)',
                color: 'var(--bg-card)',
                fontSize: 'var(--fs-cell)',
              }}
            >
              {t('client.ownPortfolios', { count: portfolios.filter((p) => !p.is_external).length })}
            </span>
            {onOpenFremdbanken && (
              <button
                type="button"
                onClick={onOpenFremdbanken}
                title={t('client.externalBanksTooltip')}
                style={{
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-btn-inactive)',
                  color: 'var(--text-primary)',
                  border: 'none',
                  fontSize: 'var(--fs-cell)',
                }}
              >
                {t('client.externalBanks')}
                {portfolios.some((p) => p.is_external)
                  ? ` (${portfolios.filter((p) => p.is_external).length})`
                  : ''}
              </button>
            )}
          </div>
          {portfolios.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>{t('client.noPortfolios')}</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-3)' }}>
              {portfolios.map((p) => (
                <PortfolioCard
                  key={p.nr}
                  portfolio={p}
                  violations={violationsByPortfolio.get(p.id ?? -1) ?? []}
                  onClick={() => onOpenPortfolio(p.nr)}
                  t={t}
                />
              ))}
            </div>
          )}
        </section>

        {/* Beratungen table */}
        <section>
          <h3 style={{ fontSize: 'var(--fs-card-title)', margin: '0 0 var(--space-2) 0' }}>{t('client.consultations')}</h3>
          {proposals.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>{t('client.noConsultations')}</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--fs-cell)' }}>
              <thead>
                <tr style={{ background: 'var(--bg-nav)', textAlign: 'left' }}>
                  <th style={thStyle}>{t('client.colService')}</th>
                  <th style={thStyle}>{t('client.colContainer')}</th>
                  <th style={thStyle}>{t('client.colAdvisoryType')}</th>
                  <th style={thStyle}>{t('client.colConsultation')}</th>
                  <th style={thStyle}>{t('client.colNr')}</th>
                  <th style={thStyle}>{t('client.colStatus')}</th>
                  <th style={thStyle}>{t('client.colChangedBy')}</th>
                  <th style={thStyle}>{t('client.colLastChange')}</th>
                  <th style={{ ...thStyle, width: 32 }}></th>
                </tr>
              </thead>
              <tbody>
                {proposals.map((p, idx) => (
                  <ProposalRowView key={p.id ?? idx} proposal={p} t={t} />
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Notes */}
        <section id="client-notes">
          <h3 style={{ fontSize: 'var(--fs-card-title)', margin: '0 0 var(--space-2) 0' }}>{t('client.notes')}</h3>
          {collapsedNotes.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>{t('client.noNotes')}</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {collapsedNotes.map((n) => {
                const dupCount = n.duplicate_count ?? 1;
                return (
                  <div key={n.index} style={{ padding: 'var(--space-2)', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: 'var(--fs-cell)', color: 'var(--text-secondary)', marginBottom: 4 }}>
                      {formatDate(n.date)}
                      {dupCount > 1 && <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>{t('client.repeated', { count: dupCount })}</span>}
                    </div>
                    <div style={{ fontSize: 'var(--fs-body)', whiteSpace: 'pre-wrap' }}>{n.text}</div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Tags */}
        <section>
          <h3 style={{ fontSize: 'var(--fs-card-title)', margin: '0 0 var(--space-2) 0' }}>Tags</h3>
          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            {tags.region.length === 0 && tags.industry.length === 0 && (
              <span style={{ color: 'var(--text-muted)' }}>{t('client.noTags')}</span>
            )}
            {tags.region.map((tag) => (
              <span key={`r-${tag.name}`} style={{ ...chipStyle, background: 'var(--primary-light)', color: 'var(--primary-text)' }}>
                {t('client.region')}: {tag.name}
              </span>
            ))}
            {tags.industry.map((tag) => (
              <span key={`i-${tag.name}`} style={{ ...chipStyle, background: '#fff4e0', color: '#b8651f' }}>
                {t('client.industry')}: {tag.name}
              </span>
            ))}
          </div>
        </section>

        {/* Violations */}
        <section id="client-violations">
          <h3 style={{ fontSize: 'var(--fs-card-title)', margin: '0 0 var(--space-2) 0' }}>{t('client.ruleViolations')}</h3>
          {violations.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>{t('client.noViolations')}</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {violations.map((v, idx) => (
                <ViolationRow key={v.id ?? idx} violation={v} portfolios={portfolios} t={t} />
              ))}
            </div>
          )}
        </section>

        {/* Data gaps */}
        {data_gaps.length > 0 && (
          <section>
            <h3 style={{ fontSize: 'var(--fs-card-title)', margin: '0 0 var(--space-2) 0' }}>{t('client.dataGaps')}</h3>
            <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-secondary)', fontSize: 'var(--fs-body)' }}>
              {data_gaps.map((g, i) => (
                <li key={i}>{g}</li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: '8px 12px',
  fontWeight: 500,
  color: 'var(--text-secondary)',
  borderBottom: '1px solid var(--border)',
};

const chipStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 'var(--radius-pill)',
  fontSize: 'var(--fs-cell)',
  fontWeight: 500,
};

function PortfolioCard({
  portfolio,
  violations,
  onClick,
  t,
}: {
  portfolio: PortfolioSummary;
  violations: Violation[];
  onClick: () => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}) {
  const hasError = violations.some((v) => v.severity === 'Error');
  const hasWarning = violations.some((v) => v.severity === 'Warning');

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-3)',
        cursor: 'pointer',
        boxShadow: 'var(--shadow-card)',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--primary)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 'var(--fs-card-title)' }}>
            {portfolio.nr} — {portfolio.name}
          </div>
          <div style={{ fontSize: 'var(--fs-cell)', color: 'var(--text-secondary)' }}>
            {portfolio.service ?? '—'} / {portfolio.strategy ?? '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {portfolio.is_external && (
            <span title={t('client.externalBank')} style={{ color: 'var(--text-secondary)' }}>
              <BankIcon />
            </span>
          )}
          {hasError && (
            <span title={t('client.errorViolation')} style={{ color: 'var(--danger)' }}>
              <ViolationIcon size={16} />
            </span>
          )}
          {hasWarning && !hasError && (
            <span title={t('client.warningViolation')} style={{ color: 'var(--warning)' }}>
              <WarningIcon size={16} />
            </span>
          )}
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)', fontSize: 'var(--fs-cell)' }}>
        <div>
          <div style={{ color: 'var(--text-muted)' }}>{t('client.portfolioValue')}</div>
          <div style={{ fontWeight: 600 }}>{formatMoney(portfolio.aum, portfolio.currency ?? 'CHF')}</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)' }}>{t('client.volatility')}</div>
          <div>{formatFraction(portfolio.volatility)}</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)' }}>{t('client.return12M')}</div>
          <div style={{ color: (portfolio.return_12m_pct ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            {formatPct(portfolio.return_12m_pct, 2, true)}
          </div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)' }}>{t('client.return3M')}</div>
          <div>{formatPct(portfolio.return_3m_pct, 2, true)}</div>
        </div>
      </div>
    </div>
  );
}

function BankIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 21h18" />
      <path d="M3 10h18" />
      <path d="M12 3l9 7H3l9-7z" />
      <path d="M5 10v11" />
      <path d="M19 10v11" />
      <path d="M9 10v11" />
      <path d="M14 10v11" />
    </svg>
  );
}

function ProposalRowView({ proposal, t }: { proposal: ProposalRow; t: (key: MessageKey, vars?: Record<string, string | number>) => string }) {
  const containerLabel = proposal.portfolio_known
    ? proposal.container
    : t('client.portfolioUnknown').replace('{id}', String(proposal.portfolio_id));

  const statusLabel = proposal.status;
  const statusStyle = getStatusStyle(statusLabel, proposal.status_archived, proposal.status_allows_submit);

  const beratungLabel = proposal.changed_at ? t('client.consultationOn').replace('{date}', formatDate(proposal.changed_at)) : '—';

  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      <td style={tdStyle}>{proposal.advisory_type}</td>
      <td style={tdStyle}>{containerLabel}</td>
      <td style={tdStyle}>{proposal.advisory_type === 'Investment proposal' ? 'Investment proposal' : proposal.advisory_type}</td>
      <td style={tdStyle}>
        {proposal.portfolio_known ? (
          <a href="#" onClick={(e) => e.preventDefault()} style={{ color: 'var(--primary-text)', textDecoration: 'underline' }}>
            {beratungLabel}
          </a>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>{beratungLabel}</span>
        )}
      </td>
      <td style={tdStyle}>{proposal.portfolio_nr ?? '—'}</td>
      <td style={tdStyle}>
        <span style={statusStyle}>{statusLabel}</span>
      </td>
      <td style={tdStyle}>{proposal.changed_by ?? '—'}</td>
      <td style={tdStyle}>{formatDate(proposal.changed_at)}</td>
      <td style={tdStyle}>
        {proposal.can_delete && (
          <span title={t('client.deletable')} style={{ color: 'var(--text-muted)', cursor: 'pointer' }}>
            <TrashIcon />
          </span>
        )}
      </td>
    </tr>
  );
}

function getStatusStyle(status: string, archived: boolean, allowsSubmit: boolean): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 'var(--radius-pill)',
    fontSize: 'var(--fs-cell)',
    fontWeight: 500,
  };
  if (status === 'Abgelehnt' || archived) {
    return { ...base, background: '#fde8e7', color: 'var(--danger)' };
  }
  if (status === 'Final' && allowsSubmit) {
    return { ...base, background: '#e8f5e1', color: 'var(--success)' };
  }
  if (status === 'Entwurf') {
    return { ...base, background: 'var(--bg-nav)', color: 'var(--text-secondary)' };
  }
  return { ...base, background: 'var(--bg-nav)', color: 'var(--text-primary)' };
}

const tdStyle: React.CSSProperties = {
  padding: '8px 12px',
  verticalAlign: 'middle',
};

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
      <path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
    </svg>
  );
}

function ViolationRow({ violation, portfolios, t }: { violation: Violation; portfolios: PortfolioSummary[]; t: (key: MessageKey, vars?: Record<string, string | number>) => string }) {
  const isError = violation.severity === 'Error';
  const portfolioLabel = violation.portfolio_known
    ? portfolios.find((p) => p.id === violation.portfolio_id)?.nr ?? `Portfolio ${violation.portfolio_id}`
    : t('client.portfolioUnknownShort');

  // Filter out engine type guards (value === limit) — those carry no information
  const informativeValues = violation.values.filter((v) => v.value !== v.limit);

  const formatValue = (v: { value: number; limit: number; unit: 'ratio' | 'value'; label: string }) => {
    const formattedValue = v.unit === 'ratio' ? formatFraction(v.value) : formatPlainNumber(v.value);
    const formattedLimit = v.unit === 'ratio' ? formatFraction(v.limit) : formatPlainNumber(v.limit);
    return `${v.label}: ${formattedValue} vs ${t('client.violationLimit')} ${formattedLimit}`;
  };

  return (
    <div
      style={{
        padding: 'var(--space-2)',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${isError ? 'var(--danger)' : 'var(--warning)'}`,
        borderRadius: 'var(--radius-md)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        {isError ? (
          <span style={{ color: 'var(--danger)' }}><ViolationIcon size={16} /></span>
        ) : (
          <span style={{ color: 'var(--warning)' }}><WarningIcon size={16} /></span>
        )}
        <strong style={{ fontSize: 'var(--fs-cell)' }}>{violation.rule_code}</strong>
        <span style={{ fontSize: 'var(--fs-cell)', color: 'var(--text-muted)' }}>— {portfolioLabel}</span>
        {!violation.portfolio_known && (
          <span style={{ fontSize: 'var(--fs-cell)', color: 'var(--danger)', fontStyle: 'italic' }}>{t('client.dataDefect')}</span>
        )}
      </div>
      <div style={{ fontSize: 'var(--fs-body)', marginBottom: 4 }}>{violation.rule_description}</div>
      {informativeValues.length > 0 && (
        <div style={{ fontSize: 'var(--fs-cell)', color: 'var(--text-secondary)' }}>
          <em>{t('client.simulationValues')}</em>{' '}
          {informativeValues.map((v, i) => (
            <span key={i}>
              {i > 0 && ', '}
              {formatValue(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function formatPlainNumber(value: number): string {
  // Up to 4 decimals, no trailing zeros
  return value.toFixed(4).replace(/\.?0+$/, '');
}
