import { Search } from 'lucide-react'
import { useT } from '../i18n'
import './components.css'

interface SearchBoxProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export default function SearchBox({
  value,
  onChange,
  placeholder,
}: SearchBoxProps) {
  const t = useT()
  const resolvedPlaceholder = placeholder ?? t('common.search')
  return (
    <label className="uro-search">
      <Search size={14} className="uro-search__icon" />
      <input
        type="text"
        className="uro-search__input"
        value={value}
        placeholder={resolvedPlaceholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}
