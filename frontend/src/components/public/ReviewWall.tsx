import { Quote, Star } from 'lucide-react'

import { REVIEWS } from '../../content/social-proof'
import { cn } from '../../lib/cn'

/**
 * What families say.
 *
 * The quotes come from `content/social-proof.ts` and nothing is written here — a
 * testimonial hard-coded into a component is a testimonial nobody can audit
 * before launch. **The entries there are sample content, not real customers;**
 * that file's header carries the consent rules for replacing them.
 *
 * No `aggregateRating` JSON-LD is emitted, here or from the home page. A rating
 * in structured data is a factual claim to a search engine, and this one has not
 * been earned yet. `src/test/socialProof.test.tsx` keeps it that way.
 */

function Stars({ rating }: { rating: number }) {
  const rounded = Math.max(0, Math.min(5, Math.round(rating)))
  return (
    <div className="flex items-center gap-0.5" role="img" aria-label={`${rounded} out of 5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          aria-hidden="true"
          className={cn(
            'h-4 w-4',
            i < rounded ? 'fill-brand-500 text-brand-500' : 'fill-none text-border-strong',
          )}
        />
      ))}
    </div>
  )
}

export function ReviewWall() {
  if (REVIEWS.length === 0) return null

  return (
    <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {REVIEWS.map((review, i) => (
        <figure
          key={`${review.name}-${i}`}
          className={cn(
            'flex h-full flex-col rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card',
            // A green top edge on every card, so the band reads as brand rather
            // than as six neutral boxes.
            'relative overflow-hidden before:absolute before:inset-x-0 before:top-0 before:h-1',
            'before:bg-gradient-to-r before:from-brand-500 before:to-brand-300',
          )}
        >
          <Quote className="h-6 w-6 shrink-0 text-brand-300" aria-hidden="true" />
          <blockquote className="mt-3 flex-1 text-body text-text-secondary">
            &ldquo;{review.quote}&rdquo;
          </blockquote>
          <figcaption className="mt-5 flex items-center gap-3 border-t border-border-subtle pt-4">
            <span
              aria-hidden="true"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-body font-bold text-brand-700"
            >
              {review.name.charAt(0)}
            </span>
            <span className="min-w-0">
              <span className="block text-body font-semibold text-text-primary">{review.name}</span>
              <span className="block text-small text-text-muted">{review.context}</span>
            </span>
            <span className="ml-auto shrink-0">
              <Stars rating={review.rating} />
            </span>
          </figcaption>
        </figure>
      ))}
    </div>
  )
}
