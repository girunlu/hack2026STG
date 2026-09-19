import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { api, errorMessage } from '../../api/client';
import DataTable from '../../components/DataTable';
import FilterTabs from '../../components/FilterTabs';
import MetaBand from '../../components/MetaBand';
import Pagination from '../../components/Pagination';
import SearchBox from '../../components/SearchBox';
import type { Column, SortState } from '../../components/types';
import { useShellBadges } from '../../shell/ShellContext';
import type { ClientRow, ClientsResponse, Tab } from '../../types';
import { formatDate, formatMoney } from '../../utils/format';
import ClientFileImport from '../../components/ClientFileImport';
import { useI18n } from '../../i18n';


import './dashboard.css';

interface Props {
  onOpenClient: (clientRef: string) => void;
  /** Filter tab requested by the shell nav; kept in the URL so it survives refresh. */
  tab?: string;
  /** Called when the active tab changes, so the shell can update the URL. */
  onTabChange?: (tab: string) => void;
}

type TabId =
  | 'kunden'
  | 'beratungen'
  | 'liquidity_gt_10'
  | 'maturities'
  | 'last_consultation_gt_12m'
  | 'rule_violations'
  | 'warnings'
  | 'birthdays';

const PAGE_SIZE_OPTIONS = [10, 25, 50];
const BIRTHDAY_WINDOW = 90;

/**
 * F2 — the advisor's home screen. Fetches `GET /api/clients`, renders the welcome meta band,
 * the filter tab bar, the search box, the sortable client table and pagination. All tab filtering,
 * sorting and pagination are real client-side computations over the response rows — no counts,
 * dates or names are hard-coded.
 */
