import './portfolio.css';
import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  PieChart as PieIcon,
  Settings,
  Maximize2,
  SquareMinus,
  SquarePlus,
  Globe,
  LayoutGrid,
} from 'lucide-react';
import { api, errorMessage } from '../../api/client';
import type {
  PortfolioDetailResponse,
  PositionRow,
  PositionGroup,
  SaaRow,
  Widget,
} from '../../types';
import {
  formatAmount,
  formatMoney,
  formatFraction,
  formatPct,
  formatCompactAmount,
} from '../../utils/format';
import { useI18n, type MessageKey } from '../../i18n';
import MetaBand from '../../components/MetaBand';
import Card from '../../components/Card';
import DonutChart from '../../components/DonutChart';
import ProgressBar from '../../components/ProgressBar';

/**
 * F4 — Portfolio analysis screen.
 *
 * Shows the SAA vs actual allocation, the positions list with collapsible groups,
 * the metric rail, and a briefing button scoped to this portfolio.
 */

interface Props {
  clientRef: string;
  portfolioNr: string;
  onBack: () => void;
  onBriefing?: (portfolioNr: string) => void;
}

const CATEGORY_COLOR: Record<string, string> = {
  Liquidity: 'var(--chart-liquidity)',
  Bonds: 'var(--chart-bonds)',
  Shares: 'var(--chart-stocks)',
  'Real estate': 'var(--chart-realestate)',
  'Specialties andCommodities': 'var(--chart-other)',
};

const CATEGORY_LABEL_KEYS: Record<string, MessageKey> = {
  Liquidity: 'portfolio.categoryLiquidity',
  Bonds: 'portfolio.categoryBonds',
  Shares: 'portfolio.categoryShares',
  'Real estate': 'portfolio.categoryRealEstate',
  'Specialties andCommodities': 'portfolio.categoryOther',
  'Nicht klassifiziert': 'portfolio.categoryUnclassified',
};

// Scale so that ≈60% of portfolio weight fills the bar. Using max=0.6 means
// a 60% actual weight renders at 100% of the track; larger values cap at full.

