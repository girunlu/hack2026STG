# URO Advisor Pro — Data Models & Mock Data (v2, audit-corrected)

> TypeScript interfaces and mock data. v2: all row values re-verified against 3x zoomed crops of the screenshots.

---

## 1. Core Types

```typescript
interface Client {
  ClientId: number;
  ClientRef: string;              // e.g. "41839-29"
  FirstName: string;
  LastName: string;
  Company: string | null;
  IsClientACompany: boolean;
  RegulatoryClientTypeName: string;  // "Natürliche Person" | "Juristische Person"
  RiskProfileName: string;           // display: "Ausgeglichen"
  Birthday: string | null;           // ISO "1964-11-12"
  ProfilingDateUtc: string | null;   // ISO
  LastChangedDate: string | null;    // ISO
  LastConsultationDate: string | null; // ISO; null = blank cell
  AssetsUnderManagementInDefaultCurrency: number;
  hasRuleViolation: boolean;         // red ×-circle
  hasWarning: boolean;               // yellow !-triangle
  Portfolios: Portfolio[];
}

interface Portfolio {
  PortfolioNr: string;            // "15.02996" | "42.249999" | "ZKB"
  Name: string;                   // "Anlageberatung Portfolio"
  StrategyLabel: string;          // "Rendite" | "URO-Ausgewogen Standard" | "Keine Strategie"
  PortfolioCurrency: string;      // "CHF"
  AssetsUnderManagementInDefaultCurrency: number;
  suitabilityPercent: number;
  iconKind: "person" | "bank";
  hasWarning: boolean;
  StrategicAssetAllocation: SAAEntry[];
}

interface SAAEntry {
  category: string;   // "Liqu. / Geldmarkt" | "Obligationen" | "Aktien" | "Immobilien" | "Übrige Anlagen"
  color: string;      // bar fill color
  min: number; soll: number; max: number; portfolio: number; aktion: number; // percent
}

interface Beratung {
  id: string;
  anlageDienstleistung: string;
  container: string;              // "27131"
  beratungsart: string;           // "Anlagevorschlag" | "Depotbesprechung" | "Telefonberatung"
  beratungLabel: string;          // "Beratung vom 10.09.2026"
  nr: string;                     // "20260910-349514351-281"
  status: "Vorgeschlagen" | "Entwurf";   // both rendered as plain dark text
  geaendertDurch: string;         // "Hans Muster"
  letzteAenderung: string;        // "10.09.2026"
  hasRuleViolation: boolean;
  hasWarning: boolean;
  hasTrash: boolean;              // trash icon present only on some rows
}

interface PositionRow {
  kind: "total" | "group" | "item";
  label: string;
  wertCHF: number | null;
  aktion: string | null;          // "→ 3.63%" green, else null
  pw: string | null;              // "1.55%"
}

interface FilterTab { id: string; label: string; count: number; active?: boolean; }

interface MetricWidget {
  id: string; title: string;
  type: "donut" | "gauge" | "bar" | "line" | "scatter" | "map" | "grid" | "icons" | "target";
  value?: string; sub?: string; isAlert?: boolean;
}
```

---

## 2. Screen 1 — Dashboard

