import { useEffect, useState, useCallback } from 'react';
import type { Column } from '../../components/types';
import Card from '../../components/Card';
import DataTable from '../../components/DataTable';
import MetaBand from '../../components/MetaBand';
import { formatMoney, formatPct, formatAmount, formatDate } from '../../utils/format';
import { errorMessage, api } from '../../api/client';
import { useI18n } from '../../i18n';
import { fremdbankenStringsFor } from './strings';
import './fremdbanken.css';

interface Props {
  clientRef: string;
  onBack?: () => void;
}

interface ReportListItem {
  file: string;
  name: string;
  size: number;
  pages: number;
  /** 'side-challenge' for the ten provided statements, 'upload' for an advisor's PDF. */
  source: 'side-challenge' | 'upload';
}

interface CurrencyStructureEntry {
  code: string;
  name: string;
  amounts: {
    liquidity: number | null;
    bonds: number | null;
    shares: number | null;
    alternatives: number | null;
    total: number | null;
  };
  percents: {
    liquidity: number | null;
    bonds: number | null;
    shares: number | null;
    alternatives: number | null;
    total: number | null;
  };
  evidence: string;
}

interface Position {
  asset_class: string | null;
  name: string;
  currency: string;
  quantity: number | null;
  quantity_raw: string;
  valor: string | null;
  isin: string | null;
  cost_price: number | null;
  cost_price_raw: string | null;
  market_price: number | null;
  market_price_raw: string | null;
  cost_basis: number | null;
  market_value: number | null;
  market_value_raw: string;
  weight: number | null;
  weight_pct_raw: string;
  date: string | null;
  date_raw: string | null;
  is_cash: boolean;
  page: number;
  evidence: string;
  matched_security_id: number | null;
  matched_security_name: string | null;
}

interface Transaction {
  type: string;
  name: string;
  currency: string | null;
  quantity: number | null;
  quantity_raw: string | null;
  valor: string | null;
  isin: string | null;
  booking_date: string | null;
  booking_date_raw: string | null;
  price: number | null;
  price_raw: string | null;
  amount_chf: number | null;
  amount_chf_raw: string;
  cost: number | null;
  cost_raw: string;
  evidence: string;
}

interface ParsedPortfolio {
  source: string;
  provenance: string;
  file: string;
  pages: number;
  client_name: string | null;
  portfolio_label: string | null;
  depot_nr: string | null;
  mandat: string | null;
  reported_at: string | null;
  stichtag: string | null;
  currency: string;
  total_value: number | null;
  total_value_raw: string | null;
  performance_2025_twr_pct: number | null;
  performance_2025_twr_raw: string | null;
  positions: Position[];
  position_count: number;
  position_total_chf: number | null;
  position_total_vs_reported_delta: number | null;
  currency_structure: CurrencyStructureEntry[];
  unhedged_foreign_currency_chf: number | null;
  unhedged_foreign_currency_pct: number | null;
  transactions: Transaction[];
  transaction_count: number;
  isins_matched: number;
  isins_unmatched: string[];
  unavailable: string[];
  gaps: string[];
  evidence: {
    kpi: string;
    currency_structure: string;
    positions: string[];
    transactions: string;
  };
}

interface ImportResponse {
  portfolio_nr: string;
  report: ParsedPortfolio;
}

/** A string field of an unvalidated JSON object, or undefined. */
function stringField(value: unknown, key: string): string | undefined {
  if (!value || typeof value !== 'object' || !(key in value)) return undefined;
  // JSON.parse output: the key test above is what makes this record view safe to read.
  const record = value as Record<string, unknown>;
  const found = record[key];
  return typeof found === 'string' ? found : undefined;
}

/**
 * The server's own reason for a failed import, in the advisor's language.
 *
 * Two shapes travel: a plain string (not found, unknown client) and a structured detail for the
 * cases the panel explains better than raw JSON — a duplicate import, a PDF the reader could not
 * make sense of, and a statement with no readable positions.
 */
async function importErrorMessage(
  res: Response,
  s: { alreadyImported: string; unreadablePdf: string; noPositionsImported: string },
): Promise<string> {
  const raw = await res.text();
  let detail: unknown;
  try {
    const payload: unknown = JSON.parse(raw);
    detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? (payload as Record<string, unknown>).detail
        : undefined;
  } catch {
    return raw || `HTTP ${res.status}`;
  }

  const code = stringField(detail, 'code');
  if (res.status === 409 && code === 'already_imported') {
    return s.alreadyImported
      .replace('{nr}', stringField(detail, 'portfolio_nr') ?? '')
      .replace('{file}', stringField(detail, 'source_file') ?? '');
  }
  if (code === 'unreadable_pdf') return s.unreadablePdf;
  if (code === 'no_positions') return s.noPositionsImported;
  if (typeof detail === 'string') return detail;
  return stringField(detail, 'message') ?? raw ?? `HTTP ${res.status}`;
}

