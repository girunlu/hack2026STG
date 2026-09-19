import { Search, ChevronDown } from 'lucide-react'
import { useI18n } from '../i18n'
import type { Lang } from '../i18n'
import './components.css'

export default function Header() {
  const { lang, setLang, t } = useI18n()

  return (
    <header className="uro-header">
      <img
        src="/logos/uro-dark.svg"
        alt="URO Advisor Pro"
        className="uro-header__logo"
      />
      <div className="uro-header__spacer" />
      <div className="uro-header__lang-switcher">
        <button
          type="button"
          className={`uro-header__lang-btn${lang === 'en' ? ' uro-header__lang-btn--active' : ''}`}
          onClick={() => setLang('en' as Lang)}
          aria-pressed={lang === 'en'}
        >
          EN
        </button>
        <span className="uro-header__lang-sep">|</span>
        <button
          type="button"
          className={`uro-header__lang-btn${lang === 'de' ? ' uro-header__lang-btn--active' : ''}`}
          onClick={() => setLang('de' as Lang)}
          aria-pressed={lang === 'de'}
        >
          DE
        </button>
      </div>
      <button
        type="button"
        className="uro-header__search"
        aria-label={t('header.search')}
        title={t('header.search')}
        onClick={() => {
          window.location.hash = '#/market';
        }}
      >
        <Search size={16} />
      </button>
      <button type="button" className="uro-header__user">
        Hans Muster
        <ChevronDown size={14} />
      </button>
    </header>
  )
}
