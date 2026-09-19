import type { ReactNode } from 'react'
import './components.css'

interface CardProps {
  title?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  padded?: boolean
}

export default function Card({
  title,
  actions,
  children,
  className,
  padded = true,
}: CardProps) {
  const hasHeader = title || actions
  return (
    <div className={`uro-card${className ? ` ${className}` : ''}`}>
      {hasHeader ? (
        <div className="uro-card__header">
          <div className="uro-card__title">{title}</div>
          {actions ? <div className="uro-card__actions">{actions}</div> : null}
        </div>
      ) : null}
      <div className={padded ? 'uro-card__body' : 'uro-card__body uro-card__body--flush'}>
        {children}
      </div>
    </div>
  )
}
