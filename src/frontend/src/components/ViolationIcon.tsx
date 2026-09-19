interface ViolationIconProps {
  size?: number
}

export function ViolationIcon({ size = 12 }: ViolationIconProps) {
  return (
    <svg
      viewBox="0 0 12 12"
      width={size}
      height={size}
      aria-label="Regelverletzung"
      role="img"
    >
      <circle cx="6" cy="6" r="6" fill="var(--danger)" />
      <path
        d="M3.8 3.8 8.2 8.2 M8.2 3.8 3.8 8.2"
        stroke="#fff"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
