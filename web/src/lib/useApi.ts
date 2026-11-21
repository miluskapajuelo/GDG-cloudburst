import { useEffect, useState } from 'react'
import * as api from '../api'
import type { GateConfig, Health, HoldoutMetrics } from '../types'

export type HealthState = { state: 'checking' } | { state: 'online'; health: Health } | { state: 'offline' }

export function useHealth(pollMs = 15_000): HealthState {
  const [h, setH] = useState<HealthState>({ state: api.OFFLINE ? 'offline' : 'checking' })
  useEffect(() => {
    if (api.OFFLINE) return
    let alive = true
    const check = () =>
      api.health().then(
        (health) => alive && setH({ state: 'online', health }),
        () => alive && setH({ state: 'offline' }),
      )
    check()
    const id = setInterval(check, pollMs)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [pollMs])
  return h
}

export function useConfig(): GateConfig | null {
  const [c, setC] = useState<GateConfig | null>(null)
  useEffect(() => {
    if (api.OFFLINE) return
    api.config().then(setC, () => setC(null))
  }, [])
  return c
}

export type MetricsState = { state: 'loading' } | { state: 'ok'; metrics: HoldoutMetrics } | { state: 'not_run' } | { state: 'offline' }
export function useMetrics(): MetricsState {
  const [m, setM] = useState<MetricsState>({ state: api.OFFLINE ? 'offline' : 'loading' })
  useEffect(() => {
    if (api.OFFLINE) return
    api.metrics().then(
      (metrics) => setM({ state: 'ok', metrics }),
      (e) => setM({ state: e instanceof api.ApiError && e.kind === 'not_found' ? 'not_run' : 'offline' }),
    )
  }, [])
  return m
}
