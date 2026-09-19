import { SquareMinus } from 'lucide-react'
import './components.css'

interface FilterTab {
  id: string
  label: string
  count: number
  hint?: string | null
  unsupported?: boolean
}

interface FilterTabsProps {
  tabs: FilterTab[]
  active: string
  onChange: (id: string) => void
  onAdd?: () => void
}

export default function FilterTabs({
  tabs,
  active,
  onChange,
  onAdd,
}: FilterTabsProps) {
  return (
    <div className="uro-filter-tabs" role="tablist">
      {tabs.map((tab) => {
        const isActive = tab.id === active
        const classes = [
          'uro-filter-tabs__tab',
          isActive ? 'uro-filter-tabs__tab--active' : '',
          tab.unsupported ? 'uro-filter-tabs__tab--unsupported' : '',
        ]
          .filter(Boolean)
          .join(' ')
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={classes}
            onClick={() => {
              if (!tab.unsupported) onChange(tab.id)
            }}
            title={tab.hint ?? undefined}
            disabled={tab.unsupported}
          >
            <span>{tab.label}</span>
            <span className="uro-filter-tabs__badge">{tab.count}</span>
          </button>
        )
      })}
      {onAdd ? (
        <button
          type="button"
          className="uro-filter-tabs__add"
          onClick={onAdd}
          aria-label="Neuer Filter"
          title="Neuer Filter"
        >
          <SquareMinus size={14} />
        </button>
      ) : null}
    </div>
  )
}
