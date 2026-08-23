import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PartnerStrip } from '../components/public/PartnerStrip'
import { ReviewWall } from '../components/public/ReviewWall'
import { PARTNERS, REVIEWS, hasPlaceholders } from '../content/social-proof'

/**
 * The guard on the reviews and tie-up bands.
 *
 * These sections exist so the finished design can be judged before there is
 * anything real to put in them. The property worth locking is not how they look
 * — it is that scaffolding can never be presented as a genuine endorsement, and
 * that the notice saying so clears itself the moment real content lands rather
 * than needing someone to remember a second switch.
 */

describe('social proof placeholders', () => {
  it('warns on the review wall for as long as any quote is scaffolding', () => {
    render(<ReviewWall />)

    // Guarding the guard: if someone fills in real quotes, this assertion
    // should be deleted along with the flags, not quietly inverted.
    expect(hasPlaceholders(REVIEWS)).toBe(true)
    expect(screen.getByText(/Sample layout, not real reviews/i)).toBeInTheDocument()
  })

  it('warns on the partner strip for as long as any tie-up is scaffolding', () => {
    render(<PartnerStrip />)

    expect(hasPlaceholders(PARTNERS)).toBe(true)
    expect(screen.getByText(/Placeholders, not announced partners/i)).toBeInTheDocument()
  })

  it('drops the notice once every entry is real', () => {
    expect(hasPlaceholders([{ placeholder: true }, {}])).toBe(true)
    expect(hasPlaceholders([{}, {}])).toBe(false)
    expect(hasPlaceholders([])).toBe(false)
  })

  it('never claims a rating it did not collect', async () => {
    // `aggregateRating` in JSON-LD is a factual claim to a search engine.
    // Placeholder stars must not become one.
    const seo = await import('../components/public/Seo')
    expect(JSON.stringify(seo.ORGANISATION_JSON_LD)).not.toMatch(/aggregateRating|reviewCount/i)
  })
})
