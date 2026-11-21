import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export interface Prefs {
  showTranslation: boolean
  pageOnlyCritical: boolean
  confirmBeforeSend: boolean
  density: 'comfortable' | 'compact'
  theme: 'dark' | 'light' | 'system'
}
const DEFAULTS: Prefs = { showTranslation: true, pageOnlyCritical: true, confirmBeforeSend: true, density: 'comfortable', theme: 'dark' }
const KEY = 'sentineldesk.prefs'

function load(): Prefs {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) ?? '{}') }
  } catch {
    return DEFAULTS
  }
}

const Ctx = createContext<{ prefs: Prefs; set: (p: Partial<Prefs>) => void }>({ prefs: DEFAULTS, set: () => {} })

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(load)
  const set = (p: Partial<Prefs>) =>
    setPrefs((cur) => {
      const next = { ...cur, ...p }
      try {
        localStorage.setItem(KEY, JSON.stringify(next))
      } catch {
        /* storage unavailable: keep in memory */
      }
      return next
    })
  // Dark is the default look; light is for bright rooms and washed-out projectors.
  useEffect(() => {
    document.documentElement.dataset.theme = prefs.theme
  }, [prefs.theme])
  return <Ctx.Provider value={{ prefs, set }}>{children}</Ctx.Provider>
}
export const usePrefs = () => useContext(Ctx)
