/**
 * Compile-time guard: shared/fixtures/mock_triage_response.json must have the
 * exact shape of TriageResponse (docs/contract.md §1). If `npm run build`
 * fails here, types.ts and the contract fixture have drifted.
 */
import mock from '../../shared/fixtures/mock_triage_response.json'
import type { TriageResponse } from './types'

/** JSON imports widen string literals ("de" -> string); compare shapes, not literals. */
type Loose<T> = T extends string
  ? string
  : T extends (infer U)[]
    ? Loose<U>[]
    : T extends object
      ? { [K in keyof T]: Loose<T[K]> }
      : T

// Fails to compile if the fixture lacks (or renames) any contract field, or a type differs.
const _shapeOk: Loose<TriageResponse> = mock
void _shapeOk

/** The contract fixture, typed. Used when no API is running. */
export const MOCK_TRIAGE = mock as TriageResponse
