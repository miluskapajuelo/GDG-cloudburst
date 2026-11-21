/**
 * Presentation safety net: a switch that swaps the live API for built-in demo
 * data (mockBackend + localTriage). Off by default. Stored in localStorage so a
 * refresh keeps the mode; flipping it reloads the page so every view re-seeds.
 */
const KEY = 'sentineldesk.demoMode'

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export const DEMO_MODE = read()

export function setDemoMode(on: boolean): void {
  try {
    if (on) localStorage.setItem(KEY, '1')
    else localStorage.removeItem(KEY)
  } catch {
    /* storage blocked: the reload below falls back to live mode */
  }
  location.reload()
}
