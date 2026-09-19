import type { ReactNode } from 'react'

export interface NavItem {
  id: string
  label: string
  icon?: string
  badge?: number | null
  badgeTone?: 'danger' | 'muted' | 'solid'
  /** Items with no destination in the prototype render disabled instead of dead. */
  disabled?: boolean
}

export interface Column<T> {
  key: string
  label: string
  width?: string
  align?: 'left' | 'right' | 'center'
  sortable?: boolean
  render?: (row: T) => ReactNode
}

export type SortDirection = 'asc' | 'desc'

export interface SortState {
  key: string | null
  direction: SortDirection
}