```typescript
const dashboardSummary = {
  greeting: "Willkommen zurück, Hans Muster",
  stats: [
    { label: "Pendente Beratungen", value: "215" },
    { label: "Restriktionen",       value: null },   // NO value in screenshot
    { label: "Warnungen",           value: "21" },
  ],
  totalVermoegen: 52618933.52,   // CHF 52'618'933.52
};

const navScreen1 = [
  { icon: "briefcase",  label: "Beratermappe" },
  { icon: "users",      label: "Kundenliste", active: true },
  { icon: "ban",        label: "Regelverletzungen", badge: 114, badgeColor: "red" },
  { icon: "triangle",   label: "Warnungen", badge: 21, badgeColor: "red" },
];

const filterTabs: FilterTab[] = [
  { id: "kunden",     label: "Kunden",                             count: 45,  active: true },
  { id: "neukunden",  label: "Neukunden",                          count: 6 },
  { id: "beratungen", label: "Beratungen",                         count: 215 },
  { id: "liq10",      label: "01 - Liquidity > 10%",               count: 112 },
  { id: "maturities", label: "02 - Maturities",                    count: 0 },
  { id: "consult12m", label: "03 - Last Consultation > 12 Months", count: 191 },
  { id: "violations", label: "04 - Rule Violations (urgent)",      count: 28 },
  { id: "birthdays",  label: "05 - Birthdays",                     count: 13 },
  { id: "neu1",       label: "Neu",                                count: 146 },
  { id: "neu2",       label: "Neu",                                count: 146 },
  { id: "testsuche",  label: "Testsuche",                          count: 5 },
  { id: "neu3",       label: "Neu",                                count: 146 },
  { id: "neu4",       label: "Neu",                                count: 146 },
];

// Exact rows as shown (page 1). Indicators: R = red ×-circle, Y = yellow !-triangle.
const dashboardClients: Client[] = [
  { ClientId: 1,  ClientRef: "67123-42",  FirstName: "Phillipp",  LastName: "Abend",       Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1964-11-12", ProfilingDateUtc: "2024-04-19", LastChangedDate: "2026-08-24", LastConsultationDate: "2026-08-24", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: false, hasWarning: false, Portfolios: [] },
  { ClientId: 2,  ClientRef: "209692-80", FirstName: "Mandy",     LastName: "Baer",        Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1993-01-04", ProfilingDateUtc: "2020-10-27", LastChangedDate: "2026-08-14", LastConsultationDate: "2026-08-14", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: true,  hasWarning: true,  Portfolios: [] },
  { ClientId: 3,  ClientRef: "215129-14", FirstName: "Lucas",     LastName: "Bauer",       Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1988-08-14", ProfilingDateUtc: "2026-05-08", LastChangedDate: "2026-08-19", LastConsultationDate: "2026-08-19", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: true,  hasWarning: true,  Portfolios: [] },
  { ClientId: 4,  ClientRef: "41839-29",  FirstName: "Tanja",     LastName: "Bauer",       Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1936-02-22", ProfilingDateUtc: "2026-08-25", LastChangedDate: "2026-09-10", LastConsultationDate: "2026-09-10", AssetsUnderManagementInDefaultCurrency: 1497989.49, hasRuleViolation: true, hasWarning: true, Portfolios: [] },
  { ClientId: 5,  ClientRef: "176264-82", FirstName: "Bauer",     LastName: "AG",          Company: "Bauer AG", IsClientACompany: true, RegulatoryClientTypeName: "Juristische Person", RiskProfileName: "Ausgeglichen", Birthday: "1978-02-25", ProfilingDateUtc: "2024-06-21", LastChangedDate: "2024-06-21", LastConsultationDate: null,        AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: false, hasWarning: false, Portfolios: [] },
  { ClientId: 6,  ClientRef: "29341-61",  FirstName: "Christian", LastName: "Bergmann",    Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1989-06-24", ProfilingDateUtc: "2024-04-23", LastChangedDate: "2025-06-30", LastConsultationDate: "2024-04-23", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: true,  hasWarning: false, Portfolios: [] },
  { ClientId: 7,  ClientRef: "236075-29", FirstName: "Tom",       LastName: "Biermann",    Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1976-08-13", ProfilingDateUtc: "2024-07-17", LastChangedDate: "2025-07-07", LastConsultationDate: "2025-07-07", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: true,  hasWarning: true,  Portfolios: [] },
  { ClientId: 8,  ClientRef: "15103-68",  FirstName: "Ulrike",    LastName: "Bohm",        Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1934-06-03", ProfilingDateUtc: "2020-06-23", LastChangedDate: "2025-07-03", LastConsultationDate: null,        AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: false, hasWarning: true,  Portfolios: [] },
  { ClientId: 9,  ClientRef: "53143-87",  FirstName: "Stephanie", LastName: "Drescher",    Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1967-07-10", ProfilingDateUtc: "2026-07-17", LastChangedDate: "2026-07-17", LastConsultationDate: "2026-07-17", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: false, hasWarning: false, Portfolios: [] },
  { ClientId: 10, ClientRef: "127929-74", FirstName: "Karolin",   LastName: "Ebersbacher", Company: null,     IsClientACompany: false, RegulatoryClientTypeName: "Natürliche Person",  RiskProfileName: "Ausgeglichen", Birthday: "1960-12-08", ProfilingDateUtc: "2024-11-01", LastChangedDate: "2024-12-20", LastConsultationDate: "2024-12-20", AssetsUnderManagementInDefaultCurrency: 0, hasRuleViolation: false, hasWarning: false, Portfolios: [] },
];

const dashboardPagination = { prevLabel: "« Vorherige", pages: [1, 2, 3, 4, 5], current: 1, nextLabel: "Nächste »" };
```

