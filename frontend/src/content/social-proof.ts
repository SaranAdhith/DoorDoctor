/**
 * Reviews and tie-ups for the public site.
 *
 * ---------------------------------------------------------------------------
 *  READ BEFORE LAUNCH — this is sample content, written to fill the design.
 * ---------------------------------------------------------------------------
 *
 * None of the people or organisations below exist. The names, quotes and
 * partnerships were written to show what the reviews and tie-up bands look like
 * populated, on the founder's instruction, and the on-page notices that used to
 * say so have been removed at their request. That makes this file the only place
 * the distinction is still recorded, so:
 *
 *   REVIEWS   — swap each entry for a real quote with the family's written
 *               consent to publish it, under the name and detail they agreed to.
 *               A review about a named relative's health is personal data;
 *               someone saying something kind on a call is not consent to print
 *               it. Do not raise a rating that did not come from a real review
 *               process, and do not add `aggregateRating` structured data — see
 *               `Seo.tsx`. `src/test/socialProof.test.tsx` locks that.
 *
 *   PARTNERS  — the organisation names here are invented on purpose, so that no
 *               real hospital's mark is used without an agreement. Replace them
 *               only with organisations that have signed one, in the form that
 *               agreement permits. A hospital named here implies a clinical
 *               relationship a family may rely on in an emergency.
 *
 * Misleading endorsements in Indian advertising fall under the ASCI code and the
 * Consumer Protection Act 2019 (§2(28)), and healthcare is where that is
 * enforced hardest. `SHOW_SOCIAL_PROOF = false` takes both bands off the site in
 * one edit if you would rather ship without them until the real thing exists.
 */

/** Master switch for the reviews and tie-up bands on the home page. */
export const SHOW_SOCIAL_PROOF = true

export interface Review {
  /** The quote itself. One or two sentences reads best in the card. */
  quote: string
  /** Who said it, as they agreed to be named. */
  name: string
  /** Their relationship to the patient, and where they are. */
  context: string
  /** 1–5. Only ever from a real review process. */
  rating: number
}

export const REVIEWS: readonly Review[] = [
  {
    quote:
      'My father tells me he is fine every single Sunday. The chart showed his blood pressure ' +
      'climbing for three weeks straight. We got his medication changed before it became the ' +
      'kind of thing you find out about from a hospital.',
    name: 'Priya Raghavan',
    context: 'Daughter · Indiranagar',
    rating: 5,
  },
  {
    quote:
      'What sold me was the medication log. I could finally see that Amma was skipping the ' +
      'evening dose — not guessing, not asking her and being told what she thought I wanted ' +
      'to hear. The nurse now sits with her for it.',
    name: 'Anil Kulkarni',
    context: 'Son · Jayanagar',
    rating: 5,
  },
  {
    quote:
      'I am eleven and a half hours ahead. Being able to read the visit notes at my breakfast, ' +
      'the same morning they were written, is the difference between worrying and knowing. ' +
      'The weekly summary is in plain English, which I did not expect.',
    name: 'Meera Nair',
    context: 'Daughter · Toronto',
    rating: 5,
  },
  {
    quote:
      'The nursing has been good and the record is genuinely useful. Scheduling was rocky for ' +
      'the first fortnight — two visits moved at short notice — though it has settled since, ' +
      'and they did call to explain rather than leaving us to notice.',
    name: 'Rakesh Menon',
    context: 'Son · Whitefield',
    rating: 4,
  },
  {
    quote:
      'My mother is eighty-four and will not touch a smartphone, which ruled out everything ' +
      'else we looked at. Nothing is asked of her at all. Someone comes, does the checks, and ' +
      'it appears on my phone.',
    name: 'Lakshmi Iyer',
    context: 'Daughter · HSR Layout',
    rating: 5,
  },
  {
    quote:
      'An oxygen reading came back low on a Tuesday afternoon. I had a call from their care ' +
      'team before I had finished reading the alert, and they had already spoken to his ' +
      'physician. That is the whole reason we pay for this.',
    name: 'Farhan Qureshi',
    context: 'Son · Koramangala',
    rating: 5,
  },
]

export type PartnerKind = 'hospital' | 'employer' | 'diagnostics' | 'residence'

export interface Partner {
  /** The organisation's name, exactly as the agreement permits it to appear. */
  name: string
  kind: PartnerKind
  /** What the tie-up actually covers. Be specific; vagueness reads as filler. */
  note: string
}

export const PARTNER_KIND_LABELS: Record<PartnerKind, string> = {
  hospital: 'Hospital',
  diagnostics: 'Diagnostics',
  employer: 'Employer',
  residence: 'Residence',
}

export const PARTNERS: readonly Partner[] = [
  {
    name: 'Sanjeevini Multispeciality',
    kind: 'hospital',
    note: 'Primary escalation route for south Bengaluru. Receives the patient’s record with the handover.',
  },
  {
    name: 'Ashraya Health City',
    kind: 'hospital',
    note: 'Second escalation route, so one hospital being full is never a single point of failure.',
  },
  {
    name: 'Chetana Diagnostics',
    kind: 'diagnostics',
    note: 'Home sample collection for the blood panels included in a plan, results into the same record.',
  },
  {
    name: 'Nexvia Technologies',
    kind: 'employer',
    note: 'Elder care offered to 400+ employees as a benefit, billed to the company.',
  },
  {
    name: 'Brightlane Consulting',
    kind: 'employer',
    note: 'Covering parents of staff posted outside Bengaluru.',
  },
  {
    name: 'Tulasi Senior Living',
    kind: 'residence',
    note: 'Clinical monitoring for every resident, priced per resident per day.',
  },
]
