import { AssistantPanel } from '../../components/assistant/AssistantPanel'

/**
 * "Ask DoorDoctor" for an admin.
 *
 * Org-wide rather than patient-scoped, and it reads the same records the
 * dashboards do — the board, the alert queue, the roster and the revenue
 * summary. No emergency block: an admin's escalation path runs through the alert
 * queue, and the assistant still returns 108 first if a question describes one.
 */
export function AdminAssistant() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Ask DoorDoctor</h1>
        <p className="mt-1 text-small text-text-secondary">
          Today's board, the alert queue, nurse workload and revenue — in one question.
        </p>
      </div>

      <AssistantPanel intro="Ask about operations, the roster or the business." />
    </div>
  )
}
