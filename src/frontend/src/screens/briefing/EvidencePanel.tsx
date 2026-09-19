import { useI18n } from '../../i18n';
import type { EvidenceIndex } from './briefingTypes';

interface EvidencePanelProps {
  refs: string[];
  index: EvidenceIndex;
  heading?: string;
  /** Inline evidence rows (e.g. from Q&A) — rendered in addition to refs. */
  inline?: { label: string; value: number | string | null; source?: string; path?: string }[];
}

export default function EvidencePanel({ refs, index, heading, inline }: EvidencePanelProps) {
  const { t } = useI18n();
  const resolved = refs
    .map((ref) => {
      const entry = index[ref];
      if (!entry) return null;
      return { ref, entry };
    })
    .filter((x): x is { ref: string; entry: EvidenceIndex[string] } => x !== null);

  const hasContent = resolved.length > 0 || (inline && inline.length > 0);

  return (
    <div className="evidence-panel">
      <div className="evidence-panel-title">{heading ?? t('briefing.evidence')}</div>
      {!hasContent ? (
        <div className="evidence-panel-empty">{t('briefing.noEvidenceForBlock')}</div>
      ) : null}
      {resolved.map(({ ref, entry }) => (
        <div key={ref} className="evidence-row">
          <div className="evidence-label">{entry.label}</div>
          <div className="evidence-value">
            {entry.value_text !== null && entry.value_text !== undefined
              ? entry.value_text
              : entry.value === null || entry.value === undefined
                ? '—'
                : typeof entry.value === 'number'
                  ? Number.isInteger(entry.value)
                    ? String(entry.value)
                    : entry.value.toFixed(2)
                  : String(entry.value)}
          </div>
          <div className="evidence-source">
            {entry.source}
            {entry.path ? ` · ${entry.path}` : ''}
          </div>
          <div className="evidence-path">{ref}</div>
        </div>
      ))}
      {inline && inline.length > 0
        ? inline.map((row, i) => (
            <div key={`inline-${i}`} className="evidence-row">
              <div className="evidence-label">{row.label}</div>
              <div className="evidence-value">
                {row.value === null || row.value === undefined
                  ? '—'
                  : typeof row.value === 'number'
                    ? Number.isInteger(row.value)
                      ? String(row.value)
                      : row.value.toFixed(2)
                    : String(row.value)}
              </div>
              <div className="evidence-source">
                {row.source ?? '—'}
                {row.path ? ` · ${row.path}` : ''}
              </div>
            </div>
          ))
        : null}
    </div>
  );
}
