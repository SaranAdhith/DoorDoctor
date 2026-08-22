import { Plus } from 'lucide-react'

/**
 * Questions and answers, built on `<details>`.
 *
 * A native disclosure rather than a hand-rolled accordion: it is keyboard
 * operable, announced correctly, and findable by the browser's own in-page
 * search even while collapsed — which a `useState`-driven version is not.
 */

export interface FaqItem {
  question: string
  answer: string
}

export function FaqList({ items, idPrefix = 'faq' }: { items: FaqItem[]; idPrefix?: string }) {
  return (
    <div className="divide-y divide-border-subtle border-y border-border-subtle">
      {items.map((item, index) => (
        <details key={item.question} className="group" id={`${idPrefix}-${index}`}>
          <summary className="flex cursor-pointer list-none items-start justify-between gap-4 py-5 text-left">
            <span className="text-body font-semibold text-text-primary">{item.question}</span>
            <Plus
              className="mt-0.5 h-5 w-5 shrink-0 text-text-muted transition-transform group-open:rotate-45"
              aria-hidden="true"
            />
          </summary>
          <p className="max-w-3xl pb-5 text-body text-text-secondary">{item.answer}</p>
        </details>
      ))}
    </div>
  )
}
