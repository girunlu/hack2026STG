/**
 * Swiss formatting. Implemented by hand rather than via `toLocaleString`, because the ICU data for
 * `de-CH` uses a typographic apostrophe (U+2019) that does not match the screenshots' `'` (U+0027) —
 * and a demo number that renders differently on the judge's machine is a bug.
 */

const APOSTROPHE = "'";

export function formatAmount(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const negative = value < 0;
  const fixed = Math.abs(value).toFixed(decimals);
  const [whole, fraction] = fixed.split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, APOSTROPHE);
  return `${negative ? '-' : ''}${fraction ? `${grouped}.${fraction}` : grouped}`;
}

export function formatMoney(value: number | null | undefined, currency = 'CHF', decimals = 2): string {
  if (value === null || value === undefined) return '—';
  return `${currency} ${formatAmount(value, decimals)}`;
}

/** For a value that is already a percentage: 15.1538 -> "15.15%". */
export function formatPct(value: number | null | undefined, decimals = 2, signed = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/** For a fraction: 0.567 -> "56.70%". */
export function formatFraction(value: number | null | undefined, decimals = 2, signed = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return formatPct(value * 100, decimals, signed);
}

/** Compact money for a donut centre: language-aware so `T` (German Tausend) does not read as
 *  English "trillion". EN: 905.5k / 905.5m / 905.5bn. DE: 905.5 Tsd. / 905.5 Mio. / 905.5 Mrd. */
export function formatCompactAmount(value: number | null | undefined, lang: 'en' | 'de' | string = 'en'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const abs = Math.abs(value);
  const isDe = lang === 'de';
  if (abs >= 1_000_000_000) {
    return isDe ? `${(value / 1_000_000_000).toFixed(1)} Mrd.` : `${(value / 1_000_000_000).toFixed(1)}bn`;
  }
  if (abs >= 1_000_000) {
    return isDe ? `${(value / 1_000_000).toFixed(1)} Mio.` : `${(value / 1_000_000).toFixed(1)}m`;
  }
  if (abs >= 1_000) {
    return isDe ? `${(value / 1_000).toFixed(1)} Tsd.` : `${(value / 1_000).toFixed(1)}k`;
  }
  return value.toFixed(0);
}

/** '2026-07-01' -> '01.07.2026'. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return '—';
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;
}
