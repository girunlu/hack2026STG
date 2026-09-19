import { useEffect, useMemo, useState } from 'react';
import { useI18n, type MessageKey } from '../../i18n';
import { api, errorMessage } from '../../api/client';
import type { MarketSearchResponse, MarketSignal } from '../../types';
import { formatAmount, formatDate, formatFraction } from '../../utils/format';
import './market.css';

/**
 * The model returns a fixed vocabulary; these map it to the catalogue. A `t()` call built by
 * interpolation would not be type-checked against the message keys, so the mapping is explicit.
 */
const SENTIMENT_KEYS: Record<MarketSignal['sentiment'], MessageKey> = {
  positive: 'market.sentiment.positive',
  negative: 'market.sentiment.negative',
  neutral: 'market.sentiment.neutral',
  mixed: 'market.sentiment.mixed',
};

const MATERIALITY_KEYS: Record<MarketSignal['materiality'], MessageKey> = {
  high: 'market.materiality.high',
  medium: 'market.materiality.medium',
  low: 'market.materiality.low',
};

interface Props {
  query: string | null;
  onSearch: (q: string) => void;
}

/**
 * Market search panel — advisor tool for quick instrument research.
 * Fetches from /api/market/search and displays instrument details, holdings, news, bank view, and gaps.
 */
