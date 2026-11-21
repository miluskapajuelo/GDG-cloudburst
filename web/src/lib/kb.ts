import type { Precedent } from '../types'
import examples from '../data/dataset_examples.json'

/**
 * Precedents for OFFLINE mode and help-article suggestions.
 * 1) 10 real dataset rows that are in the KB split (see data/dataset_examples.json).
 * 2) Hand-written demo precedents.
 * Never add holdout test rows here (docs/data-and-leakage.md).
 * When the API is up, precedents come from the real KB index.
 */
type KbRow = Omit<Precedent, 'similarity' | 'answer_snippet' | 'body_snippet'> & { body: string }

const REAL: KbRow[] = (examples as { tickets: (KbRow & { answer: string })[] }).tickets.map((t) => ({
  ticket_id: t.ticket_id, language: t.language, subject: t.subject, body: t.body, answer: t.answer.replace(/<name>/g, 'there'),
  type: t.type, queue: t.queue, priority: t.priority, tags: t.tags,
}))

const HAND_WRITTEN: KbRow[] = [
  {
    ticket_id: 'TKT-00412', language: 'en', subject: 'VPN error 809 for all remote sites',
    body: 'Since this morning none of our branch offices can establish a VPN connection. Clients report error 809. Restarting the firewall did not help.',
    answer: 'The VPN gateway certificate had expired overnight, which causes error 809 during authentication. We renewed the certificate and restarted the VPN service; connections were restored. Please check the certificate expiry date on the gateway and set a renewal reminder.',
    type: 'Incident', queue: 'Technical Support', priority: 'high', tags: ['VPN', 'Network', 'Outage'],
  },
  {
    ticket_id: 'TKT-03187', language: 'en', subject: 'IKEv2 VPN connections failing after firewall change',
    body: 'After a firewall rule update yesterday our IKEv2 VPN tunnels fail to connect for all users.',
    answer: 'The firewall update blocked UDP ports 500 and 4500 used by IKEv2. After re-opening both ports the tunnels came back up. We recommend reviewing firewall change requests against the VPN port list.',
    type: 'Incident', queue: 'IT Support', priority: 'high', tags: ['VPN', 'Firewall'],
  },
  {
    ticket_id: 'TKT-11920', language: 'de', subject: 'VPN-Ausfall nach Client-Update',
    body: 'Nach dem automatischen Update des VPN-Clients können sich unsere Mitarbeitenden nicht mehr anmelden.',
    answer: 'Das Client-Update hat das gespeicherte Zertifikatsprofil zurückgesetzt. Nach dem erneuten Import des Profils funktionierte die Verbindung wieder. Wir empfehlen, das Profil zentral zu verteilen.',
    type: 'Incident', queue: 'Technical Support', priority: 'medium', tags: ['VPN', 'Client'],
  },
  {
    ticket_id: 'TKT-02254', language: 'en', subject: 'Password reset email never arrives',
    body: 'I requested a password reset three times but the email does not arrive, not even in spam.',
    answer: 'Reset emails were being held by the recipient mail server because our sender domain was not on the allow-list. Please ask your IT team to allow-list noreply@ our domain, then request a new reset link; links are valid for 30 minutes.',
    type: 'Request', queue: 'IT Support', priority: 'medium', tags: ['Login', 'Email', 'Account'],
  },
  {
    ticket_id: 'TKT-05531', language: 'de', subject: 'Passwort-Zurücksetzen funktioniert nicht',
    body: 'Die E-Mail zum Zurücksetzen des Passworts kommt nicht an.',
    answer: 'Bitte prüfen Sie den Spam-Ordner und ob unsere Absenderadresse von Ihrem Mailserver blockiert wird. Nach der Freigabe können Sie einen neuen Link anfordern; dieser ist 30 Minuten gültig.',
    type: 'Request', queue: 'IT Support', priority: 'medium', tags: ['Login', 'Account'],
  },
  {
    ticket_id: 'TKT-07788', language: 'en', subject: 'Charged twice for the same invoice',
    body: 'Our card was charged twice for invoice 2024-118. Please fix this.',
    answer: 'We confirmed a duplicate authorisation caused by a payment-gateway retry. The second authorisation was voided and disappears from your statement within 5–7 business days. No action is needed on your side.',
    type: 'Problem', queue: 'Billing and Payments', priority: 'medium', tags: ['Billing', 'Payment'],
  },
  {
    ticket_id: 'TKT-09102', language: 'en', subject: 'Dashboard returns 502 Bad Gateway',
    body: 'The analytics dashboard shows 502 errors intermittently since the last release.',
    answer: 'The 502 errors came from an upstream timeout on the reporting service under heavy queries. We increased the timeout and added caching; please clear your browser cache and reload. If it persists, send us the time and the request ID shown on the error page.',
    type: 'Problem', queue: 'Technical Support', priority: 'medium', tags: ['Bug', 'Performance'],
  },
  {
    ticket_id: 'TKT-04410', language: 'de', subject: 'Berechtigung für Projektordner ändern',
    body: 'Bitte geben Sie meiner Kollegin Schreibrechte auf den Ordner Projekte/2025.',
    answer: 'Berechtigungsänderungen müssen vom Ordnerverantwortlichen freigegeben werden. Bitte senden Sie uns die Freigabe per E-Mail; danach richten wir die Schreibrechte innerhalb eines Werktags ein.',
    type: 'Change', queue: 'IT Support', priority: 'low', tags: ['Access', 'IT'],
  },
  {
    ticket_id: 'TKT-06620', language: 'en', subject: 'Account locked after failed logins',
    body: 'My account is locked after too many failed login attempts.',
    answer: 'Accounts unlock automatically after 15 minutes. If you need access sooner, verify your identity through the self-service portal, which unlocks the account immediately. We recommend enabling MFA to avoid future lockouts.',
    type: 'Request', queue: 'IT Support', priority: 'medium', tags: ['Login', 'Security'],
  },
  {
    ticket_id: 'TKT-08870', language: 'de', subject: 'Drucker druckt leere Seiten nach Treiber-Update',
    body: 'Seit dem Treiber-Update druckt der Drucker im 2. OG nur noch leere Seiten.',
    answer: 'Das Treiber-Update hat das Druckprofil auf einen falschen Papiertyp gesetzt. Bitte deinstallieren Sie den Treiber, installieren Sie Version 3.2 erneut und wählen Sie das Standardprofil. Danach druckte das Gerät wieder normal.',
    type: 'Incident', queue: 'IT Support', priority: 'low', tags: ['Hardware', 'Printer'],
  },
  {
    ticket_id: 'TKT-01877', language: 'en', subject: 'Remote access gateway unreachable',
    body: 'Remote desktop gateway times out for all staff working from home.',
    answer: 'The remote access gateway ran out of licences after a configuration change. We released stale sessions and increased the session pool; access was restored. Please reconnect and report any user who still cannot log in.',
    type: 'Incident', queue: 'Service Outages and Maintenance', priority: 'high', tags: ['Network', 'Outage', 'VPN'],
  },
  {
    ticket_id: 'TKT-03390', language: 'en', subject: 'Question about integration with our CRM',
    body: 'Does your platform integrate with our CRM, and what does it cost?',
    answer: 'Integration options depend on your plan. A solutions engineer will review your CRM version and contact you with the supported connectors.',
    type: 'Request', queue: 'Sales and Pre-Sales', priority: 'low', tags: ['Sales', 'Integration'],
  },
  {
    ticket_id: 'TKT-12011', language: 'de', subject: 'Synchronisation der Kalender schlägt fehl',
    body: 'Unsere Kalender synchronisieren seit gestern nicht mehr mit der App.',
    answer: 'Die Synchronisation scheiterte an einem abgelaufenen OAuth-Token. Bitte melden Sie sich in den App-Einstellungen ab und wieder an, um das Token zu erneuern.',
    type: 'Problem', queue: 'Product Support', priority: 'medium', tags: ['Bug', 'Sync'],
  },
  {
    ticket_id: 'TKT-10544', language: 'en', subject: 'Return label for damaged device',
    body: 'The tablet arrived with a cracked screen. How do I return it?',
    answer: 'We have emailed you a prepaid return label. Please pack the device in its original box; a replacement ships as soon as the courier scans the parcel.',
    type: 'Request', queue: 'Returns and Exchanges', priority: 'medium', tags: ['Returns', 'Hardware'],
  },
]

export const KB: KbRow[] = [...REAL, ...HAND_WRITTEN]
