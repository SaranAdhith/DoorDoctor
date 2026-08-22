import type { AssistantAnswer, AssistantMessage, AssistantSuggestion } from '../types'
import { api } from './client'

export const assistantApi = {
  ask: (question: string, patientId?: number | null) =>
    api.post<AssistantAnswer>('/assistant/ask', {
      question,
      patient_id: patientId ?? null,
    }),
  /** The caller's own history. The server never returns anyone else's. */
  conversations: () => api.get<AssistantMessage[]>('/assistant/conversations'),
  suggestions: (patientId?: number | null) =>
    api.get<AssistantSuggestion[]>(
      patientId ? `/assistant/suggestions?patient_id=${patientId}` : '/assistant/suggestions',
    ),
}
