import { PageHero, Section, Seo } from '../../components/public'

/**
 * The shared shell for the privacy policy and the terms.
 *
 * Long-form legal prose is the one place on a marketing site where the layout
 * should get out of the way entirely: a narrow measure, a plain heading scale
 * and nothing else. Both pages share it so they cannot drift into two different
 * typographic treatments of the same kind of document.
 */

export interface LegalSection {
  heading: string
  paragraphs?: string[]
  list?: string[]
}

interface Props {
  title: string
  path: string
  description: string
  intro: string
  sections: LegalSection[]
}

export function LegalPage({ title, path, description, intro, sections }: Props) {
  return (
    <>
      <Seo title={title} description={description} path={path} />

      <PageHero eyebrow="Legal" title={title} description={intro} />

      <Section tone="default" narrow>
        <div className="space-y-10">
          {sections.map((section, index) => (
            <section key={section.heading} aria-labelledby={`legal-${index}`}>
              <h2
                id={`legal-${index}`}
                className="text-h2 font-bold tracking-tight text-text-primary"
              >
                {section.heading}
              </h2>

              {section.paragraphs?.map((paragraph) => (
                <p key={paragraph} className="mt-3 text-body leading-7 text-text-secondary">
                  {paragraph}
                </p>
              ))}

              {section.list && (
                <ul className="mt-4 space-y-2.5">
                  {section.list.map((item) => (
                    <li key={item} className="flex gap-3 text-body leading-7 text-text-secondary">
                      <span
                        className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-border-strong"
                        aria-hidden="true"
                      />
                      {item}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>

        <p className="mt-12 border-t border-border-subtle pt-6 text-small text-text-muted">
          DoorDoctor is a healthcare monitoring and coordination service, not an emergency service
          and not a provider of medical diagnosis. In an emergency, call{' '}
          <a href="tel:108" className="font-semibold text-status-critical underline">
            108
          </a>
          .
        </p>
      </Section>
    </>
  )
}