export default function FremdbankenPanel({ clientRef, onBack }: Props) {
  const { lang } = useI18n();
  const s = fremdbankenStringsFor(lang);
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [imported, setImported] = useState<ImportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportsError, setReportsError] = useState<string | null>(null);

  const handleSelectReport = useCallback(async (file: string) => {
    setSelectedFile(file);
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/import/ex-custody', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file, client_ref: clientRef, lang }),
      });
      if (!res.ok) {
        throw new Error(await importErrorMessage(res, s));
      }
      const data: ImportResponse = await res.json();
      setImported(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [clientRef, lang]);

  const handleUpload = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    setSelectedFile(file.name);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('client_ref', clientRef);
      const res = await fetch(`/api/import/ex-custody/upload?lang=${lang}`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        throw new Error(await importErrorMessage(res, s));
      }
      const data: ImportResponse = await res.json();
      setImported(data);
      // The uploaded statement joins the picker as well, so a second advisor sees it listed.
      setReports((current) => [...current, {
        file: data.report.file,
        name: data.report.client_name ?? data.report.file,
        size: 0,
        pages: data.report.pages,
        source: 'upload',
      }]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [clientRef, lang, s]);

  // Fetch reports on mount — uses api client for deduplication
  useEffect(() => {
    let cancelled = false;
    async function fetchReports() {
      try {
        const data = await api.get<{ reports: ReportListItem[] }>('/api/import/reports', lang);
        if (!cancelled) {
          setReports(data.reports);
        }
      } catch (err) {
        if (!cancelled) {
          setReportsError(errorMessage(err));
        }
      }
    }
    fetchReports();
    return () => {
      cancelled = true;
    };
  }, []);

  // No auto-import. Selecting a report *is* the advisor's action, and importing on mount meant every
  // visit to this screen stored another copy of the same portfolio (three visits produced three
  // `EXT-*` portfolios). The picker below is the intended flow; the duplicate store is what this
  // replaces.

  // Position columns
  const positionColumns: Column<Position>[] = [
    {
      key: 'name',
      label: s.colPosition,
      render: (row) => (
        <div className="uro-fremdbanken__position-row">
          <span>{row.name}</span>
          <span className="uro-fremdbanken__page-chip">S. {row.page}</span>
        </div>
      ),
    },
    {
      key: 'identifier',
      label: 'ISIN / Valor',
      render: (row) => {
        if (row.is_cash) return <span style={{ color: 'var(--text-muted)' }}>{s.cash}</span>;
        const parts: string[] = [];
        if (row.isin) parts.push(row.isin);
        if (row.valor) parts.push(s.valorLabel.replace('{valor}', String(row.valor)));
        return <span>{parts.join(' / ') || '—'}</span>;
      },
    },
    {
      key: 'currency',
      label: s.colCurrency,
      align: 'center',
    },
    {
      key: 'quantity',
      label: s.colQuantity,
      align: 'right',
      render: (row) => (row.quantity !== null ? formatAmount(row.quantity, 2) : '—'),
    },
    {
      key: 'market_price',
      label: s.colMarketPrice,
      align: 'right',
      render: (row) => (row.market_price !== null ? formatAmount(row.market_price, 2) : '—'),
    },
    {
      key: 'cost_price',
      label: s.colCostPrice,
      align: 'right',
      render: (row) => (row.cost_price !== null ? formatAmount(row.cost_price, 2) : '—'),
    },
    {
      key: 'weight',
      label: s.colWeight,
      align: 'right',
      render: (row) => (row.weight !== null ? formatPct(row.weight * 100, 2) : '—'),
    },
    {
      key: 'match',
      label: s.colStatus,
      align: 'center',
      render: (row) => {
        if (row.is_cash) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
        if (row.matched_security_id !== null) {
          return (
            <span className="uro-fremdbanken__match-badge uro-fremdbanken__match-badge--matched">
              ✓ Erfasst
            </span>
          );
        }
        return (
          <span className="uro-fremdbanken__match-badge uro-fremdbanken__match-badge--unmatched">
            ? Unbekannt
          </span>
        );
      },
    },
  ];

  // Currency structure columns
  const currencyColumns: Column<CurrencyStructureEntry>[] = [
    { key: 'code', label: s.colCurrencyCode },
    { key: 'name', label: s.colName },
    {
      key: 'liquidity',
      label: s.colLiquidity,
      align: 'right',
      render: (row) => (row.amounts.liquidity !== null ? formatAmount(row.amounts.liquidity, 0) : '—'),
    },
    {
      key: 'bonds',
      label: s.colBonds,
      align: 'right',
      render: (row) => (row.amounts.bonds !== null ? formatAmount(row.amounts.bonds, 0) : '—'),
    },
    {
      key: 'shares',
      label: s.colShares,
      align: 'right',
      render: (row) => (row.amounts.shares !== null ? formatAmount(row.amounts.shares, 0) : '—'),
    },
    {
      key: 'alternatives',
      label: s.colAlternatives,
      align: 'right',
      render: (row) => (row.amounts.alternatives !== null ? formatAmount(row.amounts.alternatives, 0) : '—'),
    },
    {
      key: 'total',
      label: s.colTotal,
      align: 'right',
      render: (row) => (row.amounts.total !== null ? formatAmount(row.amounts.total, 0) : '—'),
    },
  ];

  // Transaction columns
  const transactionColumns: Column<Transaction>[] = [
    {
      key: 'type',
      label: s.colType,
      render: (row) => {
        const typeLabels: Record<string, string> = {
          Kauf: s.txBuy,
          Verkauf: s.txSell,
          Dividende: s.txDividend,
          Coupon: s.txCoupon,
          Depotgebühren: s.txCustodyFees,
          Vermögenszufluss: s.txInflow,
        };
        return typeLabels[row.type] || row.type;
      },
    },
    { key: 'name', label: s.colDescription },
    {
      key: 'booking_date',
      label: s.colDate,
      render: (row) => formatDate(row.booking_date),
    },
    {
      key: 'amount_chf',
      label: s.colAmountChf,
      align: 'right',
      render: (row) => (row.amount_chf !== null ? formatMoney(row.amount_chf, 'CHF', 2) : '—'),
    },
    {
      key: 'cost',
      label: s.colCostIncome,
      align: 'right',
      render: (row) => (row.cost !== null ? formatMoney(row.cost, 'CHF', 2) : '—'),
    },
  ];

  // Reports fetch error
  if (reportsError) {
    return (
      <div className="uro-fremdbanken">
        <div className="uro-fremdbanken__header">
          {onBack && (
            <button className="uro-fremdbanken__back-btn" onClick={onBack}>
              {s.back}
            </button>
          )}
          <div className="uro-fremdbanken__bank">{s.bankName}</div>
          <h1 className="uro-fremdbanken__title">{s.title}</h1>
        </div>
        <div className="uro-fremdbanken__declaration">
          <strong>{s.declarationTitle}</strong>
          <div>{s.declarationBody}
          </div>
        </div>
        <div className="uro-fremdbanken__error">
          <strong>{s.reportsLoadError}</strong>
          <div>{reportsError}</div>
        </div>
      </div>
    );
  }

  // The parsed statement lives on `report` (snake_case view model); `portfolio` is the F5 shape.
  const portfolio = imported?.report;

  return (
    <div className="uro-fremdbanken">
      {/* Header */}
      <div className="uro-fremdbanken__header">
        {onBack && (
          <button className="uro-fremdbanken__back-btn" onClick={onBack}>
            {s.back}
          </button>
        )}
        <div className="uro-fremdbanken__bank">{s.bankName}</div>
        <h1 className="uro-fremdbanken__title">
          {portfolio?.client_name || s.titleFallback}
        </h1>
        <div className="uro-fremdbanken__meta">
          {portfolio?.file && <span>{s.file}: {portfolio.file}</span>}
          {imported?.portfolio_nr && (
            <>
              {' · '}
              <span>{s.portfolioNr}: {imported.portfolio_nr}</span>
            </>
          )}
        </div>
      </div>

      {/* Declaration — always visible above the fold */}
      <div className="uro-fremdbanken__declaration">
        <strong>{s.declarationTitle}</strong>
        <div>{s.declarationBody}
        </div>
      </div>

      {/* Import error */}
      {error && (
        <div className="uro-fremdbanken__error">
          <strong>{s.importError}</strong>
          <div>{error}</div>
        </div>
      )}

      {/* Report picker */}
      {!imported && !loading && reports.length > 0 && (
        <Card title={s.selectReport}>
          <div className="uro-fremdbanken__picker">
            <div className="uro-fremdbanken__picker-label">
              {s.availableReports.replace('{count}', String(reports.length))}
            </div>
            <div className="uro-fremdbanken__report-list">
              {reports.map((report) => (
                <div
                  key={report.file}
                  className={`uro-fremdbanken__report-item${
                    selectedFile === report.file ? ' uro-fremdbanken__report-item--active' : ''
                  }`}
                  onClick={() => handleSelectReport(report.file)}
                >
                  <div>
                    <div className="uro-fremdbanken__report-name">
                      {report.name}
                      {report.source === 'upload' ? (
                        <span className="uro-fremdbanken__report-badge">{s.uploaded}</span>
                      ) : null}
                    </div>
                    <div className="uro-fremdbanken__report-meta">
                      {report.pages} {s.pages} · {(report.size / 1024).toFixed(1)} KB
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* The brief's bonus challenge: a statement the advisor uploads, not one of the samples. */}
          <div className="uro-fremdbanken__upload">
            <div className="uro-fremdbanken__upload-title">{s.uploadTitle}</div>
            <div className="uro-fremdbanken__upload-hint">{s.uploadHint}</div>
            <label className="uro-fremdbanken__upload-button">
              {s.uploadButton}
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => {
                  const chosen = event.target.files?.[0];
                  if (chosen) void handleUpload(chosen);
                  event.target.value = '';
                }}
              />
            </label>
          </div>
        </Card>
      )}

      {/* Loading */}
      {loading && (
        <div className="uro-fremdbanken__loading">{s.importing}</div>
      )}

      {/* Imported portfolio */}
      {portfolio && !loading && (
        <>
          {/* KPI card */}
          <Card title={s.kpi}>
            <MetaBand
              pairs={[
                {
                  label: s.keyDate,
                  value: formatDate(portfolio.stichtag),
                },
                {
                  label: s.reportingCurrency,
                  value: portfolio.currency,
                },
                {
                  label: s.positions,
                  value: String(portfolio.position_count),
                },
                {
                  label: s.transactions,
                  value: String(portfolio.transaction_count),
                },
              ]}
            />
            <div className="uro-fremdbanken__kpi-grid" style={{ marginTop: 'var(--space-4)' }}>
              <div className="uro-fremdbanken__kpi">
                <div className="uro-fremdbanken__kpi-label">{s.assetsAsOfKeyDate}</div>
                <div className="uro-fremdbanken__kpi-value">
                  {formatMoney(portfolio.total_value, portfolio.currency)}
                </div>
              </div>
              <div className="uro-fremdbanken__kpi">
                <div className="uro-fremdbanken__kpi-label">{s.performance2025}</div>
                <div className="uro-fremdbanken__kpi-value">
                  {formatPct(portfolio.performance_2025_twr_pct, 2)}
                </div>
              </div>
              {portfolio.position_total_vs_reported_delta !== null && (
                <div className="uro-fremdbanken__kpi">
                  <div className="uro-fremdbanken__kpi-label">
                    {s.deltaPositionsVsReport}
                  </div>
                  <div className="uro-fremdbanken__kpi-value">
                    {formatMoney(portfolio.position_total_vs_reported_delta, portfolio.currency)}
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Currency structure */}
          {(portfolio.currency_structure?.length ?? 0) > 0 && (
            <Card title={s.currencyStructure}>
              <DataTable<CurrencyStructureEntry>
                columns={currencyColumns}
                rows={portfolio.currency_structure}
                rowKey={(row) => row.code}
                emptyText={s.noCurrencyStructure}
              />
            </Card>
          )}

          {/* Positions ledger */}
          <Card title={s.detailPositions}>
            <DataTable<Position>
              columns={positionColumns}
              rows={portfolio.positions ?? []}
              rowKey={(row) => `${row.isin || row.valor || row.name}-${row.page}-${row.currency}`}
              emptyText={s.noPositions}
            />
            <div style={{ marginTop: 'var(--space-3)', fontSize: 'var(--fs-cell)', color: 'var(--text-muted)' }}>
              {s.isinsMatched.replace('{count}', String(portfolio.isins_matched ?? 0))} · {s.isinsUnknown.replace('{count}', String(portfolio.isins_unmatched?.length ?? 0))}
            </div>
          </Card>

          {/* Transactions */}
          {(portfolio.transactions?.length ?? 0) > 0 && (
            <Card title={s.transactions}>
              <DataTable<Transaction>
                columns={transactionColumns}
                rows={portfolio.transactions ?? []}
                rowKey={(row) => `${row.type}-${row.name}-${row.booking_date || 'x'}-${row.amount_chf ?? 0}`}
                emptyText={s.noTransactions}
              />
            </Card>
          )}

          {/* Gaps and unavailable */}
          {((portfolio.gaps?.length ?? 0) > 0 || (portfolio.unavailable?.length ?? 0) > 0) && (
            <Card title={s.dataQualityNotes}>
              <div className="uro-fremdbanken__gaps-list">
                {(portfolio.gaps ?? []).map((gap, idx) => (
                  <div key={`gap-${idx}`} className="uro-fremdbanken__gap-item">
                    {gap}
                  </div>
                ))}
                {(portfolio.unavailable ?? []).map((item, idx) => (
                  <div key={`unavail-${idx}`} className="uro-fremdbanken__gap-item">
                    {item}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