export default function DashboardScreen({ onOpenClient, tab, onTabChange }: Props) {
  const { lang, t } = useI18n();
  const [data, setData] = useState<ClientsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);


  const [activeTab, setActiveTab] = useState<string>('kunden');
  const [search, setSearch] = useState<string>('');
  const [sort, setSort] = useState<SortState>({ key: null, direction: 'asc' });
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (tab) setActiveTab(tab);
  }, [tab]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .clients(lang)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // Publish nav badges as soon as we have the counts.
  useShellBadges({
    regelverletzungen: data?.counts.error_violations ?? null,
    warnungen: data?.counts.warning_violations ?? null,
  });

  const referenceDate = data?.data_as_of ?? null;

  // Stale-cutoff date: reference minus 12 months, ISO-formatted for lex compare.
  const staleBefore = useMemo<string | null>(() => {
    if (!referenceDate || referenceDate.length < 10) return null;
    const y = Number(referenceDate.slice(0, 4));
    const m = Number(referenceDate.slice(5, 7));
    const d = Number(referenceDate.slice(8, 10));
    if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return null;
    return new Date(Date.UTC(y - 1, m - 1, d)).toISOString().slice(0, 10);
  }, [referenceDate]);

  // --- Tab filtering: real predicates over the row fields, mirroring the backend's `_tabs`.
  const filteredByTab = useMemo<ClientRow[]>(() => {
    if (!data) return [];
    const rows = data.rows;
    switch (activeTab as TabId) {
      case 'kunden':
        return rows;
      case 'beratungen':
        return rows.filter((r) => !!r.last_consultation);
      case 'liquidity_gt_10':
        return rows.filter((r) => (r.liquidity_pct ?? 0) > 0.1);
      case 'maturities':
        return rows.filter((r) => r.has_maturities);
      case 'last_consultation_gt_12m':
        return rows.filter(
          (r) => !r.last_consultation || (staleBefore !== null && r.last_consultation < staleBefore),
        );
      case 'rule_violations':
        return rows.filter((r) => r.has_violation);
      case 'warnings':
        return rows.filter((r) => r.has_warning);
      case 'birthdays':
        return rows.filter(
          (r) =>
            r.days_to_birthday !== null &&
            r.days_to_birthday !== undefined &&
            r.days_to_birthday <= BIRTHDAY_WINDOW,
        );
      default:
        return rows;
    }
  }, [data, activeTab, staleBefore]);

  // --- Search: matches name, ref, city (when present). Empty search is a no-op.
  const filteredBySearch = useMemo<ClientRow[]>(() => {
    const q = search.trim().toLowerCase();
    if (!q) return filteredByTab;
    return filteredByTab.filter((r) => {
      const hay = [r.ref, r.name, r.city ?? ''].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [filteredByTab, search]);

  // --- Sort: stable, case-insensitive for strings, ISO-lex for dates (nulls last).
  const sorted = useMemo<ClientRow[]>(() => {
    if (!sort.key) return filteredBySearch;
    const dir = sort.direction === 'asc' ? 1 : -1;
    const key = sort.key;
    const copy = filteredBySearch.slice();
    copy.sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[key];
      const bv = (b as unknown as Record<string, unknown>)[key];
      if (av == null && bv == null) return 0;
      if (av == null) return dir;
      if (bv == null) return -dir;
      if (typeof av === 'string' && typeof bv === 'string') {
        return dir * av.localeCompare(bv, 'de-CH', { sensitivity: 'base' });
      }
      if (typeof av === 'number' && typeof bv === 'number') return dir * (av - bv);
      return dir * String(av).localeCompare(String(bv), 'de-CH', { sensitivity: 'base' });
    });
    return copy;
  }, [filteredBySearch, sort]);

  // Clamp page when filters shrink the result set.
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, pageCount);
  useEffect(() => {
    if (safePage !== page) setPage(safePage);
  }, [page, safePage]);

  // Reset to page 1 when tab/search/pageSize change.
  useEffect(() => {
    setPage(1);
  }, [activeTab, search, pageSize]);

  const pageRows = useMemo<ClientRow[]>(() => {
    const start = (safePage - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, safePage, pageSize]);

  const columns = useMemo<Column<ClientRow>[]>(() => {
    const nameRender = (row: ClientRow): ReactNode => (
      <a
        className="dash-name-link"
        href={`#/client/${encodeURIComponent(row.ref)}`}
        onClick={(e) => {
          e.preventDefault();
          onOpenClient(row.ref);
        }}
        title={row.type ?? undefined}
      >
        {row.name}
      </a>
    );
    // The violation and warning cells are drawn by DataTable itself (`showIndicators` below), which
    // owns their aria-labelled header cells. Declaring them here *as well* put four indicator cells in
    // every row: each icon appeared twice, and the surplus cells pushed every value one column to the
    // left of its header — the client number under an empty slot, the name under "Client no.", the
    // birthday under "Name", with "Last consultation" left empty.
    return [
      { key: 'ref', label: t('dashboard.colClientNr'), sortable: true, width: '110px', render: (r) => r.ref },
      { key: 'name', label: t('dashboard.colName'), sortable: true, render: nameRender },
      {
        key: 'birthday',
        label: t('dashboard.colBirthday'),
        sortable: true,
        width: '120px',
        render: (r) => formatDate(r.birthday),
      },
      {
        key: 'profiling_date',
        label: t('dashboard.colProfiling'),
        sortable: true,
        width: '150px',
        render: (r) => formatDate(r.profiling_date),
      },
      {
        key: 'last_changed',
        label: t('dashboard.colLastChanged'),
        sortable: true,
        width: '150px',
        render: (r) => formatDate(r.last_changed),
      },
      {
        key: 'last_consultation',
        label: t('dashboard.colLastConsultation'),
        sortable: true,
        width: '150px',
        render: (r) => formatDate(r.last_consultation),
      },
    ];
  }, [onOpenClient, t]);


  const tabs = useMemo(
    () =>
      (data?.tabs ?? []).map((t: Tab) => ({
        id: t.id,
        label: t.label,
        count: t.count,
        hint: t.hint ?? null,
        unsupported: !t.supported,
      })),
    [data],
  );

  if (loading) {
    return <div className="screen screen-loading">{t('dashboard.loadingClients')}</div>;
  }
  if (error || !data) {
    return (
      <div className="screen">
        <div className="screen-error">
          <strong>{t('dashboard.loadError')}</strong>
          <div>{error ?? t('dashboard.unknownError')}</div>
        </div>
      </div>
    );
  }

  const welcomeSecondLine =
    `${t('dashboard.pendingConsultations', { count: data.counts.open_proposals ?? 0 })} | ${t('dashboard.restrictions')} | ${t('dashboard.warningsCount', { count: data.counts.warning_violations ?? 0 })}`;

  return (
    <>
      <MetaBand
        left={
          <div className="dash-welcome">
            <div className="dash-welcome-title">
              {t('dashboard.welcomeBack', { name: data.advisor.name })}
            </div>
            <div className="dash-welcome-sub muted">{welcomeSecondLine}</div>
          </div>
        }
        right={
          <div className="dash-book-total tabular">
            {formatMoney(data.book_total.amount, data.book_total.currency)}
          </div>
        }
      />
      <div className="screen">
        <h2 className="dash-section-title">{t('dashboard.myClients')}</h2>

        <div className="dash-toolbar">
          <FilterTabs tabs={tabs} active={activeTab} onChange={(id) => { setActiveTab(id); onTabChange?.(id); }} />
          <SearchBox value={search} onChange={setSearch} placeholder={t('common.search')} />
          <ClientFileImport onImported={() => setReloadKey((k) => k + 1)} />
        </div>

        <DataTable<ClientRow>
          columns={columns}
          rows={pageRows}
          rowKey={(r) => r.ref}
          onRowClick={(r) => onOpenClient(r.ref)}
          // No checkbox column: the prototype has no bulk action, and a checkbox that selects nothing
          // but bubbles its click into the row's handler navigated to the client instead (measured:
          // #/ -> #/client/CASE-022, tick lost). A control must not look like it does something.
          showIndicators
          indicators={(r) => ({ violation: r.has_violation, warning: r.has_warning })}
          sort={sort}
          onSort={setSort}
          emptyText={t('dashboard.noClientsFound')}
          footer={
            // Only the valuation date. The data-quality counts and the contract notes were internal
            // QA output (dangling refs, absent source columns, how derived fields are computed) and
            // read as noise to an advisor preparing a call.
            data.data_as_of ? (
              <div className="dash-footer-meta">
                <span>{t('dashboard.dataAsOf', { date: formatDate(data.data_as_of) })}</span>
              </div>
            ) : undefined
          }
        />

        <Pagination
          page={safePage}
          pageCount={pageCount}
          onPageChange={setPage}
          pageSize={pageSize}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          onPageSizeChange={(size) => setPageSize(size)}
          total={sorted.length}
        />
      </div>
    </>
  );
}
