import { useEffect, useState } from 'react'

/** Tiny hash router: no dependency, works from file:// and any static host. */
export function useRoute(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  const [parts, setParts] = useState(read)
  useEffect(() => {
    const on = () => setParts(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return parts
}

export function navigate(path: string) {
  window.location.hash = path.startsWith('/') ? path : `/${path}`
}

/** True when focus is in a text field, so single-key shortcuts don't hijack typing. */
export function isTyping(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null
  if (!el) return false
  return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)
}