export default function PortfolioScreen({ clientRef, portfolioNr, onBack, onBriefing }: Props) {
  const { lang, t } = useI18n();
  const [data, setData] = useState<PortfolioDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [splittingOn, setSplittingOn] = useState(true);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .portfolio(clientRef, portfolioNr, lang)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientRef, portfolioNr, lang]);


  // Hooks must run before any early return (see ClientScreen): a useMemo after an `if (loading)
  // return` makes the next render throw "Rendered more hooks than during the previous render".
  const donutSegments = useMemo(() => {
    const byGroup: Record<string, number> = {};
    for (const position of data?.positions ?? []) {
      const key = position.group || 'Nicht klassifiziert';
      byGroup[key] = (byGroup[key] ?? 0) + (position.weight ?? 0);
    }
    return Object.entries(byGroup).map(([group, value]) => ({
      group,
      value,
      color: CATEGORY_COLOR[group] ?? 'var(--chart-other)',
    }));
  }, [data]);

  if (loading) {
    return (
      <div className="screen">
        <MetaBand pairs={[{ label: 'Portfolio', value: portfolioNr }]} />
        <div className="screen-loading">{t('portfolio.loading')}</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="screen">
        <MetaBand pairs={[{ label: 'Portfolio', value: portfolioNr }]} />
        <div className="screen-error">{error ?? t('portfolio.unknownError')}</div>
        <button className="link-button" onClick={onBack}>
          ← {t('common.back')}
        </button>
      </div>
    );
  }
  const { portfolio, total, saa, positions, groups, metrics, data_gaps, exposures } = data;

  const metaPairs = [
    { label: 'Portfolio', value: portfolio.nr },
    { label: t('portfolio.service'), value: portfolio.service ?? '—' },
    { label: t('portfolio.strategy'), value: portfolio.strategy ?? '—' },
  ];
  const metaRight = formatMoney(total.value, total.currency ?? 'CHF');

  // SAA: find the single largest deviation for the Anlagetipp sentence.
  const tipRow: SaaRow | null =
    saa.available && saa.rows.length > 0
      ? saa.rows.reduce<SaaRow | null>((best, row) => {
          const abs = Math.abs(row.difference);
          if (!best || abs > Math.abs(best.difference)) return row;
          return best;
        }, null)
      : null;

  const anlagetipp = tipRow
    ? `${t(CATEGORY_LABEL_KEYS[tipRow.category] ?? `portfolio.category${tipRow.category}`)} ${formatFraction(Math.abs(tipRow.difference))} ${tipRow.difference < 0 ? t('portfolio.under') : t('portfolio.over')} ${t('portfolio.target')} — ${t('portfolio.target')} ${formatFraction(tipRow.target)}, ${t('portfolio.effective')} ${formatFraction(tipRow.actual)}.`
    : null;

  const toggleGroup = (category: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [category]: !prev[category] }));
  };

  // Exposures for the toggle: country / industry / currency (matches the backend's rail widget mapping)
  const currentExposures = {
    country: splittingOn ? exposures.country.splitting_on : exposures.country.splitting_off,
    industry: splittingOn ? exposures.industry.splitting_on : exposures.industry.splitting_off,
    currency: splittingOn ? exposures.currency.splitting_on : exposures.currency.splitting_off,
  };

  return (
    <div className="screen">
      <MetaBand pairs={metaPairs} right={<span className="meta-total">{metaRight}</span>} />

      <div className="portfolio-layout">
        <section className="portfolio-main" id="portfolio-saa">
          <div className="section-header">
            <div className="section-title">
              <PieIcon size={16} /> <span>SAA</span>
            </div>
            <div className="section-actions">
              <Settings size={14} />
              <Maximize2 size={14} />
            </div>
          </div>

          <div className="saa-grid">
            <div className="saa-table-col">
              {saa.available ? (
                <>
                  {saa.saa_name && <div className="saa-name">{saa.saa_name}</div>}
                  {saa.description && <p className="saa-description">{saa.description}</p>}
                  {anlagetipp && (
                    <p className="anlagetipp">
                      <strong>{t('portfolio.investmentTip')}</strong> {anlagetipp}
                    </p>
                  )}

                  <h4 className="saa-subheading">{t('portfolio.saaTitle')}</h4>

                  <table className="saa-table">
                    <thead>
                      <tr>
                        <th></th>
                        <th className="num">Min.</th>
                        <th className="num">{t('portfolio.colTarget')}</th>
                        <th className="num">Max.</th>
                        <th className="num">Portfolio</th>
                        <th className="num">{t('portfolio.colAction')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {saa.rows.map((row) => {
                        const color = CATEGORY_COLOR[row.category] ?? 'var(--chart-other)';
                        const barValue = Math.max(0, row.actual);
                        const categoryLabel = CATEGORY_LABEL_KEYS[row.category]
                          ? t(CATEGORY_LABEL_KEYS[row.category])
                          : row.category;
                        return (
                          <tr key={row.category} className="saa-row">
                            <td>{categoryLabel}</td>
                            <td className="num">{formatFraction(row.min)}</td>
                            <td className="num">{formatFraction(row.target)}</td>
                            <td className="num">{formatFraction(row.max)}</td>
                            <td className="num">{formatFraction(row.actual)}</td>
                            <td className={`num ${row.difference >= 0 ? 'positive' : 'negative'}`}>
                              {formatFraction(row.difference, 2, true)}
                            </td>
                            <td colSpan={6} className="saa-bar-cell">
                              <ProgressBar value={barValue} color={color} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="saa-empty">
                  <strong>{t('portfolio.noStrategy')}</strong>
                  {saa.reason && <p className="saa-reason">{saa.reason}</p>}
                </div>
              )}
            </div>

            {/* The allocation donut belongs beside the allocation table, not in a column of its own:
                at 220px tall inside a full-height grid column it left ~1650px of empty page. */}
            <div className="saa-donut">
              <DonutChart
                size={200}
                strokeWidth={10}
                segments={donutSegments.map((s) => ({ value: s.value, color: s.color }))}
                centerText={formatCompactAmount(total.value, lang)}
                centerSub={total.currency ?? 'CHF'}
              />
            </div>
          </div>
        </section>

        {/* RIGHT: metric rail */}
        <aside className="portfolio-rail">
          {metrics.map((w) => (
            <MetricCard key={w.id} widget={w} />
          ))}
        </aside>

      {/* Positions */}
      <section className="positions-section" id="portfolio-positions">
        <div className="section-header">
          <div className="section-title">{t('portfolio.positionsList')}</div>
          <button
            type="button"
            className="split-toggle"
            onClick={() => setSplittingOn((v) => !v)}
          >
            {splittingOn ? t('portfolio.disableSplitting') : t('portfolio.enableSplitting')}
          </button>
        </div>

        <table className="positions-table">
          <thead>
            <tr>
              <th>{t('portfolio.colPosition')}</th>
              <th>{t('portfolio.colIdentifier')}</th>
              <th>{t('portfolio.colCurrency')}</th>
              <th className="num">PRC</th>
              <th className="num">Qt./Nom.</th>
              <th className="num">{t('portfolio.colPriceCost')}</th>
              <th className="num">{`${t('portfolio.colValueIn')} ${total.currency ?? 'CHF'}`}</th>
              <th className="num">{t('portfolio.colWeight')}</th>
              <th className="num">{t('portfolio.colPerformance')}</th>
              <th className="num">{t('portfolio.colRiskContribution')}</th>
              <th className="num">{t('portfolio.colSustainability')}</th>
              <th className="num">{t('portfolio.colRules')}</th>
            </tr>
          </thead>
          <tbody>
            <tr className="total-row">
              <td>{t('common.total')}</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td className="num">{formatAmount(total.value)}</td>
              <td className="num">100.00%</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
            </tr>
            {groups.map((g) => (
              <GroupBlock
                key={g.category}
                group={g}
                positions={positions.filter((p) => p.group === g.category)}
                collapsed={!!collapsedGroups[g.category]}
                onToggle={() => toggleGroup(g.category)}
                t={t}
              />
            ))}
          </tbody>
        </table>

        {/* Exposures summary driven by the toggle */}
        <div className="exposures-summary">
          <ExposureBlock title={t('portfolio.countries')} rows={currentExposures.country} t={t} />
          <ExposureBlock title={t('portfolio.sectors')} rows={currentExposures.industry} t={t} />
          <ExposureBlock title={t('portfolio.currencies')} rows={currentExposures.currency} t={t} />
        </div>

        {data_gaps.length > 0 && (
          <div className="data-gaps">
            <strong>{t('portfolio.dataNotes')}</strong>
            <ul>
              {data_gaps.map((gap, i) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      </div>

      {onBriefing && (
        <div className="briefing-bar">
          <button type="button" className="primary-button" onClick={() => onBriefing(portfolioNr)}>
            {t('portfolio.createBriefing')}
          </button>
        </div>
      )}
    </div>
  );
}

function GroupBlock({
  group,
  positions,
  collapsed,
  onToggle,
  t,
}: {
  group: PositionGroup;
  positions: PositionRow[];
  collapsed: boolean;
  onToggle: () => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}) {
  const categoryLabel = CATEGORY_LABEL_KEYS[group.category] 
    ? t(CATEGORY_LABEL_KEYS[group.category])
    : group.category;
    
  return (
    <>
      <tr className="group-row">
        <td colSpan={6}>
          <button type="button" className="group-toggle" onClick={onToggle}>
            {collapsed ? <SquarePlus size={14} /> : <SquareMinus size={14} />}
            <span>{categoryLabel}</span>
          </button>
        </td>
        <td className="num">{formatAmount(group.value)}</td>
        <td className="num">{formatFraction(group.weight)}</td>
        <td></td>
        <td></td>
        <td></td>
        <td></td>
      </tr>
      {!collapsed &&
        positions.map((p) => (
          <PositionRowView key={`${p.kind}-${p.security_id ?? p.position}`} position={p} t={t} />
        ))}
    </>
  );
}

function PositionRowView({ position, t }: { position: PositionRow; t: (key: MessageKey, vars?: Record<string, string | number>) => string }) {
  const priceCell =
    position.price !== null && position.price !== undefined
      ? formatAmount(position.price)
      : '—';
  const quantityCell =
    position.quantity !== null && position.quantity !== undefined
      ? formatAmount(position.quantity)
      : '—';
  const prcCell = position.prc !== null && position.prc !== undefined ? String(position.prc) : '—';
  const weightCell = position.weight !== null && position.weight !== undefined ? formatFraction(position.weight) : '—';
  const riskCell =
    position.risk_contribution !== null && position.risk_contribution !== undefined
      ? formatFraction(position.risk_contribution)
      : '—';
  const sustainCell =
    position.sustainability_score !== null && position.sustainability_score !== undefined
      ? String(position.sustainability_score)
      : '—';

  return (
    <tr className="position-row">
      <td className="position-name">{position.position}</td>
      <td>{position.kennung ?? '—'}</td>
      <td>{position.whg ?? '—'}</td>
      <td className="num">{prcCell}</td>
      <td className="num">{quantityCell}</td>
      <td className="num" title={t('portfolio.priceCostTooltip')}>
        {priceCell}
      </td>
      <td className="num">{formatAmount(position.value)}</td>
      <td className="num">{weightCell}</td>
      <td className="num" title={t('portfolio.performanceTooltip')}>
        —
      </td>
      <td className="num">{riskCell}</td>
      <td className="num">{sustainCell}</td>
      <td className="num" title={t('portfolio.rulesTooltip')}>
        —
      </td>
    </tr>
  );
}

function ExposureBlock({
  title,
  rows,
  t,
}: {
  title: string;
  rows: { category: string; value: number; weight: number }[];
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}) {
  const top = rows[0];
  const topLabel = top
    ? (CATEGORY_LABEL_KEYS[top.category] ? t(CATEGORY_LABEL_KEYS[top.category]) : top.category)
    : null;
  return (
    <div className="exposure-block">
      <div className="exposure-title">{title}</div>
      {top ? (
        <>
          <div className="exposure-value">{formatFraction(top.weight)}</div>
          <div className="exposure-category">{topLabel}</div>
        </>
      ) : (
        <div className="exposure-value">—</div>
      )}
    </div>
  );
}

function MetricCard({ widget }: { widget: Widget }) {
  const alertClass = widget.alert ? 'metric-alert' : '';
  const visual = renderWidgetVisual(widget);
  const valueText = formatWidgetValue(widget);
  return (
    <Card className={`metric-card ${alertClass}`} title={widget.title} padded>
      {/* Only when there is something to draw. A widget whose visual is absent must not reserve the
          space for one — that is what left empty cards around a single number. */}
      {visual ? (
        <div className="metric-visual" title={widget.formula}>
          {visual}
        </div>
      ) : null}
      <div className="metric-value">{valueText}</div>
      {/* When value_label/sub_label are present the value line already renders both numbers. */}
      {widget.sub && !widget.value_label && <div className="metric-sub">{widget.sub}</div>}
    </Card>
  );
}

function renderWidgetVisual(widget: Widget): ReactNode {
  switch (widget.type) {
    case 'donut': {
      const pct = typeof widget.value === 'number' ? widget.value : null;
      // No number, nothing to draw: the card must not reserve space for an empty ring (the
      // Sustainability widget states a profile name, not a share).
      if (pct === null) return null;
      // mode="rings" reads the value as the percentage to fill. In the default "arcs" mode a
      // single segment is normalised to its own sum, so every ring rendered full — 5% and 84%
      // looked identical.
      return (
        <DonutChart
          size={60}
          strokeWidth={6}
          mode="rings"
          segments={[{ value: pct, color: 'var(--primary)' }]}
          alert={widget.alert}
        />
      );
    }
    case 'scatter': {
      // No series exists in the widget payload (checked across the book), so there is nothing to
      // plot. The previous fallback drew four invented points in every portfolio — a chart that
      // looked like data and was not. The two real numbers render below instead.
      const points = widget.rows ?? [];
      if (points.length === 0) return null;
      return (
        <svg viewBox="0 0 60 30" width="60" height="30">
          {points.map((point, i) => (
            <circle
              key={i}
              cx={(i / Math.max(points.length - 1, 1)) * 56 + 2}
              cy={30 - point.value * 26}
              r={2}
              fill="var(--primary)"
            />
          ))}
        </svg>
      );
    }
    case 'map':
      return <Globe size={28} color="var(--primary)" />;
    case 'grid':
      return <LayoutGrid size={28} color="var(--primary)" />;
    case 'rows': {
      const rows = widget.rows ?? [];
      if (rows.length === 0) return null;
      return (
        <div className="metric-rows">
          {rows.slice(0, 3).map((r, i) => (
            <div key={i} className="metric-row-line">
              <span>{r.label}</span>
              <span>{formatAmount(r.value)}</span>
            </div>
          ))}
        </div>
      );
    }
    default:
      // 'line' and 'gauge' carry a value but no series; the value line states it.
      return null;
  }
}

function formatWidgetValue(widget: Widget): string {
  // value_label / sub_label: format both as percentages (e.g. risk_return)
  if (widget.value_label) {
    const valueText = typeof widget.value === 'number' ? formatPct(widget.value) : String(widget.value ?? '—');
    const subText = typeof widget.sub === 'number' ? formatPct(widget.sub) : (widget.sub ?? '');
    return subText ? `${valueText} / ${subText}` : valueText;
  }
  if (widget.value === null || widget.value === undefined) return '—';
  if (typeof widget.value === 'string') return widget.value;
  if (typeof widget.value !== 'number') return String(widget.value);

  // All numeric widget values from the backend are already in percentage form (e.g. 15.5 = 15.5%)
  // Exception: positions count is an integer
  if (widget.id === 'positions') {
    return String(Math.round(widget.value));
  }

  return formatPct(widget.value);
}