---

## 3. Screen 2 — Client Detail (Tanja Bauer)

```typescript
const navScreen2 = [
  { icon: "briefcase", label: "Beratermappe" },
  { icon: "note",      label: "Notizen", badge: 0, badgeColor: "gray" },
  { icon: "pie",       label: "Vermögen", active: true },
  { icon: "ban",       label: "Regelverletzungen", badge: 4, badgeColor: "red" },
  { icon: "usercircle",label: "Kundeninformation" },
  { icon: "arrowleft" }, { icon: "menu" },
];

const clientMeta = {
  name: "Tanja Bauer (41839-29)",
  total: 1497989.49,   // CHF 1'497'989.49
  pairs: [
    { label: "Kundentyp",    value: "Natürliche Person" },
    { label: "Kundenprofil", value: "Ausgeglichen" },
  ],
};

const portfolioFilterButtons = [
  { label: "Alle Portfolios",  active: true,  warning: true },
  { label: "Eigene Portfolios", active: false, warning: true },
  { label: "Fremdbanken",       active: false, warning: true },
  { label: "Konsolidierung",    active: false, warning: false },
  { label: "Beziehungen",       active: false, warning: false },
];

const tanjaPortfolios: Portfolio[] = [
  { PortfolioNr: "15.02996",  Name: "Anlageberatung Portfolio", StrategyLabel: "Rendite",                 PortfolioCurrency: "CHF", AssetsUnderManagementInDefaultCurrency: 456457,   suitabilityPercent: 12, iconKind: "person", hasWarning: true,  StrategicAssetAllocation: [/* see Screen 3 */] },
  { PortfolioNr: "42.249999", Name: "Verwaltungsdepot",         StrategyLabel: "URO-Ausgewogen Standard", PortfolioCurrency: "CHF", AssetsUnderManagementInDefaultCurrency: 1041533,  suitabilityPercent: 8,  iconKind: "person", hasWarning: false, StrategicAssetAllocation: [] },
  { PortfolioNr: "ZKB",       Name: "Anlageberatung Fokus",     StrategyLabel: "Keine Strategie",         PortfolioCurrency: "CHF", AssetsUnderManagementInDefaultCurrency: 951,      suitabilityPercent: 17, iconKind: "bank",   hasWarning: false, StrategicAssetAllocation: [] },
];
// Card title line renders as `${Name} | ${StrategyLabel} (CHF)`
// Carousel: 2 dots, first active.

const beratungen: Beratung[] = [
  { id: "b1",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Anlagevorschlag",  beratungLabel: "Beratung vom 10.09.2026",           nr: "20260910-349514351-281", status: "Vorgeschlagen", geaendertDurch: "Hans Muster", letzteAenderung: "10.09.2026", hasRuleViolation: false, hasWarning: false, hasTrash: false },
  { id: "b2",  anlageDienstleistung: "Verwaltungsdepot",         container: "27131", beratungsart: "Anlagevorschlag",  beratungLabel: "Beratung vom 26.08.2026",           nr: "20260826-349514351-280", status: "Vorgeschlagen", geaendertDurch: "Hans Muster", letzteAenderung: "26.08.2026", hasRuleViolation: false, hasWarning: false, hasTrash: false },
  { id: "b3",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Depotbesprechung", beratungLabel: "Beratung vom 26.08.2026",           nr: "20260826-349514351-279", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "26.08.2026", hasRuleViolation: false, hasWarning: true,  hasTrash: true },
  { id: "b4",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Depotbesprechung", beratungLabel: "Beratung vom 26.08.2026",           nr: "20260826-349514351-278", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "26.08.2026", hasRuleViolation: false, hasWarning: true,  hasTrash: true },
  { id: "b5",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Telefonberatung",  beratungLabel: "Beratung vom 26.08.2026",           nr: "20260826-349514351-277", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "26.08.2026", hasRuleViolation: false, hasWarning: true,  hasTrash: true },
  { id: "b6",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Telefonberatung",  beratungLabel: "Beratung vom 26.08.2026",           nr: "20260826-349514351-276", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "26.08.2026", hasRuleViolation: true,  hasWarning: true,  hasTrash: false },
  { id: "b7",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Anlagevorschlag",  beratungLabel: "Beratung vom 26.08.2026",           nr: "20260826-349514351-275", status: "Vorgeschlagen", geaendertDurch: "Hans Muster", letzteAenderung: "26.08.2026", hasRuleViolation: false, hasWarning: true,  hasTrash: false },
  { id: "b8",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Depotbesprechung", beratungLabel: "Beratung vom 25.08.2026",           nr: "20260825-349514351-273", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "25.08.2026", hasRuleViolation: false, hasWarning: true,  hasTrash: true },
  { id: "b9",  anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Depotbesprechung", beratungLabel: "Beratung vom 25.08.2026",           nr: "20260825-349514351-272", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "25.08.2026", hasRuleViolation: true,  hasWarning: true,  hasTrash: true },
  { id: "b10", anlageDienstleistung: "Anlageberatung Portfolio", container: "27131", beratungsart: "Anlagevorschlag",  beratungLabel: "Kopie von Beratung vom 25.08.2026", nr: "20260825-349514351-271", status: "Entwurf",       geaendertDurch: "Hans Muster", letzteAenderung: "25.08.2026", hasRuleViolation: false, hasWarning: true,  hasTrash: true },
];

const clientPagination = { prevLabel: "« Vorherige", pages: [1, 2, 3, 4, 5, "…", 16], current: 1, nextLabel: "Nächste »" };
```

