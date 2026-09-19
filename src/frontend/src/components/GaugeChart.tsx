import { useT } from '../i18n'
import './components.css'

interface GaugeChartProps {
  size?: number
  strokeWidth?: number
  percent: number | null
  color?: string
  label?: string
}

const VIEW_W = 100
const VIEW_H = 60
const CX = 50
const CY = 55
const R = 40

export default function GaugeChart({
  size = 120,
  strokeWidth = 6,
  percent,
  color = 'var(--primary)',
  label,
}: GaugeChartProps) {
  const t = useT()
  const halfCirc = Math.PI * R
  const clamped =
    percent == null ? null : Math.max(0, Math.min(100, percent))
  const fill = clamped == null ? 0 : (clamped / 100) * halfCirc

  const displayLabel =
    clamped == null ? '—' : `${clamped.toFixed(clamped % 1 === 0 ? 0 : 1)}%`

  return (
    <div className="uro-gauge" style={{ width: size }}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        width={size}
        height={size * (VIEW_H / VIEW_W)}
        role="img"
        aria-label={label ?? (clamped == null ? t('chart.metricUnavailable') : t('chart.metric', { value: displayLabel }))}
      >
        <path
          d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`}
          fill="none"
          stroke="var(--track)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {clamped != null && clamped > 0 ? (
          <path
            d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${fill} ${halfCirc}`}
          />
        ) : null}
        <text
          x={CX}
          y={CY - 4}
          className={
            clamped == null
              ? 'uro-gauge__label uro-gauge__label--empty'
              : 'uro-gauge__label'
          }
        >
          {displayLabel}
        </text>
        {label ? (
          <text
            x={CX}
            y={CY + 10}
            textAnchor="middle"
            fontSize="8"
            fill="var(--text-secondary)"
          >
            {label}
          </text>
        ) : null}
      </svg>
    </div>
  )
}
