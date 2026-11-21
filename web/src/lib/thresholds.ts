/** Shown when GET /config is unavailable. */
/** Kept in sync with agent/config.py defaults (B2 owns the real values; GET /config is the source of truth). */
export const DEFAULT_THRESHOLDS: Record<string, number> = { T_HIGH_PRIORITY_P: 0.2, T_INCIDENT_P: 0.3, T_CONF_TYPE: 0.5, T_CONF_PRIORITY: 0.5, T_CONF_QUEUE: 0.25, T_SIM: 0.55, TOP_K: 5, BURST_SIM: 0.65, BURST_MIN: 3, BURST_WINDOW_MIN: 15 }
export const EXPLAIN: Record<string, string> = {
  T_HIGH_PRIORITY_P: 'Probability of “high” priority at which an incident goes to on-call',
  T_INCIDENT_P: 'Probability of “Incident” required for an on-call escalation',
  T_CONF_TYPE: 'Below this type confidence, a person reviews the ticket',
  T_CONF_PRIORITY: 'Below this priority confidence, a person reviews the ticket',
  T_CONF_QUEUE: 'Below this queue confidence, a person reviews the ticket',
  T_SIM: 'Minimum similarity to a past resolution before a response is suggested',
  TOP_K: 'Number of historical resolutions retrieved per ticket',
  BURST_SIM: 'Similarity for grouping tickets into a possible major incident',
  BURST_MIN: 'Similar tickets needed to flag a major incident',
  BURST_WINDOW_MIN: 'Time window for major-incident detection (minutes)',
}
