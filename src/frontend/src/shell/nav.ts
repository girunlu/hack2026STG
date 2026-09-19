import type { NavItem } from '../components/types';
import type { MessageKey } from '../i18n';

/**
 * Navigation per screen, transcribed from the URO Advisor Pro screenshots
 * (`unriskomega-2026/ui_reverse/01-component-table.md` §1). Badge values are injected by the shell
 * from real counts, never hard-coded here.
 */

type T = (key: MessageKey) => string;

export function dashboardNav(t: T): NavItem[] {
  return [
    { id: 'beratermappe', label: t('nav.advisorFolder'), icon: 'book' },
    { id: 'kundenliste', label: t('nav.clientList'), icon: 'users' },
    { id: 'regelverletzungen', label: t('nav.ruleViolations'), icon: 'alert-octagon', badgeTone: 'danger' },
    { id: 'warnungen', label: t('nav.warnings'), icon: 'alert-triangle', badgeTone: 'danger' },
    { id: 'menu', label: '', icon: 'menu', disabled: true },
  ];
}

export function clientNav(t: T): NavItem[] {
  return [
    { id: 'beratermappe', label: t('nav.advisorFolder'), icon: 'book' },
    { id: 'notizen', label: t('nav.notes'), icon: 'notebook', badgeTone: 'muted' },
    { id: 'vermoegen', label: t('nav.assets'), icon: 'wallet' },
    { id: 'regelverletzungen', label: t('nav.ruleViolations'), icon: 'alert-octagon', badgeTone: 'danger' },
    { id: 'kundeninformation', label: t('nav.clientInfo'), icon: 'info' },
    { id: 'menu', label: '', icon: 'menu', disabled: true },
  ];
}

export function portfolioNav(t: T): NavItem[] {
  return [
    { id: 'telefonberatung', label: t('nav.phoneConsultation'), icon: 'phone', disabled: true },
    { id: 'beratermappe', label: t('nav.advisorFolder'), icon: 'book' },
    { id: 'notizen', label: t('nav.notes'), icon: 'notebook', badgeTone: 'muted' },
    { id: 'analyse', label: t('nav.analysis'), icon: 'chart' },
    { id: 'kundeninformation', label: t('nav.clientInfo'), icon: 'info' },
    { id: 'portfolio', label: t('nav.portfolio'), icon: 'pie' },
    { id: 'menu', label: '', icon: 'menu', disabled: true },
  ];
}
