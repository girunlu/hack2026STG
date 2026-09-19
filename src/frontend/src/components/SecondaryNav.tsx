import {
  BookOpen,
  Users,
  AlertOctagon,
  AlertTriangle,
  NotebookPen,
  Wallet,
  Info,
  Phone,
  BarChart3,
  PieChart,
  Menu,
  ArrowLeft,
  Search,
  ChevronDown,
  ChevronRight,
  SquareMinus,
  Trash2,
  Pencil,
  Settings,
  Maximize2,
  Globe,
  LayoutGrid,
  Target,
  TrendingUp,
  Calendar,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { NavItem } from './types'
import { useT } from '../i18n'
import './components.css'

const ICON_MAP: Record<string, LucideIcon> = {
  book: BookOpen,
  users: Users,
  'alert-octagon': AlertOctagon,
  'alert-triangle': AlertTriangle,
  notebook: NotebookPen,
  wallet: Wallet,
  info: Info,
  phone: Phone,
  chart: BarChart3,
  pie: PieChart,
  menu: Menu,
  'arrow-left': ArrowLeft,
  search: Search,
  'chevron-down': ChevronDown,
  'chevron-right': ChevronRight,
  'square-minus': SquareMinus,
  trash: Trash2,
  pencil: Pencil,
  settings: Settings,
  maximize: Maximize2,
  globe: Globe,
  grid: LayoutGrid,
  target: Target,
  'trending-up': TrendingUp,
  calendar: Calendar,
}

interface SecondaryNavProps {
  items: NavItem[]
  active: string
  title?: string
  showBack?: boolean
  onBack?: () => void
  onNavigate?: (id: string) => void
}

export default function SecondaryNav({
  items,
  active,
  title,
  showBack,
  onBack,
  onNavigate,
}: SecondaryNavProps) {
  const t = useT()
  return (
    <nav className="uro-nav" aria-label={t('nav.advisorFolder')}>
      {title ? <div className="uro-nav__title">{title}</div> : null}
      <div className="uro-nav__items">
        {items.map((item) => {
          const Icon = item.icon ? ICON_MAP[item.icon] : undefined
          const isActive = item.id === active
          const classes = [
            'uro-nav__item',
            isActive ? 'uro-nav__item--active' : '',
          ]
            .filter(Boolean)
            .join(' ')
          const badgeClass =
            item.badgeTone === 'danger'
              ? 'uro-nav__badge--danger'
              : item.badgeTone === 'muted'
                ? 'uro-nav__badge--muted'
                : 'uro-nav__badge--solid'
          return (
            <button
              key={item.id}
              type="button"
              className={classes}
              aria-current={isActive ? 'page' : undefined}
              disabled={item.disabled}
              title={item.disabled ? t('nav.notInPrototype') : undefined}
              onClick={item.disabled ? undefined : () => onNavigate?.(item.id)}
            >
              {Icon ? <Icon size={14} /> : null}
              <span>{item.label}</span>
              {item.badge != null ? (
                <span className={`uro-nav__badge ${badgeClass}`}>
                  {item.badge}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
      <div className="uro-nav__right">
        {showBack ? (
          <button
            type="button"
            className="uro-nav__back"
            onClick={onBack}
            aria-label={t('common.back')}
            title={t('common.back')}
          >
            <ArrowLeft size={14} />
          </button>
        ) : null}
        <button
          type="button"
          className="uro-nav__item"
          aria-label={t('common.menu')}
          title={t('nav.notInPrototype')}
          disabled
        >
          <Menu size={14} />
        </button>
      </div>
    </nav>
  )
}
