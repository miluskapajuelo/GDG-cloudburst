import { useCallback } from 'react'
import * as api from '../api'
import { useStore, useToast } from '../store'

/**
 * POST /burst/reset, then hide live burst flags in the console.
 * Offline is tolerated (the console view is still cleared); a real API error is reported and returns false.
 */
export function useBurstReset(): () => Promise<boolean> {
  const { clearBurst } = useStore()
  const toast = useToast()
  return useCallback(async () => {
    try {
      await api.resetBurst()
    } catch (e) {
      if (e instanceof api.ApiError && (e.kind === 'network' || e.kind === 'timeout')) {
        toast({ tone: 'info', text: 'The triage API is offline. Cleared the burst in this console only.' })
      } else {
        toast({ tone: 'error', text: e instanceof Error ? `Could not reset the burst: ${e.message}` : 'Could not reset the burst.' })
        return false
      }
    }
    clearBurst()
    return true
  }, [clearBurst, toast])
}