---

## 4. Screen 3 — Portfolio Analyse

```typescript
const navScreen3 = [
  { icon: "phone",      label: "Telefonberatung" },
  { icon: "briefcase",  label: "Beratermappe" },
  { icon: "note",       label: "Notizen", badge: 0, badgeColor: "gray" },
  { icon: "pie",        label: "Analyse", active: true },
  { icon: "usercircle", label: "Kundeninformation" },
  { icon: "info",       label: "Portfolio" },
  { icon: "arrowleft" }, { icon: "menu" },
];

const portfolioMeta = {
  clientName: "Tanja Bauer (41839-29)",
  total: 456456.98,   // CHF 456'456.98
  pairs: [   // STATIC label/value pairs — NOT tabs
    { label: "Portfolio",             value: "15.02996" },
    { label: "Anlagedienstleistung",  value: "Anlageberatung Portfolio" },
    { label: "Strategie",             value: "Rendite" },
  ],
};

const saaDescription =
  "Die Strategische Asset Allokation zeigt die Aufteilung des Portfolios nach Anlagekategoriegruppen und " +
  "Anlagekategorien. Die Zielwerte werden dabei durch die vereinbarte Anlagestrategie definiert, welche eine " +
  "dem Risiko der Strategie entsprechende Diversifikation festlegt. Um eine möglichst detaillierte " +
  "Branchenallokation darzustellen, …";   // tail truncated in screenshot; complete plausibly in German
// Then inline: <strong>Anlagetipp:</strong> followed by regular text on the same line (no box).

const saaEntries: SAAEntry[] = [
  { category: "Liqu. / Geldmarkt", color: "#4A90D9", min: 0.0,  soll: 5.0,  max: 15.0, portfolio: 1.5,  aktion: 3.5 },
  { category: "Obligationen",      color: "#4A90D9", min: 35.0, soll: 45.0, max: 55.0, portfolio: 16.5, aktion: 28.5 },
  { category: "Aktien",            color: "#45B4E6", min: 15.0, soll: 25.0, max: 35.0, portfolio: 59.1, aktion: -34.1 },
  { category: "Immobilien",        color: "#45D0C5", min: 0.0,  soll: 7.5,  max: 17.5, portfolio: 4.9,  aktion: 2.6 },
  { category: "Übrige Anlagen",    color: "#57D9A3", min: 7.5,  soll: 17.5, max: 27.5, portfolio: 18.0, aktion: -0.5 },
];
// Bar under each row: track = full-width light gray (#C9CED6); fill width ≈ portfolio% / 60% (Aktien ≈ full).
// Negative aktion values render as plain dark text (NOT red).

const donutCenter = { line1: "456.5T", line2: "CHF" };

const sidebarMetrics: MetricWidget[] = [
  { id: "saa",            title: "SAA",            type: "donut",   isAlert: true },
  { id: "suitability",    title: "Suitability",    type: "gauge",   value: "12%" },
  { id: "riskReturn",     title: "Risiko / Rendite", type: "scatter", value: "12%", sub: "4.3%" },
  { id: "scenarios",      title: "Szenarien",      type: "bar",     value: "-30.5%", sub: "Globale Finanzkrise" },
  { id: "productRisk",    title: "Product Risk",   type: "donut",   value: "57.3%", sub: "PRC-L" },
  { id: "countries",      title: "Länder",         type: "map",     value: "65.4%", sub: "Nordamerika" },
  { id: "industries",     title: "Branchen",       type: "donut",   value: "20%",  sub: "Zyklischer Konsum" },
  { id: "currencies",     title: "Währungen",      type: "donut",   value: "44%",  sub: "US-Dollar (USD)" },
  { id: "maturities",     title: "Fälligkeiten",   type: "bar",     value: "100%", sub: "Nicht klassifiziert" },
  { id: "restrictions",   title: "Restriktionen",  type: "icons",   value: "1", sub: "5 / 0" },
  { id: "performance",    title: "Performance",    type: "line",    value: "13.1%" },
  { id: "sustainability", title: "Nachhaltigkeit", type: "donut",   value: "Nachhaltig", sub: "0 ESG-Rating" },
  { id: "goalAchieve",    title: "Zielerreichung", type: "target" },
  { id: "issuerRisk",     title: "Emittentenrisiko", type: "donut", value: "100%", sub: "Ausgeschlossen" },
  { id: "positions",      title: "Positionsliste", type: "grid",    value: "13 Positionen" },
];

const positionsSplitButton = "Fondssplitting deaktivieren";   // solid blue, ONE word "Fondssplitting"

const positionRows: PositionRow[] = [
  { kind: "total", label: "Total",             wertCHF: 456456.98, aktion: null,       pw: null },
  { kind: "group", label: "Liqu. / Geldmarkt", wertCHF: 7058.13,   aktion: "→ 3.63%",  pw: "1.55%" },
  { kind: "item",  label: "Liquide Mittel",    wertCHF: 7058.13,   aktion: null,       pw: "1.55%" },
  // … continue to 13 positions total (screenshot cuts off here)
];
```

---

## 5. Number Formatting

```typescript
function formatCHF(value: number): string {
  const [int, dec] = value.toFixed(2).split(".");
  return `CHF ${int.replace(/\B(?=(\d{3})+(?!\d))/g, "'")}.${dec}`;
}
// 52618933.52 → "CHF 52'618'933.52"

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
}
```

---

## 6. Navigation State

```typescript
type Screen = "dashboard" | "client" | "portfolio";

interface AppState {
  currentScreen: Screen;
  selectedClientId: number | null;
  selectedPortfolioNr: string | null;
  activeFilterTab: string;        // dashboard tab id
  activePortfolioButton: string;  // "Alle Portfolios" | …
  tablePage: number;
  tablePageSize: number;
  searchQuery: string;
}
// Dashboard → Client: click Name link. Client → Portfolio: click card. Back: ← arrow in nav.
```
