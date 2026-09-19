import type { ReactNode } from 'react'
import type { Column, SortState } from './types'
import { ViolationIcon } from './ViolationIcon'
import { WarningIcon } from './WarningIcon'
import { useT } from '../i18n'
import './components.css'

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  onRowClick?: (row: T) => void
  showCheckboxes?: boolean
  showIndicators?: boolean
  indicators?: (row: T) => { violation: boolean; warning: boolean }
  sort?: SortState
  onSort?: (state: SortState) => void
  emptyText?: string
  footer?: ReactNode
}

function SortArrow({
  active,
  direction,
}: {
  active: boolean
  direction: 'asc' | 'desc'
}) {
  return (
    <span
      className={`uro-table__sort-arrow${active ? ' uro-table__sort-arrow--active' : ''}`}
      aria-hidden="true"
    >
      {direction === 'asc' ? '▲' : '▼'}
    </span>
  )
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  showCheckboxes,
  showIndicators,
  indicators,
  sort,
  onSort,
  emptyText,
  footer,
}: DataTableProps<T>) {
  const t = useT()
  const resolvedEmptyText = emptyText ?? t('common.noData')
  const handleSort = (key: string) => {
    if (!onSort) return
    const current = sort?.key === key ? sort.direction : null
    const next: SortState =
      current === 'asc'
        ? { key, direction: 'desc' }
        : current === 'desc'
          ? { key: null, direction: 'asc' }
          : { key, direction: 'asc' }
    onSort(next)
  }

  const thAlignClass = (align?: 'left' | 'right' | 'center') =>
    align === 'right'
      ? 'uro-table__th--right'
      : align === 'center'
        ? 'uro-table__th--center'
        : ''

  const tdAlignClass = (align?: 'left' | 'right' | 'center') =>
    align === 'right'
      ? 'uro-table__td--right'
      : align === 'center'
        ? 'uro-table__td--center'
        : ''

  return (
    <div className="uro-table-wrap">
      <table className="uro-table">
        <colgroup>
          {showCheckboxes ? <col style={{ width: 28 }} /> : null}
          {showIndicators ? (
            <>
              <col style={{ width: 20 }} />
              <col style={{ width: 20 }} />
            </>
          ) : null}
          {columns.map((c) => (
            <col key={c.key} style={c.width ? { width: c.width } : undefined} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {showCheckboxes ? <th className="uro-table__checkbox" /> : null}
            {showIndicators ? (
              <>
              <th aria-label={t('common.violation')} />
              <th aria-label={t('common.warning')} />
              </>
            ) : null}
            {columns.map((c) => {
              const sortable = c.sortable === true && !!onSort
              const active = sort?.key === c.key
              const dir = active && sort ? sort.direction : 'asc'
              return (
                <th
                  key={c.key}
                  className={`${thAlignClass(c.align)}${sortable ? ' uro-table__th--sortable' : ''}`}
                  onClick={sortable ? () => handleSort(c.key) : undefined}
                  style={c.width ? { width: c.width } : undefined}
                >
                  {c.label}
                  {sortable ? <SortArrow active={!!active} direction={dir} /> : null}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                className="uro-table__empty"
                colSpan={
                  columns.length +
                  (showCheckboxes ? 1 : 0) +
                  (showIndicators ? 2 : 0)
                }
              >
                {resolvedEmptyText}
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const key = rowKey(row)
              const ind = showIndicators && indicators ? indicators(row) : null
              return (
                <tr
                  key={key}
                  className={onRowClick ? 'uro-table__row--clickable' : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {showCheckboxes ? (
                    <td className="uro-table__checkbox">
                      <input type="checkbox" aria-label={t('common.selectRow')} />
                    </td>
                  ) : null}
                  {showIndicators ? (
                    <>
                      <td className="uro-table__indicator">
                        {ind?.violation ? <ViolationIcon /> : null}
                      </td>
                      <td className="uro-table__indicator">
                        {ind?.warning ? <WarningIcon /> : null}
                      </td>
                    </>
                  ) : null}
                  {columns.map((c) => {
                    const value = (row as Record<string, unknown>)[c.key]
                    const content: ReactNode = c.render
                      ? c.render(row)
                      : value == null
                        ? ''
                        : String(value)
                    return (
                      <td
                        key={c.key}
                        className={tdAlignClass(c.align)}
                        title={typeof content === 'string' ? content : undefined}
                      >
                        {content}
                      </td>
                    )
                  })}
                </tr>
              )
            })
          )}
        </tbody>
        {footer ? <tfoot className="uro-table__footer">{footer}</tfoot> : null}
      </table>
    </div>
  )
}