export default function MarketSearchPanel({ query, onSearch }: Props) {
  const { lang, t } = useI18n();
  const [input, setInput] = useState(query ?? '');
  const [data, setData] = useState<MarketSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync input when query prop changes (e.g. URL navigation)
  useEffect(() => {
    if (query !== null) setInput(query);
  }, [query]);

  // Fetch when query changes
  useEffect(() => {
    if (!query) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .marketSearch(query, lang)
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
  }, [query, lang]);

  // Signals arrive for exactly the headlines that were sent, so they are matched by headline text.
  // A null-prototype record: the keys are headlines from an external feed, not our own vocabulary.
  const signalByHeadline = useMemo(() => {
    const index: Record<string, MarketSignal> = Object.create(null);
    for (const signal of data?.signals.items ?? []) index[signal.headline] = signal;
    return index;
  }, [data]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (trimmed) onSearch(trimmed);
  };

  return (
    <div className="market-screen">
      <div className="market-toolbar">
        <span className="market-toolbar__title">{t('market.title')}</span>
        {data?.as_of && (
          <span className="market-toolbar__asof">
            {t('market.asOf', { date: formatDate(data.as_of) })}
          </span>
        )}
      </div>

      <form className="market-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="market-form__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('market.placeholder')}
          aria-label={t('market.placeholder')}
        />
        <button type="submit" className="market-form__btn" disabled={loading}>
          {t('market.submit')}
        </button>
      </form>

      {!query && !loading && !error && (
        <div className="market-prompt">
          <div className="market-prompt__title">{t('market.promptTitle')}</div>
          <div className="market-prompt__body">{t('market.promptBody')}</div>
        </div>
      )}

      {loading && <div className="market-loading">{t('market.loading')}</div>}

      {error && (
        <div className="market-error">
          <div className="market-error__title">{t('market.errorTitle')}</div>
          <div>{error}</div>
        </div>
      )}

      {data && !loading && !error && (
        <>
          {/* Instrument card */}
          <section className="market-section">
            <h2 className="market-section__title">
              {t('market.instrument')}
              {data.instrument.matched ? (
                data.query_kind ? (
                  <span className="market-chip market-chip--live">
                    {t('market.queryKind', { kind: data.query_kind })}
                  </span>
                ) : null
              ) : (
                <span className="market-chip market-chip--muted">
                  {t('market.matchedFalse')}
                </span>
              )}
            </h2>

            {!data.instrument.matched && (
              <div className="market-matched-warn">{t('market.matchedFalse')}</div>
            )}

            <div className="market-instrument__header">
              <span className="market-instrument__name">
                {data.instrument.display_name ?? '—'}
              </span>
              {data.instrument.name && data.instrument.name !== data.instrument.display_name && (
                <span className="market-instrument__raw">
                  {data.instrument.name}
                </span>
              )}
            </div>

            <div className="market-kv-grid">
              <div className="market-kv">
                <span className="market-kv__label">{t('market.isin')}</span>
                <span className="market-kv__value">{data.instrument.isin ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.valor')}</span>
                <span className="market-kv__value">{data.instrument.valor ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.securityType')}</span>
                <span className="market-kv__value">{data.instrument.security_type ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.currency')}</span>
                <span className="market-kv__value">{data.instrument.currency ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.assetClass')}</span>
                <span className="market-kv__value">{data.instrument.asset_class ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.assetClassDetailed')}</span>
                <span className="market-kv__value">{data.instrument.asset_class_detailed ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.industry')}</span>
                <span className="market-kv__value">{data.instrument.industry ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.country')}</span>
                <span className="market-kv__value">{data.instrument.country ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.countryGroup')}</span>
                <span className="market-kv__value">{data.instrument.country_group ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.price')}</span>
                <span className="market-kv__value">
                  {data.instrument.price !== null ? formatAmount(data.instrument.price, 2) : '—'}
                </span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.priceDate')}</span>
                <span className="market-kv__value">{formatDate(data.instrument.price_date)}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.volatility')}</span>
                <span className="market-kv__value">
                  {data.instrument.volatility !== null ? formatFraction(data.instrument.volatility, 2) : '—'}
                </span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.sustainability')}</span>
                <span className="market-kv__value">
                  {data.instrument.sustainability_score !== null ? formatAmount(data.instrument.sustainability_score, 1) : '—'}
                </span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.prc')}</span>
                <span className="market-kv__value">
                  {data.instrument.prc !== null ? data.instrument.prc : '—'}
                </span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.bankRating')}</span>
                <span className="market-kv__value">{data.instrument.bank_rating ?? '—'}</span>
              </div>
              <div className="market-kv">
                <span className="market-kv__label">{t('market.recommendationList')}</span>
                <span className="market-kv__value">
                  {data.instrument.in_recommendation_list ? (
                    <span className="market-chip market-chip--rec">
                      {t('market.inRecommendationList')}
                    </span>
                  ) : (
                    t('market.notInRecommendationList')
                  )}
                </span>
              </div>
            </div>

            {(data.instrument.recommendation_lists ?? []).length > 0 && (
              <div className="market-kv" style={{ marginTop: 'var(--space-2)' }}>
                <span className="market-kv__label">{t('market.recommendationList')}</span>
                <span className="market-kv__value">
                  {(data.instrument.recommendation_lists ?? []).join(', ')}
                </span>
              </div>
            )}

            {data.instrument.alternatives.length > 0 && (
              <div className="market-alternatives">
                <div className="market-alternatives__title">{t('market.alternatives')}</div>
                <div className="market-alternatives__list">
                  {data.instrument.alternatives.map((alt) => (
                    <span key={alt.security_id} className="market-alternative">
                      {alt.name}
                      {alt.isin && ` · ${alt.isin}`}
                      {alt.currency && ` · ${alt.currency}`}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Held by clients */}
          <section className="market-section">
            <h2 className="market-section__title">{t('market.heldBy')}</h2>
            <div className="market-heldby__head">
              <span className="market-heldby__count">
                {t('market.heldByCount', {
                  count: data.held_by_total,
                  total: data.held_by.length,
                })}
              </span>
              {data.portfolio_weight !== null && (
                <span className="market-heldby__max">
                  {t('market.largestPosition')}: {formatFraction(data.portfolio_weight, 2)}
                </span>
              )}
            </div>
            {data.held_by.length === 0 ? (
              <div className="market-empty">{t('market.noClientsHold')}</div>
            ) : (
              <table className="market-table">
                <thead>
                  <tr>
                    <th>{t('market.client')}</th>
                    <th>{t('market.portfolioNr')}</th>
                    <th className="num">{t('market.weight')}</th>
                    <th className="num">{t('market.value')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.held_by.map((row) => (
                    <tr key={`${row.client_ref}-${row.portfolio_nr}`}>
                      <td>
                        {row.client_name} <span style={{ color: 'var(--text-muted)' }}>({row.client_ref})</span>
                      </td>
                      <td>{row.portfolio_nr}</td>
                      <td className="num">{formatFraction(row.weight, 2)}</td>
                      <td className="num">
                        {row.currency} {formatAmount(row.value, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* News */}
          <section className="market-section">
            <h2 className="market-section__title">
              {t('market.news')}
              {data.news.providers_used.length > 0 && (
                <span className="market-chip market-chip--live">
                  {t('market.newsLive')} · {data.news.providers_used.join(', ')}
                </span>
              )}
            </h2>
            {data.news.items.length === 0 ? (
              <div className="market-empty">{t('market.noNews')}</div>
            ) : (
              <>
                <div className="market-signals__head">
                  {data.signals.applied ? (
                    <span className="market-chip market-chip--live">
                      {t('market.signalsLlm', { model: data.signals.model ?? '' })}
                    </span>
                  ) : (
                    <span className="market-chip market-chip--muted">
                      {t('market.signalsUnavailable', { reason: data.signals.reason ?? '' })}
                    </span>
                  )}
                </div>
                <div className="market-news__list">
                  {data.news.items.map((item, idx) => {
                    const signal = signalByHeadline[item.headline];
                    return (
                      <div key={idx} className="market-news__item">
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="market-news__headline"
                          >
                            {item.headline}
                          </a>
                        ) : (
                          <div className="market-news__headline">{item.headline}</div>
                        )}
                        <div className="market-news__meta">
                          {item.source && <span>{item.source}</span>}
                          {item.source && item.published && <span> · </span>}
                          {item.published && <span>{formatDate(item.published)}</span>}
                        </div>
                        {signal && (
                          <div className={`market-signal market-signal--${signal.sentiment}`}>
                            <span className="market-signal__tags">
                              <span className={`market-chip market-signal__chip--${signal.sentiment}`}>
                                {t(SENTIMENT_KEYS[signal.sentiment])}
                              </span>
                              <span className={`market-chip market-signal__chip--${signal.materiality}`}>
                                {t(MATERIALITY_KEYS[signal.materiality])}
                              </span>
                            </span>
                            <span className="market-signal__why">{signal.why}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
            {data.news.notes.length > 0 && (
              <div className="market-news__notes">
                <strong>{t('market.newsNotes')}:</strong>
                <ul style={{ margin: 'var(--space-1) 0 0', paddingLeft: 'var(--space-4)' }}>
                  {data.news.notes.map((note, idx) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {/* Bank view */}
          {data.bank_view && (
            <section className="market-section">
              <h2 className="market-section__title">
                {t('market.bankView')}
                {data.bank_view.mock && (
                  <span className="market-chip market-chip--mock">
                    {t('market.bankViewMock')}
                  </span>
                )}
              </h2>
              <div className="market-bankview__head">
                {data.bank_view.source && (
                  <span className="market-bankview__source">{data.bank_view.source}</span>
                )}
                {data.bank_view.as_of && (
                  <span className="market-bankview__asof">
                    {t('market.bankViewAsOf')}: {formatDate(data.bank_view.as_of)}
                  </span>
                )}
              </div>
              {data.bank_view.stances.length > 0 && (
                <table className="market-table">
                  <thead>
                    <tr>
                      <th>{t('market.bankViewDimension')}</th>
                      <th>{t('market.bankViewCategory')}</th>
                      <th>{t('market.bankViewStance')}</th>
                      <th>{t('market.bankViewNote')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.bank_view.stances.map((stance, idx) => (
                      <tr key={idx}>
                        <td>{stance.dimension}</td>
                        <td>{stance.category}</td>
                        <td>{stance.stance}</td>
                        <td>{stance.note ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {data.bank_view.disclaimer && (
                <div className="market-bankview__disclaimer">
                  <strong>{t('market.bankViewDisclaimer')}:</strong> {data.bank_view.disclaimer}
                </div>
              )}
            </section>
          )}

          {/* Unavailable data */}
          {(data.unavailable.length > 0 || data.news.unavailable.length > 0) && (
            <section className="market-section">
              <h2 className="market-section__title">{t('market.unavailable')}</h2>
              <ul className="market-unavailable__list">
                {data.unavailable.map((gap, idx) => (
                  <li key={`top-${idx}`}>{gap}</li>
                ))}
                {data.news.unavailable.map((gap, idx) => (
                  <li key={`news-${idx}`}>{gap.reason}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
