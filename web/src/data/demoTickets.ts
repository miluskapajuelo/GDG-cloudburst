import demo from '../../../shared/fixtures/demo_tickets.json'

/** Hand-written demo and red-team tickets (owned by B2), offered as examples in "Test a ticket". */
export interface DemoTicket {
  id: string
  title: string
  purpose: string
  subject: string
  body: string
  burst: boolean
}
export const DEMO_TICKETS = (demo as { tickets: DemoTicket[] }).tickets
