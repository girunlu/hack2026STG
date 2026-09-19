import { useCallback, useEffect, useState } from 'react';

import { api } from './api/client';
import Header from './components/Header';
import SecondaryNav from './components/SecondaryNav';
import type { NavItem } from './components/types';
import BriefingScreen from './screens/briefing/BriefingScreen';
import ClientScreen from './screens/client/ClientScreen';
import CreativeBriefing from './screens/creative/CreativeBriefing';
import DashboardScreen from './screens/dashboard/DashboardScreen';
import FremdbankenPanel from './screens/fremdbanken/FremdbankenPanel';
import MarketSearchPanel from './screens/market/MarketSearchPanel';
import PortfolioScreen from './screens/portfolio/PortfolioScreen';
import { useI18n, useT } from './i18n';
import { ShellProvider, useShellBadgeValues, useShellBadges } from './shell/ShellContext';
import { clientNav, dashboardNav, portfolioNav } from './shell/nav';

/**
 * F1 — the mocked URO Advisor Pro shell and its routing.
 *
 * Screens own their own data fetching and their own meta band; the shell owns the header, the
 * navigation, the route state and the presentation switch between the briefing view and the printable
 * one-pager. Every screen navigates through these callbacks — there is exactly one routing convention.
 */

type Panel = 'briefing' | 'creative';

type Route =
  | { name: 'dashboard'; tab?: string }
  | { name: 'client'; clientRef: string }
  | { name: 'portfolio'; clientRef: string; portfolioNr: string }
  | { name: 'fremdbanken'; clientRef: string }
  | { name: 'briefing'; clientRef: string; portfolioNr: string | null }
  | { name: 'creative'; clientRef: string; portfolioNr: string | null }
  | { name: 'market'; query: string | null };

/** Route → URL fragment. Keeps the address bar in step so refresh, back/forward and sharing work. */
function routeToHash(route: Route): string {
  switch (route.name) {
    case 'dashboard':
      return route.tab ? `#/?tab=${encodeURIComponent(route.tab)}` : '#/';
    case 'client':
      return `#/client/${encodeURIComponent(route.clientRef)}`;
    case 'portfolio':
      return `#/client/${encodeURIComponent(route.clientRef)}/portfolio/${encodeURIComponent(route.portfolioNr)}`;
    case 'fremdbanken':
      return `#/client/${encodeURIComponent(route.clientRef)}/fremdbanken`;
    case 'briefing': {
      const base = `#/client/${encodeURIComponent(route.clientRef)}/briefing`;
      return route.portfolioNr ? `${base}?portfolio=${encodeURIComponent(route.portfolioNr)}` : base;
    }
    case 'creative': {
      const base = `#/client/${encodeURIComponent(route.clientRef)}/creative`;
      return route.portfolioNr ? `${base}?portfolio=${encodeURIComponent(route.portfolioNr)}` : base;
    }
    case 'market':
      return route.query ? `#/market?q=${encodeURIComponent(route.query)}` : '#/market';
  }
}

