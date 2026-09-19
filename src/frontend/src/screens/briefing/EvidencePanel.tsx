import { useI18n } from '../../i18n';
import { evidenceTarget, targetLabelKey, type EvidenceRow as EvidenceRowData, type EvidenceTarget } from '../../lib/evidenceTarget';
import type { EvidenceIndex } from './briefingTypes';

interface EvidencePanelProps {
  refs: string[];
  index: EvidenceIndex;
  heading?: string;
  /** Inline evidence rows (e.g. from Q&A) — rendered in addition to refs. */
  inline?: { label: string; value: number | string | null; source?: string; path?: string }[];
  /**
   * Where a row can be opened. Rows whose data path has a screen here render as buttons that hand the
   * resolved target back — a slice like "13 rule violations" is only useful if the next click shows
   * which thirteen. Without a handler, or without a destination, the row stays plain text.
   */
  onOpen?: (target: EvidenceTarget) => void;
  /** The finding type behind a ref, for rows that are a whole finding and carry no data path. */
  findingTypeOf?: (ref: string) => string | null;
}

function formatValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '—';
  if (typeof value !== 'number') return String(value);
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

export default function EvidencePanel({
  refs,
  index,
  heading,
  inline,
  onOpen,
  findingTypeOf,
}: EvidencePanelProps) {
  const { t } = useI18n();
  const resolved = refs
    .map((ref) => {
      const entry = index[ref];
      if (!entry) return null;
      return { ref, entry };
    })
    .filter((x): x is { ref: string; entry: EvidenceIndex[string] } => x !== null);

  const hasContent = resolved.length > 0 || (inline && inline.length > 0);

  /** One row: the slice on the first line, where it came from on the second, and a way to open it. */
  const renderRow = (
    key: string,
    data: EvidenceRowData & { value: number | string | null | undefined; source?: string },
  ) => {
    const findingType = data.ref ? findingTypeOf?.(data.ref) ?? null : null;
    const target = onOpen ? evidenceTarget({ ...data, findingType }) : null;
    const body = (
      <>
        <div className="evidence-line">
          <div className="evidence-label">{data.label}</div>
          <div className="evidence-value">{formatValue(data.value)}</div>
        </div>
        <div className="evidence-meta">
          <span className="evidence-source">
            {data.source ?? '—'}
            {data.path ? ` · ${data.path}` : ''}
          </span>
          {target ? (
            <span className="evidence-open">{t(targetLabelKey(target))} ↗</span>
          ) : null}
        </div>
      </>
    );

    if (target && onOpen) {
      return (
        <button
          key={key}
          type="button"
          className="evidence-row evidence-row--action"
          onClick={() => onOpen(target)}
          title={data.path ?? undefined}
        >
          {body}
        </button>
      );
    }
    return (
      <div key={key} className="evidence-row">
        {body}
      </div>
    );
  };

  return (
    <div className="evidence-panel">
      <div className="evidence-panel-title">{heading ?? t('briefing.evidence')}</div>
      {!hasContent ? (
        <div className="evidence-panel-empty">{t('briefing.noEvidenceForBlock')}</div>
      ) : null}
      {resolved.map(({ ref, entry }) =>
        renderRow(ref, {
          ref,
          path: entry.path,
          label: entry.label,
          value:
            entry.value_text !== null && entry.value_text !== undefined ? entry.value_text : entry.value,
          source: entry.source,
        }),
      )}
      {inline && inline.length > 0
        ? inline.map((row, i) =>
            renderRow(`inline-${i}`, {
              path: row.path,
              label: row.label,
              value: row.value,
              source: row.source,
            }),
          )
        : null}
    </div>
  );
}
