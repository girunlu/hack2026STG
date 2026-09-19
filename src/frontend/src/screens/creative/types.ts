/**
 * B3 — Creative briefing format types.
 * Mirrors the POST /api/briefing response shape.
 */

export interface EvidenceIndexEntry {
  label: string;
  value: number | string | null;
  value_text: string | null;
  source: string;
  path: string;
}

export interface BriefingBlock {
  text: string;
  evidence_refs: string[];
  severity: 'high' | 'medium' | 'low' | null;
  source_kind: 'portfolio' | 'external' | 'mock' | 'gap';
  /** Set when the block is about one instrument, so its market results can be opened from here. */
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

export interface BriefingResponse {
  client_ref: string;
  client_name: string;
  renderer: 'template';
  sections: BriefingSection[];
  questions: BriefingQuestions;
  evidence_index: Record<string, EvidenceIndexEntry>;
  word_count: number;
  read_seconds_estimate: number;
  trimmed_blocks: Record<string, number>;
  generated_from: {
    data_as_of: string | null;
    engine_version: string;
    finding_count: number;
  };
}

export interface FactsPortfolio {
  id: number;
  nr: string;
  name: string;
  currency: string;
  aum: number;
  volatility: number | null;
  expected_return: number | null;
  value_at_risk: number | null;
  return_12m_pct: number | null;
  return_3m_pct: number | null;
  performance_as_of: string | null;
  service: string | null;
  strategy: string | null;
  data_gaps: string[];
  top_weight?: number | null;
  top_security?: string | null;
}

export interface FactsFinding {
  id: string;
  type: string;
  severity: string;
  score: number;
  portfolio_id: number;
  title: string;
  detail: string;
  evidence: Array<{
    label: string;
    value: number | string | null;
    source: string;
    path: string;
  }>;
}

export interface FactsAction {
  id: string;
  priority: number;
  action: string;
  rationale: string;
  finding_refs: string[];
  evidence: Array<{
    label: string;
    value: number | string | null;
    source: string;
    path: string;
  }>;
}

export interface FactsResponse {
  client: {
    ref: string;
    display_name: string;
    type: string | null;
    is_company: boolean;
    reporting_currency: string | null;
    aum: number;
    liquidity: number | null;
    risk_profile: {
      id: number;
      name: string;
      risk_level: string;
      max_vola: number | null;
      max_prc: number | null;
    } | null;
    esg_profile: string | null;
    birthday: string | null;
    profiling_date: string | null;
    tags: Array<{ name: string; type: string }>;
    overrides: Array<{ rule_code: string; description: string }>;
  };
  portfolios: FactsPortfolio[];
  findings: FactsFinding[];
  violations: Array<{
    id: number;
    portfolio_id: number;
    severity: string;
    rule_code: string;
    title: string;
    detail: string;
  }>;
  market_context: Array<{
    headline: string;
    source: string;
    url: string;
    published: string;
    linked_security_ids: string[];
    linked_sectors: string[];
    relevant_because: string;
  }>;
  market_meta: {
    providers_used: string[];
    fetched_at: string | null;
    unavailable_items: Array<{ name: string; isin: string | null; reason: string }>;
    queried: boolean;
    is_mock: boolean;
  };
  house_view: {
    source: string;
    source_url: string;
    as_of: string;
    mock: boolean;
    disclaimer: string;
    stances: Array<{
      dimension: string;
      category: string;
      stance: string;
      rationale: string;
    }>;
    matches: Array<{
      dimension: string;
      category: string;
      stance: string;
      relation: string;
      portfolio_id: number;
      evidence: Array<{ label: string; value: number | string | null }>;
    }>;
  };
  actions: FactsAction[];
  meta: {
    generated_at: string;
    data_as_of: string | null;
    unavailable: string[];
    engine_version: string;
    scope: {
      client_ref: string;
      portfolio_nr: string | null;
    };
    stages: Array<{
      id: string;
      label: string;
      ms: number;
      status: 'ok' | 'unavailable';
      note: string | null;
    }>;
  };
}

export interface BriefingApiResponse {
  facts: FactsResponse;
  briefing: BriefingResponse;
  stages: Array<{
    id: string;
    label: string;
    ms: number;
    status: 'ok' | 'unavailable';
    note: string | null;
  }>;
}
