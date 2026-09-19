/**
 * Local types for the briefing screen. These mirror the backend's response shape
 * (`POST /api/briefing`, `POST /api/qa`) without polluting the shared `types.ts`,
 * which is owned by the F2/F3/F4 contract.
 */

export type Severity = 'high' | 'medium' | 'low' | null;
export type SourceKind = 'portfolio' | 'external' | 'mock' | 'gap';

export interface BriefingClientQuestion {
  question: string;
  evidence_refs: string[];
}

export interface BriefingBlock {
  text: string;
  evidence_refs: string[];
  severity: Severity;
  source_kind: SourceKind;
  /**
   * Set when the block is about one instrument, so its market results can be opened from here.
   * Absent on blocks about the portfolio, a currency or a rule.
   */
  security_id?: number | null;
  isin?: string | null;
}

export interface BriefingSection {
  id: 'recent_development' | 'health_check' | 'outlook_actions';
  title: string;
  blocks: BriefingBlock[];
}

export interface BriefingQuestions {
  what_happened: string;
  situation: string;
  next: string;
  should_do: string;
  evidence_refs: string[];
  what_happened_refs: string[];
  situation_refs: string[];
  next_refs: string[];
  should_do_refs: string[];
}

export interface EvidenceIndexEntry {
  label: string;
  value: number | string | null;
  value_text: string | null;
  source: string;
  path: string;
}

export type EvidenceIndex = Record<string, EvidenceIndexEntry>;

export interface BriefingGeneratedFrom {
  data_as_of: string;
  engine_version: string;
  finding_count: number;
}

export interface Briefing {
  client_ref: string;
  client_name: string;
  renderer: 'template';
  sections: BriefingSection[];
  questions: BriefingQuestions;
  client_questions: BriefingClientQuestion[];
  evidence_index: EvidenceIndex;
  word_count: number;
  read_seconds_estimate: number;
  trimmed_blocks: Record<string, number>;
  generated_from: BriefingGeneratedFrom;
}

/* ---------- Facts (subset needed for provenance + actions + gaps) ---------- */

export interface FactsPortfolio {
  id: number;
  nr: string;
  name: string;
  currency: string;
  aum: number;
  data_gaps: string[];
  [key: string]: unknown;
}

export interface FactsAction {
  id: string;
  priority: number;
  action: string;
  rationale: string;
  finding_refs: string[];
  evidence: { label: string; value: number | string | null; source?: string; path?: string }[];
}

export interface FactsMeta {
  generated_at: string;
  data_as_of: string;
  unavailable: string[];
  engine_version: string;
  scope: { client_ref: string; portfolio_nr: string | null };
  stages: PipelineStage[];
}

export interface FactsMarketMeta {
  providers_used: string[];
  fetched_at: string | null;
  unavailable_items: { name: string; isin?: string | null; reason: string }[];
  queried: boolean;
  is_mock: boolean;
}

export interface FactsHouseView {
  source: string;
  source_url: string;
  as_of: string;
  mock: boolean;
  disclaimer: string;
  stances: unknown[];
  matches: unknown[];
}

export interface InstrumentCandidateEvidence {
  label: string;
  value: number | string | null;
  source: string;
  path: string;
  unit: string | null;
}

export interface InstrumentCandidateMove {
  direction: 'buy' | 'sell';
  reason_code: string;
  security_id: number | null;
  isin: string | null;
  name: string;
  asset_class: string | null;
  industry: string | null;
  in_recommendation_list: boolean | null;
  current_weight: number | null;
  target_weight: number | null;
  delta: number | null;
  amount: number | null;
  amount_currency: string | null;
  proposal_id: number | string | null;
  proposal_status: string | null;
  proposal_reason: string | null;
  proposal_date: string | null;
  portfolio_id: number | null;
  portfolio_nr: string | null;
  evidence: InstrumentCandidateEvidence[];
}

export interface InstrumentCandidateBuy {
  direction: 'buy';
  reason_code: string;
  security_id: number | null;
  isin: string | null;
  name: string;
  asset_class: string | null;
  industry: string | null;
  country_group: string | null;
  currency: string | null;
  currency_group: string | null;
  volatility: number | null;
  prc: number | null;
  sustainability_score: number | null;
  recommendation_lists: string[];
  target_category: string | null;
  target_weight: number | null;
  actual_weight: number | null;
  difference: number | null;
  rank: number | null;
  ranked_by: string[];
  proposal_id: number | string | null;
  proposal_status: string | null;
  proposal_reason: string | null;
  proposal_date: string | null;
  portfolio_id: number | null;
  portfolio_nr: string | null;
  evidence: InstrumentCandidateEvidence[];
}

export interface InstrumentCandidateBuyPool {
  portfolio_id: number | null;
  portfolio_nr: string | null;
  category: string;
  target_weight: number | null;
  actual_weight: number | null;
  difference: number | null;
  pool_size: number;
  offered: number;
  excluded_by_preference: number;
  ranked_by: string[];
}

export interface InstrumentCandidateExcluded {
  security_id: number | null;
  name: string;
  industry: string | null;
  keyword: string;
  note_path: string;
  asset_class: string | null;
  portfolio_nr: string | null;
}

export interface InstrumentCandidateGap {
  category: string;
  target_weight: number | null;
  actual_weight: number | null;
  difference: number | null;
  portfolio_nr: string | null;
  reason: string;
}

export interface InstrumentCandidates {
  scope: { client_ref: string; portfolio_nr: string | null };
  moves: InstrumentCandidateMove[];
  buys: InstrumentCandidateBuy[];
  buy_pools: InstrumentCandidateBuyPool[];
  excluded: InstrumentCandidateExcluded[];
  gaps: InstrumentCandidateGap[];
}

export interface Facts {
  client: { ref: string; display_name: string;[key: string]: unknown };
  portfolios: FactsPortfolio[];
  findings: unknown[];
  violations: unknown[];
  market_context: unknown[];
  market_meta: FactsMarketMeta;
  house_view: FactsHouseView;
  instrument_candidates: InstrumentCandidates;
  actions: FactsAction[];
  meta: FactsMeta;
}

/* ---------- Pipeline ---------- */

export interface PipelineStage {
  id: string;
  label: string;
  ms: number;
  status: 'ok' | 'unavailable';
  note: string | null;
}

/* ---------- Briefing response ---------- */

export interface BriefingResponse {
  facts: Facts;
  briefing: Briefing;
  stages: PipelineStage[];
}

/* ---------- Q&A ---------- */

export interface QaEvidence {
  label: string;
  value: number | string | null;
  source?: string;
  path?: string;
}

export interface QaResponse {
  answer: string;
  /** 'llm' when the model phrased the answer from this client's own analysis, 'rules' when the router did. */
  answered_by: 'llm' | 'rules';
  /** 'data' = the client's facts, 'web' = public pages (sources listed), 'none' = neither could answer. */
  source_kind: 'data' | 'web' | 'none';
  sources: { title: string | null; url: string | null; snippet: string | null }[];
  evidence: QaEvidence[];
  unavailable: string[];
  matched: { findings: string[]; sections: string[] };
}
