import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

/**
 * Lets a screen publish the badge counts the shell's navigation should show, so the shell never has
 * to fetch data a screen already has. The provider is remounted per route, which clears badges when
 * the advisor navigates.
 */

type BadgeValues = Record<string, number | null>;

interface ShellState {
  badges: BadgeValues;
  setBadges: (badges: BadgeValues) => void;
}

const ShellContext = createContext<ShellState | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [badges, setBadges] = useState<BadgeValues>({});
  const value = useMemo<ShellState>(() => ({ badges, setBadges }), [badges]);
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShellBadges(badges: BadgeValues): void {
  const shell = useContext(ShellContext);
  const setBadges = shell?.setBadges;
  const key = JSON.stringify(badges);
  useEffect(() => {
    if (setBadges) setBadges(JSON.parse(key) as BadgeValues);
  }, [key, setBadges]);
}

export function useShellBadgeValues(): BadgeValues {
  return useContext(ShellContext)?.badges ?? {};
}
