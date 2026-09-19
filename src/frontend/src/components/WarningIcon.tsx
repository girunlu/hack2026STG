interface WarningIconProps {
  size?: number
}

export function WarningIcon({ size = 12 }: WarningIconProps) {
  return (
    <svg
      viewBox="0 0 12 11"
      width={size}
      height={Math.round(size * (11 / 12))}
      aria-label="Warnung"
      role="img"
    >
      <polygon points="6,0 12,11 0,11" fill="var(--warning)" />
      <rect x="5.4" y="3" width="1.2" height="4" fill="#fff" />
      <rect x="5.4" y="8" width="1.2" height="1.2" fill="#fff" />
    </svg>
  )
}
