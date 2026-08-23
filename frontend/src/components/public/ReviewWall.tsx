import { Quote, Star } from 'lucide-react'

import { REVIEWS, hasPlaceholders } from '../../content/social-proof'
import { cn } from '../../lib/cn'

/**
 * What families say.
 *
 * The quotes come from `content/social-proof.ts` and nothing is written here —
 * a testimonial hard-coded into a component is a testimonial nobody can audit
 * before launch.
 *
 * Two rules this component enforces rather than trusts:
 *
 *  - While any entry is still `placeholder`, a notice renders above the grid
 *    saying so. Sample text cannot be mistaken for a real endorsement, and the
 *    notice removes itself as the flags come off.
 *  - No `aggregateRating` JSON-LD is emitted, here or from the home page. A
 *    rating in structured data is a factual claim to a search engine, and this
 *    one has not been earned yet.
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
    <>
      {hasPlaceholders(REVIEWS) && (
        <p className="mt-8 rounded-xl border border-status-watch-border bg-status-watch-bg px-4 py-3 text-small text-status-watch">
          <span className="font-semibold">Sample layout, not real reviews.</span> DoorDoctor is
          pre-launch. These cards show where families&rsquo; own words will go once we have them,
          with their consent — nothing here is a quote from a real customer.
        </p>
      )}

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        {REVIEWS.map((review, i) => (
          <figure
            key={`${review.name}-${i}`}
            className="flex h-full flex-col rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card"
          >
            <Quote className="h-6 w-6 shrink-0 text-brand-200" aria-hidden="true" />
            <blockquote className="mt-3 flex-1 text-body text-text-secondary">
              &ldquo;{review.quote}&rdquo;
            </blockquote>
            <figcaption className="mt-5 border-t border-border-subtle pt-4">
              <Stars rating={review.rating} />
              <p className="mt-2 text-body font-semibold text-text-primary">{review.name}</p>
              <p className="text-small text-text-muted">{review.context}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </>
  )
}
