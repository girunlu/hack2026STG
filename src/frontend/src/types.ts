/**
 * API contract — mirrors `src/backend/app/api/schemas.py` and the projection dicts in
 * `src/backend/app/api/clients.py`. Change one side, change the other.
 *
 * Two conventions matter when formatting these values:
 *  - fields ending in `_pct` are already percentages (15.1538 means 15.15%)
 *  - `weight`, `target`, `min`, `max`, `actual`, `difference` are fractions (0.567 means 56.70%)
 */

export interface Advisor {
  name: string;
  initials: string;
}

export interface Money {
  currency: string;
  amount: number;
}

export interface Tab {
  id: string;
  label: string;
  count: number;
  hint?: string | null;
  supported: boolean;
}

export interface DanglingRef {
  client_ref: string;
  kind: 'violation' | 'proposal';
  portfolio_id: number;
  rule_code: string | null;
  severity: string | null;
  reason: string;
}

export interface IntegrityReport {
  dangling_portfolio_refs: DanglingRef[];
  clients_without_risk_profile: string[];
  portfolios_without_positions: string[];
  notes_total: number;
  notes_distinct: number;
  known_data_typos: string[];
  counts: Record<string, number>;
}

export interface ClientRow {
  ref: string;
  client_id: number | null;
  name: string;
  type: string | null;
  is_company: boolean;
  reporting_currency: string | null;
  aum: number;
  liquidity_pct: number | null;
  birthday: string | null;
  days_to_birthday: number | null;
  profiling_date: string | null;
  last_changed: string | null;
  last_consultation: string | null;
  last_consultation_basis: string;
  portfolio_count: number;
  external_portfolio_count: number;
  external_aum: number;
  violation_count: number;
  warning_count: number;
  has_violation: boolean;
  has_warning: boolean;
  has_maturities: boolean;
  street: string | null;
  zip: string | null;
  city: string | null;
  data_gaps: string[];
}

export interface ClientsResponse {
  advisor: Advisor;
  book_total: Money;
  data_as_of: string | null;
  counts: Record<string, number>;
  tabs: Tab[];
  rows: ClientRow[];
  integrity: IntegrityReport;
  notes: string[];
  lang?: string;
}

export interface RiskProfile {
  id: number;
  name: string;
  risk_level: number | null;
  max_vola: number | null;
  max_prc: number | null;
  equity_quote: number | null;
}

export interface ClientBlock {
  ref: string;
  client_id: number | null;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
  type: string | null;
  is_company: boolean;
  is_employee: boolean;
  reporting_currency: string | null;
  aum: number;
  liquidity: number;
  liquidity_pct: number | null;
  risk_profile: RiskProfile | null;
  risk_profile_id: number | null;
  esg_profile: string | null;
  birthday: string | null;
  profiling_date: string | null;
  last_changed: string | null;
  last_consultation: string | null;
  last_consultation_basis: string;
  street: string | null;
  zip: string | null;
  city: string | null;
  counts: Record<string, number>;
}

export interface PortfolioSummary {
  id: number | null;
  nr: string;
  name: string;
  currency: string | null;
  aum: number;
  volatility: number | null;
  expected_return: number | null;
  value_at_risk: number | null;
  service: string | null;
  strategy: string | null;
  saa_id: number | null;
  is_external: boolean;
  source: string;
  return_12m_pct: number | null;
  return_3m_pct: number | null;
  performance_as_of: string | null;
  top_weight: number | null;
  top_security: string | null;
  top_currency: string | null;
  position_count: number;
  data_gaps: string[];
}

export interface ProposalRow {
  id: number | null;
  portfolio_id: number;
  portfolio_nr: string | null;
  portfolio_name: string | null;
  portfolio_known: boolean;
  container: string;
  advisory_type: string;
  service: string | null;
  status: string;
  status_archived: boolean;
  status_allows_submit: boolean;
  reason: string | null;
  proposed_at: string | null;
  changed_at: string | null;
  changed_by: string | null;
  expected_return: number | null;
  volatility: number | null;
  security_count: number;
  can_delete: boolean;
  data_gaps: string[];
}

export interface ViolationValue {
  field: string;
  label: string;
  value: number;
  limit: number;
  unit: 'ratio' | 'value';
  source: string;
  path: string;
}

export interface Violation {
  id: number | null;
  rule_code: string;
  rule_description: string;
  severity: 'Error' | 'Warning' | string;
  error_level: number;
  portfolio_id: number;
  portfolio_nr: string | null;
  portfolio_known: boolean;
  explanation: { field: string; left: number; right: number; operator: number; label?: string; unit?: 'ratio' | 'value' }[];
  values: ViolationValue[];
}

export interface Note {
  index: number;
  text: string;
  date: string | null;
  duplicate_of: number | null;
  duplicate_count?: number;
  source: string;
  path: string;
}

export interface Tag {
  name: string;
  type: string;
  scope: string;
}

export interface Tags {
  region: Tag[];
  industry: Tag[];
  other: Tag[];
  all: Tag[];
}

export interface RuleOverride {
  rule_code: string;
  description: string;
  source: string;
  path: string;
}

export interface ClientDetailResponse {
  client: ClientBlock;
  portfolios: PortfolioSummary[];
  proposals: ProposalRow[];
  violations: Violation[];
  notes: Note[];
  tags: Tags;
  overrides: RuleOverride[];
  counts: Record<string, number>;
  data_gaps: string[];
  lang?: string;
}

export interface SaaRow {
  category: string;
  min: number | null;
  target: number;
  max: number | null;
  actual: number;
  difference: number;
}

export interface Saa {
  available: boolean;
  saa_id: number | null;
  saa_name: string | null;
  description: string | null;
  reason: string | null;
  rows: SaaRow[];
}