/** URL fragment → route. Anything unrecognised falls back to the dashboard. */
function hashToRoute(hash: string): Route {
  const [path, query] = hash.replace(/^#\/?/, '').split('?');
  const parts = path.split('/').filter(Boolean);
  const params = new URLSearchParams(query ?? '');
  const portfolioNr = params.get('portfolio');

  // Market search route
  if (parts[0] === 'market') {
    return { name: 'market', query: params.get('q') };
  }

  if (parts[0] !== 'client' || !parts[1]) {
    return { name: 'dashboard', tab: params.get('tab') ?? undefined };
  }
  const clientRef = decodeURIComponent(parts[1]);
  switch (parts[2]) {
    case undefined:
      return { name: 'client', clientRef };
    case 'portfolio':
      return parts[3]
        ? { name: 'portfolio', clientRef, portfolioNr: decodeURIComponent(parts[3]) }
        : { name: 'client', clientRef };
    case 'fremdbanken':
      return { name: 'fremdbanken', clientRef };
    case 'briefing':
      return { name: 'briefing', clientRef, portfolioNr };
    case 'creative':
      return { name: 'creative', clientRef, portfolioNr };
    default:
      return { name: 'client', clientRef };
  }
}

export default function App() {
  const { lang } = useI18n();
  // Initialise from the URL, so a deep link or a refresh lands where the advisor left off.
  const [route, setRoute] = useState<Route>(() => hashToRoute(window.location.hash));

  // Keep the address bar in step with the route. pushState (not a hash write) so we do not
  // re-enter our own hashchange listener and loop.
  useEffect(() => {
    const want = routeToHash(route);
    if (window.location.hash !== want) {
      window.history.pushState(null, '', want);
    }
  }, [route]);

  // Back/forward, and a manually edited URL.
  useEffect(() => {
    const sync = () => setRoute(hashToRoute(window.location.hash));
    window.addEventListener('popstate', sync);
    window.addEventListener('hashchange', sync);
    return () => {
      window.removeEventListener('popstate', sync);
      window.removeEventListener('hashchange', sync);
    };
  }, []);

  const openClient = useCallback((clientRef: string) => setRoute({ name: 'client', clientRef }), []);
  const openPortfolio = useCallback(
    (clientRef: string, portfolioNr: string) => setRoute({ name: 'portfolio', clientRef, portfolioNr }),
    [],
  );
  const openFremdbanken = useCallback(
    (clientRef: string) => setRoute({ name: 'fremdbanken', clientRef }),
    [],
  );
  const openPanel = useCallback(
    (panel: Panel, clientRef: string, portfolioNr: string | null) =>
      setRoute(
        panel === 'briefing'
          ? { name: 'briefing', clientRef, portfolioNr }
          : { name: 'creative', clientRef, portfolioNr },
      ),
    [],
  );
  const openBriefing = useCallback(
    (clientRef: string, portfolioNr: string | null) => openPanel('briefing', clientRef, portfolioNr),
    [openPanel],
  );
  const backToDashboard = useCallback(() => setRoute({ name: 'dashboard' }), []);
  const openDashboardTab = useCallback((tab?: string) => setRoute({ name: 'dashboard', tab }), []);
  // A nav item on another screen may point at a client-section: remember the target so the
  // client screen can scroll to it once its data has landed.
  const [pendingScroll, setPendingScroll] = useState<string | null>(null);
  const openClientScroll = useCallback((clientRef: string, section: string) => {
    setPendingScroll(section);
    setRoute({ name: 'client', clientRef });
  }, []);
  useEffect(() => {
    if (route.name !== 'client') setPendingScroll(null);
  }, [route]);

  // The language is part of the key: switching it remounts the screens, so every fetch that
  // returned language-dependent content (tab labels, findings, briefing prose) is re-issued
  // instead of leaving stale text on screen until a manual refresh.
  const routeKey =
    (route.name === 'dashboard'
      ? 'dashboard'
      : route.name === 'market'
        ? `market:${route.query ?? ''}`
        : route.name === 'client' || route.name === 'fremdbanken'
          ? `${route.name}:${route.clientRef}`
          : `${route.name}:${route.clientRef}:${route.portfolioNr ?? ''}`) + `:${lang}`;

  return (
    <ShellProvider key={routeKey}>
      <Shell
        route={route}
        openClient={openClient}
        openPortfolio={openPortfolio}
        openFremdbanken={openFremdbanken}
        openBriefing={openBriefing}
        openPanel={openPanel}
        backToDashboard={backToDashboard}
        openDashboardTab={openDashboardTab}
        openClientScroll={openClientScroll}
        pendingScroll={pendingScroll}
        setRoute={setRoute}
      />
    </ShellProvider>
  );
}

function Shell({
  route,
  openClient,
  openPortfolio,
  openFremdbanken,
  openBriefing,
  openPanel,
  backToDashboard,
  openDashboardTab,
  openClientScroll,
  pendingScroll,
  setRoute,
}: {
  route: Route;
  openClient: (clientRef: string) => void;
  openPortfolio: (clientRef: string, portfolioNr: string) => void;
  openFremdbanken: (clientRef: string) => void;
  openBriefing: (clientRef: string, portfolioNr: string | null) => void;
  openPanel: (panel: Panel, clientRef: string, portfolioNr: string | null) => void;
  backToDashboard: () => void;
  openDashboardTab: (tab?: string) => void;
  openClientScroll: (clientRef: string, section: string) => void;
  pendingScroll: string | null;
  setRoute: (route: Route) => void;
}) {
  const badges = useShellBadgeValues();
  const t = useT();

  const items: NavItem[] =
    route.name === 'dashboard' || route.name === 'market'
      ? dashboardNav(t)
      : route.name === 'portfolio'
        ? portfolioNav(t)
        : clientNav(t);
  const active =
    route.name === 'dashboard' || route.name === 'market'
      ? 'kundenliste'
      : route.name === 'portfolio'
        ? 'analyse'
        : route.name === 'briefing' || route.name === 'creative'
          ? 'kundeninformation'
          : 'vermoegen';
  const title =
    route.name === 'dashboard'
      ? t('dashboard.title')
      : route.name === 'market'
        ? t('market.title')
        : route.name === 'portfolio'
          ? route.portfolioNr
          : route.name === 'fremdbanken'
            ? `${t('fremdbanken.title')} — ${route.clientRef}`
            : route.clientRef;

  const goBack =
    route.name === 'dashboard' || route.name === 'market'
      ? undefined
      : route.name === 'client' || route.name === 'fremdbanken'
        ? backToDashboard
        : route.name === 'portfolio'
          ? () => openClient(route.clientRef)
          : () => openClient(route.clientRef);

  const itemsWithBadges: NavItem[] = items.map((item) => ({
    ...item,
    badge: badges[item.id] ?? item.badge ?? null,
  }));

  // The mocked URO chrome navigates: every nav item maps to a real destination in the
  // prototype — a dashboard filter tab, a section of the current screen, or another route.
  const sectionFor: Record<string, string> = {
    notizen: 'client-notes',
    vermoegen: 'client-portfolios',
    regelverletzungen: 'client-violations',
    kundeninformation: 'client-top',
  };
  const navigate = (id: string) => {
    if (route.name === 'dashboard') {
      if (id === 'regelverletzungen') openDashboardTab('rule_violations');
      else if (id === 'warnungen') openDashboardTab('warnings');
      else openDashboardTab('kunden');
      return;
    }
    if (id === 'beratermappe' || id === 'kundenliste') {
      openDashboardTab('kunden');
      return;
    }
    if (id === 'warnungen') {
      openDashboardTab('warnings');
      return;
    }
    if (route.name === 'portfolio') {
      if (id === 'analyse') {
        document.getElementById('portfolio-saa')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      if (id === 'portfolio') {
        document.getElementById('portfolio-positions')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
    }
    const section = sectionFor[id];
    if (!section) return;
    if (route.name === 'client') {
      document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (route.name !== 'market') {
      openClientScroll(route.clientRef, section);
    }
  };

  return (
    <>
      <Header />
      <SecondaryNav
        items={itemsWithBadges}
        active={active}
        title={title}
        showBack={goBack !== undefined}
        onBack={goBack}
        onNavigate={navigate}
      />
      {(route.name === 'client' || route.name === 'portfolio' || route.name === 'fremdbanken' || route.name === 'briefing' || route.name === 'creative') && (
        <ClientBadges clientRef={route.clientRef} />
      )}
      {route.name === 'dashboard' && <DashboardScreen onOpenClient={openClient} tab={route.tab} onTabChange={openDashboardTab} />}
      {route.name === 'client' && (
        <ClientScreen
          clientRef={route.clientRef}
          onOpenPortfolio={(portfolioNr) => openPortfolio(route.clientRef, portfolioNr)}
          onOpenFremdbanken={() => openFremdbanken(route.clientRef)}
          onBriefing={(portfolioNr) => openBriefing(route.clientRef, portfolioNr ?? null)}
          initialScroll={pendingScroll}
        />
      )}
      {route.name === 'portfolio' && (
        <PortfolioScreen
          clientRef={route.clientRef}
          portfolioNr={route.portfolioNr}
          onBack={() => openClient(route.clientRef)}
          onBriefing={(portfolioNr) => openBriefing(route.clientRef, portfolioNr)}
        />
      )}
      {route.name === 'fremdbanken' && (
        <FremdbankenPanel clientRef={route.clientRef} onBack={() => openClient(route.clientRef)} />
      )}
      {(route.name === 'briefing' || route.name === 'creative') && (
        <PanelSwitch
          active={route.name}
          onChange={(panel) => openPanel(panel, route.clientRef, route.portfolioNr)}
        />
      )}
      {route.name === 'briefing' && (
        <BriefingScreen
          clientRef={route.clientRef}
          portfolioNr={route.portfolioNr}
          onBack={() => openClient(route.clientRef)}
          onOpenMarket={(isin) => setRoute({ name: 'market', query: isin })}
        />
      )}
      {route.name === 'creative' && (
        <CreativeBriefing
          clientRef={route.clientRef}
          portfolioNr={route.portfolioNr}
          onBack={() => openClient(route.clientRef)}
          onPrint={() => window.print()}
          onOpenMarket={(isin) => setRoute({ name: 'market', query: isin })}
        />
      )}
      {route.name === 'market' && (
        <MarketSearchPanel
          query={route.query}
          onSearch={(q) => setRoute({ name: 'market', query: q })}
        />
      )}
    </>
  );
}
/**
 * Publishes client-scoped badge counts (notes and violations) to the shell navigation.
 * Fetches client data for any route that belongs to a specific client.
 */
function ClientBadges({ clientRef }: { clientRef: string }) {
  const { lang } = useI18n();
  const [data, setData] = useState<{ distinct_notes: number; violations: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.client(clientRef, lang).then((response) => {
      if (cancelled) return;
      setData({
        distinct_notes: response.counts?.distinct_notes ?? 0,
        violations: response.violations?.length ?? 0,
      });
    }).catch(() => {
      if (cancelled) return;
      setData(null);
    });
    return () => {
      cancelled = true;
    };
  }, [clientRef, lang]);

  useShellBadges({
    notizen: data?.distinct_notes ?? null,
    regelverletzungen: data?.violations ?? null,
  });

  return null;
}

/**
 * Switches between the briefing (R6) and the printable one-pager (B3). Both render the same payload,
 * so this is a presentation choice the advisor makes, not a different request.
 */
function PanelSwitch({
  active,
  onChange,
}: {
  active: Panel;
  onChange: (panel: Panel) => void;
}) {
  const t = useT();
  const options: { panel: Panel; label: string }[] = [
    { panel: 'briefing', label: t('panel.briefing') },
    { panel: 'creative', label: t('panel.creative') },
  ];
  return (
    <div className="screen" style={{ paddingBottom: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <span className="muted" style={{ fontSize: 'var(--fs-cell)' }}>
          {t('panel.presentation')}
        </span>
        {options.map((option) => (
          <button
            key={option.panel}
            type="button"
            onClick={() => onChange(option.panel)}
            style={{
              padding: '2px 10px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              fontSize: 'var(--fs-cell)',
              background: active === option.panel ? 'var(--primary)' : 'var(--bg-btn-inactive)',
              color: active === option.panel ? 'var(--bg-card)' : 'var(--text-primary)',
            }}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
