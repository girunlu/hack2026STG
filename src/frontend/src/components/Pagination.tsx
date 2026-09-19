import { useT } from '../i18n'
import './components.css'

interface PaginationProps {
  page: number
  pageCount: number
  onPageChange: (page: number) => void
  pageSize: number
  pageSizeOptions?: number[]
  onPageSizeChange?: (size: number) => void
  total: number
}

function visiblePages(page: number, pageCount: number): (number | 'ellipsis')[] {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, i) => i + 1)
  }
  const pages: (number | 'ellipsis')[] = [1]
  const start = Math.max(2, page - 1)
  const end = Math.min(pageCount - 1, page + 1)
  if (start > 2) pages.push('ellipsis')
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < pageCount - 1) pages.push('ellipsis')
  pages.push(pageCount)
  return pages
}

export default function Pagination({
  page,
  pageCount,
  onPageChange,
  pageSize,
  pageSizeOptions,
  onPageSizeChange,
  total,
}: PaginationProps) {
  const t = useT()
  const safePage = Math.max(1, Math.min(page, Math.max(1, pageCount)))
  const pages = visiblePages(safePage, pageCount)

  return (
    <div className="uro-pagination">
      <button
        type="button"
        className="uro-pagination__nav"
        disabled={safePage <= 1}
        onClick={() => onPageChange(safePage - 1)}
      >
        « {t('common.previous')}
      </button>
      {pages.map((p, idx) =>
        p === 'ellipsis' ? (
          <span key={`e${idx}`} className="uro-pagination__spacer">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            className={`uro-pagination__btn${p === safePage ? ' uro-pagination__btn--active' : ''}`}
            onClick={() => onPageChange(p)}
            aria-current={p === safePage ? 'page' : undefined}
          >
            {p}
          </button>
        ),
      )}
      <button
        type="button"
        className="uro-pagination__nav"
        disabled={safePage >= pageCount}
        onClick={() => onPageChange(safePage + 1)}
      >
        {t('common.next')} »
      </button>
      <div className="uro-pagination__right">
        <span>{t('common.resultsPerPage')}</span>
        <select
          className="uro-pagination__select"
          value={pageSize}
          onChange={(e) => onPageSizeChange?.(Number(e.target.value))}
        >
          {(pageSizeOptions ?? [10, 25, 50, 100]).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <span>
          {total} {t('common.total')}
        </span>
      </div>
    </div>
  )
}
