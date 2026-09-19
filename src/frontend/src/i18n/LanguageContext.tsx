import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { messages, type Lang, type MessageKey } from './messages';

const STORAGE_KEY = 'uro.lang';
const DEFAULT_LANG: Lang = 'en';

function readStoredLang(): Lang {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === 'en' || raw === 'de') return raw;
  } catch {
    // localStorage may throw in private mode or when disabled — fall through.
  }
  return DEFAULT_LANG;
}

interface I18nState {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nState | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readStoredLang());

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  // Keep <html lang> in sync so screen readers and search engines pick it up.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const t = useCallback(
    (key: MessageKey, vars?: Record<string, string | number>) => {
      const table = messages[lang] ?? messages.en;
      let text: string =
        (table as Record<string, string>)[key] ??
        (messages.en as Record<string, string>)[key] ??
        key;
      if (vars) {
        // Handle ICU plural syntax: {count, plural, one {singular} other {plural}}
        text = text.replace(/\{(\w+),\s*plural,\s*one\s*\{([^}]*)\}\s*other\s*\{([^}]*)\}\}/g, (match, varName, oneForm, otherForm) => {
          const value = vars[varName];
          if (typeof value === 'number') {
            return value === 1 ? oneForm : otherForm;
          }
          return match;
        });
        // Simple variable substitution
        for (const [k, v] of Object.entries(vars)) {
          text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
        }
      }
      return text;
    },
    [lang],
  );

  const value = useMemo<I18nState>(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider');
  return ctx;
}

/** Convenience alias — returns only the `t` function. */
export function useT(): (key: MessageKey, vars?: Record<string, string | number>) => string {
  return useI18n().t;
}

export type { Lang, MessageKey };