export interface PositionRow {
  kind: 'security' | 'account';
  position: string;
  security_id: number | null;
  kennung: string | null;
  valor: string | null;
  whg: string | null;
  prc: number | null;
  quantity: number | null;
  price: number | null;
  value: number;
  weight: number | null;
  risk_contribution: number | null;
  marginal_risk: number | null;
  sustainability_score: number | null;
  sustainability_rating: number | null;
  asset_class: string;
  group: string;
  is_fund: boolean;
  lookthrough_rows: number;
  has_price: boolean;
  cost_basis: null;
  success: null;
  rules: null;
}

export interface PositionGroup {
  category: string;
  value: number;
  weight: number;
  positions: number;
  expandable: boolean;
}

export interface ExposureRow {
  category: string;
  value: number;
  weight: number;
}

export type Dimension = 'asset_class' | 'currency' | 'country' | 'industry';

export type Exposures = Record<Dimension, { splitting_off: ExposureRow[]; splitting_on: ExposureRow[] }>;

export interface FxRow {
  currency: string;
  currency_group: string;
  value: number;
  weight: number;
}

export interface Fx {
  rows: FxRow[];
  total: number;
  portfolio_currency: string | null;
}

export interface PrcProfile {
  distribution: Record<string, number>;
  share_prc_ge_5: number | null;
  max_prc: number | null;
}

export interface Sustainability {
  score: number | null;
  scored_weight: number;
  positioned_weight: number;
  esg_profile: string | null;
}

export interface Maturity {
  as_of: string | null;
  classified_weight: number;
  buckets: ExposureRow[];
}

export type WidgetType = 'donut' | 'gauge' | 'scatter' | 'map' | 'bar' | 'line' | 'grid' | 'rows';

export interface Widget {
  id: string;
  title: string;
  type: WidgetType;
  value: number | string | null;
  sub: string | null;
  alert?: boolean;
  direction?: 'up' | 'down';
  rows?: { label: string; value: number }[];
  formula: string;
  value_label?: string;
  sub_label?: string;
}

export interface PortfolioDetailResponse {
  client: ClientBlock;
  portfolio: PortfolioSummary;
  saa: Saa;
  positions: PositionRow[];
  groups: PositionGroup[];
  total: {
    value: number;
    currency: string | null;
    positions: number;
    accounts: number;
    portfolio_aum: number;
  };
  exposures: Exposures;
  fx: Fx;
  prc: PrcProfile;
  sustainability: Sustainability;
  maturity: Maturity;
  metrics: Widget[];
  violations: Violation[];
  integrity: { portfolio_known: boolean; data_as_of: string | null; factory_date: string | null };
  data_gaps: string[];
  lang?: string;
}

export interface HealthResponse {
  status: string;
  data_as_of: string | null;
  counts: Record<string, number>;
  clients_without_risk_profile: string[];
  dangling_portfolio_refs: number;
  engine_version: string;
  /** Whether the optional LLM renderer can run — it decides which renderer a briefing asks for. */
  llm_available: boolean;
  llm_model: string | null;
}

/**
 * Market search (advisor tool) — response shape for ``GET /api/market/search``.
 * The endpoint degrades honestly: ``instrument.matched=false`` plus live news is a normal state,
 * and empty ``news.items`` with populated ``news.unavailable`` is also a success.
 */
export interface MarketInstrumentAlternative {
  security_id: number;
  name: string;
  isin: string | null;
  currency: string | null;
  security_type: string | null;
}

export interface MarketInstrument {
  matched: boolean;
  raw_query: string;
  security_id: number | null;
  name: string | null;
  display_name: string | null;
  isin: string | null;
  valor: string | null;
  security_type: string | null;
  currency: string | null;
  asset_class: string | null;
  asset_class_detailed: string | null;
  industry: string | null;
  country: string | null;
  country_group: string | null;
  price: number | null;
  price_date: string | null;
  volatility: number | null;
  sustainability_score: number | null;
  prc: number | null;
  bank_rating: string | null;
  in_recommendation_list: boolean;
  recommendation_lists: string[];
  share_class_count: number;
  alternatives: MarketInstrumentAlternative[];
}

export interface MarketNewsItem {
  headline: string;
  source: string | null;
  url: string | null;
  published: string | null;
}

export interface MarketNewsUnavailable {
  reason: string;
}

export interface MarketNews {
  query_used: string | null;
  providers_used: string[];
  items: MarketNewsItem[];
  unavailable: MarketNewsUnavailable[];
  notes: string[];
}

export interface MarketBankViewStance {
  dimension: string;
  category: string;
  stance: string;
  note: string | null;
}

export interface MarketBankView {
  source: string | null;
  source_url: string | null;
  as_of: string | null;
  mock: boolean;
  disclaimer: string | null;
  stances: MarketBankViewStance[];
}

export interface MarketHeldByRow {
  client_ref: string;
  client_name: string;
  portfolio_nr: string;
  weight: number;
  value: number;
  currency: string;
}

export interface MarketSignal {
  headline: string;
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed';
  materiality: 'high' | 'medium' | 'low';
  why: string;
}

/**
 * The model's reading of the headlines it was given. ``applied: false`` with a ``reason`` means no
 * signals exist — the UI must say so rather than show an empty list as if the news had none.
 */
export interface MarketSignals {
  applied: boolean;
  reason: string | null;
  model: string | null;
  items: MarketSignal[];
}

export interface MarketSearchResponse {
  query: string;
  query_kind: 'isin' | 'valor' | 'name' | null;
  as_of: string | null;
  instrument: MarketInstrument;
  news: MarketNews;
  signals: MarketSignals;
  bank_view: MarketBankView | null;
  held_by: MarketHeldByRow[];
  held_by_total: number;
  portfolio_weight: number | null;
  unavailable: string[];
}
