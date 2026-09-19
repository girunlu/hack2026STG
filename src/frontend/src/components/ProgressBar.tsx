import './components.css'

interface ProgressBarProps {
  value: number
  color?: string
  max?: number
}

export default function ProgressBar({
  value,
  color,
  max = 1,
}: ProgressBarProps) {
  const safeMax = max === 0 ? 1 : max
  const frac = Math.max(0, Math.min(1, value / safeMax))
  return (
    <div
      className="uro-progress"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
    >
      <div
        className="uro-progress__fill"
        style={{
          width: `${frac * 100}%`,
          background: color ?? 'var(--primary)',
        }}
      />
    </div>
  )
}
