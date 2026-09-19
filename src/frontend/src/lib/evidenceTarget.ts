import type { MessageKey } from '../i18n';

/**
 * Where an evidence row can be inspected.
 *
 * Every slice the briefing and the assistant quote (a violating rule, a position's weight, a target
 * deviation, a note) is a row an advisor may want to open and read in full — "13 rule violations"
 * is only useful if the next click shows *which* thirteen. The destination is derived from the data
 * path the row already carries, so the mapping follows the data model rather than a hand-kept list
 * of blocks, and a row whose path has no screen here stays plain text.
 */
export type EvidenceTarget =
  | { kind: 'client'; section: string }
  | { kind: 'portfolio'; section: string }
  | { kind: 'market'; isin: string }
  | { kind: 'external'; url: string };

export interface EvidenceRow {
  ref?: string | null;
  path?: string | null;
  label?: string | null;
  /**
   * The finding's own type, when the row is a whole finding (its ref carries no data path). The type
   * is the domain the finding is about, so it decides the screen the same way a path does.
   */
  findingType?: string | null;
}

/** The section ids the client and portfolio screens publish as scroll anchors. */
export const CLIENT_SECTION = {
  violations: 'client-violations',
  portfolios: 'client-portfolios',
  notes: 'client-notes',
  top: 'client-top',
} as const;

export const PORTFOLIO_SECTION = {
  allocation: 'portfolio-saa',
  positions: 'portfolio-positions',
} as const;

/**
 * Data path → destination, in the order the paths nest. The keys are the field names the case data
 * and the derived facts actually use (`ViolationPath`, `SuitabilityViolations`, `SecurityPositions`,
 * …), so adding a screen means adding one entry here.
 */
const CLIENT_PATHS: [string, string][] = [
  ['SuitabilityViolations', CLIENT_SECTION.violations],
  ['RuleViolation', CLIENT_SECTION.violations],
  ['ClientNotes', CLIENT_SECTION.notes],
  ['Proposals', CLIENT_SECTION.portfolios],
  ['AdvisoryTypeName', CLIENT_SECTION.portfolios],
  ['Transactions', CLIENT_SECTION.portfolios],
];

const PORTFOLIO_PATHS: [string, string][] = [
  ['SecurityPositions', PORTFOLIO_SECTION.positions],
  ['ContributionVolatility', PORTFOLIO_SECTION.positions],
  ['MarginalRisk', PORTFOLIO_SECTION.positions],
  ['MarketValue', PORTFOLIO_SECTION.positions],
  ['StrategicAssetAllocation', PORTFOLIO_SECTION.allocation],
  ['AssetClass', PORTFOLIO_SECTION.allocation],
  ['SaaTarget', PORTFOLIO_SECTION.allocation],
];

const ISIN = /\b([A-Z]{2}[A-Z0-9]{9}\d)\b/;

/** Finding type → destination, for rows that are a finding rather than a value inside one. */
const FINDING_TYPES: Record<string, EvidenceTarget> = {
  rule_violation: { kind: 'client', section: CLIENT_SECTION.violations },
  allocation_drift: { kind: 'portfolio', section: PORTFOLIO_SECTION.allocation },
  concentration: { kind: 'portfolio', section: PORTFOLIO_SECTION.positions },
  sector_concentration: { kind: 'portfolio', section: PORTFOLIO_SECTION.positions },
  performance_driver: { kind: 'portfolio', section: PORTFOLIO_SECTION.positions },
};

export function evidenceTarget(row: EvidenceRow): EvidenceTarget | null {
  const path = `${row.path ?? ''} ${row.ref ?? ''}`.trim();

  // A news row is a public article: its ref *is* the page, so the row opens the source itself.
  const url = (row.ref ?? '').match(/https?:\/\/\S+/)?.[0];
  if (path.startsWith('news:') || (url && !ISIN.test(path))) {
    return url ? { kind: 'external', url } : null;
  }

  // A row that names a security is a security question: the market screen answers it by ISIN.
  const isin = path.match(ISIN)?.[1] ?? `${row.label ?? ''}`.match(ISIN)?.[1];
  if (isin) return { kind: 'market', isin };

  const byType = row.findingType ? FINDING_TYPES[row.findingType] : undefined;
  if (byType) return byType;

  for (const [needle, section] of CLIENT_PATHS) {
    if (path.includes(needle)) return { kind: 'client', section };
  }
  for (const [needle, section] of PORTFOLIO_PATHS) {
    if (path.includes(needle)) return { kind: 'portfolio', section };
  }
  return null;
}

/** What the click will show, in the advisor's words — the affordance has to say where it goes. */
export const TARGET_LABEL: Record<string, MessageKey> = {
  'client:client-violations': 'evidenceTarget.violations',
  'client:client-portfolios': 'evidenceTarget.portfolios',
  'client:client-notes': 'evidenceTarget.notes',
  'portfolio:portfolio-positions': 'evidenceTarget.positions',
  'portfolio:portfolio-saa': 'evidenceTarget.allocation',
  market: 'evidenceTarget.market',
  external: 'evidenceTarget.source',
};

export function targetLabelKey(target: EvidenceTarget): MessageKey {
  if (target.kind === 'market') return TARGET_LABEL.market;
  if (target.kind === 'external') return TARGET_LABEL.external;
  return TARGET_LABEL[`${target.kind}:${target.section}`] ?? 'evidenceTarget.open';
}
