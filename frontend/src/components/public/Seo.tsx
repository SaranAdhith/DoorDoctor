import { Helmet } from 'react-helmet-async'

/**
 * Per-route document head.
 *
 * One component so no page hand-writes a meta tag: a title that forgets the
 * brand suffix, or an Open Graph card that quietly disagrees with the page
 * description, is exactly the kind of drift a shared component prevents.
 */

const SITE_NAME = 'DoorDoctor'
const TITLE_SUFFIX = 'DoorDoctor — Elderly Healthcare at Home'

/**
 * Canonical URLs need an origin, and a static build does not know its own.
 * `window.location.origin` is right in the browser, and the fallback keeps
 * `Seo` renderable under jsdom in tests.
 */
const ORIGIN = typeof window === 'undefined' ? 'https://doordoctor.in' : window.location.origin

interface Props {
  /** Page title without the brand. Omit on the home page, which is the brand. */
  title?: string
  description: string
  /** Path only, e.g. `/pricing`. The origin is added here. */
  path: string
  /** Optional JSON-LD. Objects only — this is serialised, never interpolated. */
  jsonLd?: Record<string, unknown>
  /** Keeps a thin page (privacy, terms) out of search results if ever needed. */
  noIndex?: boolean
}

export function Seo({ title, description, path, jsonLd, noIndex = false }: Props) {
  const fullTitle = title ? `${title} · ${TITLE_SUFFIX}` : TITLE_SUFFIX
  const canonical = `${ORIGIN}${path}`

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonical} />
      {noIndex && <meta name="robots" content="noindex,follow" />}

      <meta property="og:type" content="website" />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={canonical} />

      <meta name="twitter:card" content="summary" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />

      {jsonLd && <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>}
    </Helmet>
  )
}

/**
 * The organisation card, emitted once from the home page.
 *
 * Deliberately minimal: name, what it is, where it operates, and both founders.
 * No `aggregateRating`, no `review`, no `numberOfEmployees` — structured data is
 * still a claim, and DoorDoctor is pre-launch.
 */
export const ORGANISATION_JSON_LD: Record<string, unknown> = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'DoorDoctor',
  description:
    'Scheduled home nurse visits for elderly parents, with recorded vitals, medication ' +
    'supervision and threshold-based escalation visible to the family.',
  areaServed: { '@type': 'City', name: 'Bengaluru' },
  founder: [
    { '@type': 'Person', name: 'Saran Adhith', jobTitle: 'Founder & CEO' },
    { '@type': 'Person', name: "Darren D'Souza", jobTitle: 'Co-Founder' },
  ],
}

/** FAQ structured data, built from the same array the page renders. */
export function faqJsonLd(items: { question: string; answer: string }[]): Record<string, unknown> {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  }
}
