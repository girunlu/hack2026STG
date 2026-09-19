/**
 * DonutChart — SVG donut.
 *
 * Semantics of `segments`:
 *   - Single-ring mode (default): each segment is an arc of ONE ring.
 *     `value` is the arc weight (any positive number; they are normalised to sum).
 *     Rendered as one <circle> per segment using stroke-dasharray on a shared radius.
 *   - Multi-ring mode: pass segments where each entry represents ONE concentric ring
 *     (e.g. 5 SAA category rings). Each segment is drawn as its own full/partial ring
 *     with decreasing radius. `value` is the fill fraction 0..1 (or 0..100 — values > 1
 *     are treated as percent and divided by 100).
 *
 * The component auto-detects mode: if `segments.length >= 2` AND every segment's
 * `value` is in [0, 1] (or all in [0, 100] with at least one > 1) AND the caller
 * wants multi-ring, they should pass a `rings` prop. For simplicity, we expose a
 * single `segments` array and always render them as arcs of ONE ring — callers who
 * need multi-ring should compose multiple <DonutChart> instances stacked via CSS,
 * OR pass `mode="rings"` to render each segment as its own concentric ring.
 */
import './components.css'

interface Segment {
  value: number
  color: string
}

interface DonutChartProps {
  size?: number
  strokeWidth?: number
  segments: Segment[]
  centerText?: string
  centerSub?: string
  alert?: boolean
  /**
   * When "rings", each segment is drawn as its own concentric ring (outer → inner),
   * with `value` interpreted as a percentage 0..100 and clamped there — a ring filled to the
   * percentage it states.
   * When "arcs" (default), segments are arcs of a single ring, normalised to sum.
   */
  mode?: 'arcs' | 'rings'
}

const VIEW = 100
const CENTER = VIEW / 2

export default function DonutChart({
  size = 80,
  strokeWidth = 8,
  segments,
  centerText,
  centerSub,
  alert,
  mode = 'arcs',
}: DonutChartProps) {
  const outerR = (VIEW - strokeWidth) / 2
  const gap = 8
  const ringCount = segments.length

  const renderArcs = () => {
    const total = segments.reduce((s, x) => s + Math.max(0, x.value), 0)
    const r = outerR
    const c = 2 * Math.PI * r
    let offset = 0
    return segments.map((seg, i) => {
      const frac = total > 0 ? Math.max(0, seg.value) / total : 0
      const dash = c * frac
      const el = (
        <circle
          key={i}
          cx={CENTER}
          cy={CENTER}
          r={r}
          fill="none"
          stroke={seg.color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${dash} ${c - dash}`}
          strokeDashoffset={-offset}
          transform={`rotate(-90 ${CENTER} ${CENTER})`}
          strokeLinecap="butt"
        />
      )
      offset += dash
      return el
    })
  }

  const renderRings = () =>
    segments.map((seg, i) => {
      const r = outerR - i * (strokeWidth + gap)
      if (r <= 0) return null
      const c = 2 * Math.PI * r
      const raw = seg.value
      // The percentage the caller states is the fraction drawn. Values outside 0..100 (or a
      // negative deviation) clamp at the ends rather than wrapping or overfilling the ring.
      const frac = Math.max(0, Math.min(1, raw / 100))
      const dash = c * frac
      return (
        <g key={i}>
          <circle
            className="uro-donut__bg"
            cx={CENTER}
            cy={CENTER}
            r={r}
            fill="none"
            stroke="var(--track)"
            strokeWidth={strokeWidth}
          />
          <circle
            cx={CENTER}
            cy={CENTER}
            r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${dash} ${c - dash}`}
            transform={`rotate(-90 ${CENTER} ${CENTER})`}
            strokeLinecap="butt"
          />
        </g>
      )
    })

  const children = mode === 'rings' ? renderRings() : renderArcs()
  const voidSize = mode === 'rings' && ringCount > 0
    ? outerR - (ringCount - 1) * (strokeWidth + gap) - strokeWidth / 2
    : outerR - strokeWidth / 2
  const voidDiameter = Math.max(0, voidSize * 2)

  return (
    <div
      className={`uro-donut${alert ? ' uro-donut--alert' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox={`0 0 ${VIEW} ${VIEW}`}
        width={size}
        height={size}
        role="img"
        aria-label={centerText ?? 'Donut-Diagramm'}
      >
        {mode === 'arcs' && segments.length > 0 ? (
          <circle
            className="uro-donut__bg"
            cx={CENTER}
            cy={CENTER}
            r={outerR}
            fill="none"
            stroke="var(--track)"
            strokeWidth={strokeWidth}
          />
        ) : null}
        {children}
      </svg>
      {centerText || centerSub ? (
        <div
          className="uro-donut__center"
          style={
            mode === 'rings' && voidDiameter > 0
              ? {
                  inset: `${(size - (voidDiameter / VIEW) * size) / 2}px`,
                }
              : undefined
          }
        >
          {centerText ? (
            <span className="uro-donut__center-text">{centerText}</span>
          ) : null}
          {centerSub ? (
            <span className="uro-donut__center-sub">{centerSub}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
