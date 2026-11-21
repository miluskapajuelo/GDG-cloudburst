/**
 * The signed-in agent (demo). Replace with the auth session when it exists.
 * Set VITE_AGENT_NAME and VITE_AGENT_ROLE in web/.env.local to show your own name.
 */
const name = (import.meta.env.VITE_AGENT_NAME as string | undefined)?.trim()
const role = (import.meta.env.VITE_AGENT_ROLE as string | undefined)?.trim()

export const AGENT = {
  name: name || 'Support Agent',
  role: role || 'L1 Support, EN and DE',
}
