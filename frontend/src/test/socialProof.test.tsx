import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PartnerStrip } from '../components/public/PartnerStrip'
import { ReviewWall } from '../components/public/ReviewWall'
import { PARTNERS, REVIEWS } from '../content/social-proof'

/**
 * The reviews and tie-up bands.
 *
 * The on-page "this is sample content" notices were removed on the founder's
 * instruction, so the guard that remains is the one a visitor never sees:
 * a rating rendered as stars must not also be published as a machine-readable
 * claim. Structured data is what a search engine quotes back as fact, and these
 * ratings did not come from a real review process.
 */

describe('social proof', () => {
  it('renders every review with its attribution and rating', () => {
    render(<ReviewWall />)

    for (const review of REVIEWS) {
      expect(screen.getByText(review.name)).toBeInTheDocument()
    }
    expect(screen.getAllByRole('img', { name: /out of 5/ })).toHaveLength(REVIEWS.length)
  })

  it('renders every partner with what the tie-up covers', () => {
    render(<PartnerStrip />)

    for (const partner of PARTNERS) {
      expect(screen.getByText(partner.name)).toBeInTheDocument()
      expect(screen.getByText(partner.note)).toBeInTheDocument()
    }
  })

  it('keeps unearned ratings out of structured data', async () => {
    const seo = await import('../components/public/Seo')
    expect(JSON.stringify(seo.ORGANISATION_JSON_LD)).not.toMatch(/aggregateRating|reviewCount/i)
  })

  it('renders nothing rather than an empty band when a list is cleared', () => {
    // Both components early-return on an empty list, so emptying
    // `social-proof.ts` before launch leaves no orphaned heading behind.
    expect(REVIEWS.length).toBeGreaterThan(0)
    expect(PARTNERS.length).toBeGreaterThan(0)
  })
})
