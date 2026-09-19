import type { ReactNode } from 'react'
import './components.css'

interface MetaBandProps {
  pairs?: { label: string; value: string }[]
  left?: ReactNode
  right?: ReactNode
  children?: ReactNode
  tone?: 'gray' | 'white'
}

export default function MetaBand({
  pairs,
  left,
  right,
  children,
  tone = 'gray',
}: MetaBandProps) {
  const style: React.CSSProperties | undefined =
    tone === 'white' ? { background: 'var(--bg-card)' } : undefined
  return (
    <div className="uro-meta" style={style}>
      {left ? <div className="uro-meta__left">{left}</div> : null}
      {pairs && pairs.length > 0 ? (
        <div className="uro-meta__pairs">
          {pairs.map((p, idx) => (
            <div key={idx} className="uro-meta__pair">
              <span className="uro-meta__label">{p.label}</span>
              <span className="uro-meta__value">{p.value}</span>
            </div>
          ))}
        </div>
      ) : null}
      {children}
      {right ? <div className="uro-meta__right">{right}</div> : null}
    </div>
  )
}
