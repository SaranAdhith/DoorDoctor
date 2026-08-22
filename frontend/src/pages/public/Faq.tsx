import {
  CtaBand,
  FaqList,
  PageHero,
  Section,
  SectionHeading,
  Seo,
  faqJsonLd,
  type FaqItem,
} from '../../components/public'

/**
 * The FAQ.
 *
 * Grouped, and the groups are rendered from one array so the JSON-LD emitted for
 * search engines is built from exactly the questions on the page — a structured
 * answer that differs from the visible one is a quiet way to mislead.
 */

const GROUPS: { title: string; items: FaqItem[] }[] = [
  {
    title: 'The service',
    items: [
      {
        question: 'What exactly does a visit involve?',
        answer:
          'A qualified nurse arrives at the home and checks in on site. They record vitals — blood pressure, pulse, blood sugar, oxygen saturation, temperature and weight — supervise the medicines that are due, and write a short note on how your parent seemed. Every reading is checked against the ranges configured for that patient as it is entered.',
      },
      {
        question: 'Who are the nurses?',
        answer:
          'Registered nurses and auxiliary nurse midwives. Their qualification is recorded and their credentials are verified before they are assigned to a patient, and you can see who is assigned to each visit.',
      },
      {
        question: 'Will it be the same nurse every time?',
        answer:
          'Usually. Visits are routed by area, so a small group of nurses covers each neighbourhood. We cannot promise the same person every single visit — leave and illness exist — but continuity is something we plan for rather than leave to chance.',
      },
      {
        question: 'Which areas do you cover?',
        answer:
          'Bengaluru. If your parents live elsewhere, tell us where and we will tell you honestly whether we can help rather than taking the enquiry anyway.',
      },
      {
        question: 'Do my parents need a smartphone?',
        answer:
          'No. Nothing about the service requires them to own a device or learn an app. The nurse records the visit; you read it. That is deliberate — services that depend on an elderly person operating an app tend to stop being used in month two.',
      },
      {
        question: 'Can you look after both my parents?',
        answer:
          'Yes. Each plan covers one person, so mention both when you enquire and we will price it properly rather than defaulting you to two full plans.',
      },
    ],
  },
  {
    title: 'Alerts and emergencies',
    items: [
      {
        question: 'What happens if a reading is abnormal?',
        answer:
          'An alert is raised automatically the moment the reading is entered, recording which measurement was outside its range. You and our care team are notified at the same time, and the alert stays open until an admin has worked it and closed it with a note describing what was done.',
      },
      {
        question: 'Is DoorDoctor an emergency service?',
        answer:
          'No, and this matters. We are a monitoring and coordination service. If someone needs medical help immediately, call 108. We are not an ambulance service and we do not want anyone waiting on us in a situation where minutes count.',
      },
      {
        question: 'Does an alert mean something is wrong?',
        answer:
          'It means a reading fell outside the range configured for that patient. That is a signal to look, not a diagnosis. Some alerts turn out to be a cuff on the wrong arm; some turn out to matter a great deal. A clinician decides which.',
      },
      {
        question: 'Do your nurses prescribe or change medication?',
        answer:
          'No. Our nurses record, supervise the doses already prescribed, and escalate. Changing a prescription is a doctor’s decision and nothing on our platform will ever do it.',
      },
    ],
  },
  {
    title: 'Pricing and billing',
    items: [
      {
        question: 'Is there a joining fee or a lock-in?',
        answer:
          'No joining fee, and no lock-in on the monthly plans. Cancelling takes effect at the end of the period you have already paid for.',
      },
      {
        question: 'What does paying annually save?',
        answer:
          'An annual plan costs ten months rather than twelve, so two months are free. Everything included is otherwise identical.',
      },
      {
        question: 'Can I change plan?',
        answer:
          'At any time, from inside your account. Moving up takes effect immediately and the unused part of the current month is credited against the change, so you are never billed twice for the same days.',
      },
      {
        question: 'Do you offer anything for referrals or long-standing customers?',
        answer:
          'Yes to both. Referring a family who joins and pays earns you a credit, and staying for twelve paid months earns a loyalty credit. Both are applied automatically to your next invoice — there is no code to remember or claim to file.',
      },
    ],
  },
  {
    title: 'Privacy and access',
    items: [
      {
        question: 'Who can see my parent’s record?',
        answer:
          'You, the nurses assigned to their visits, and the DoorDoctor care team who work their alerts. Access is checked on the server on every request, so a family account cannot reach another family’s patient at all.',
      },
      {
        question: 'Can other family members have access?',
        answer:
          'Yes. Every plan includes logins for more than one family member, so siblings can share the account instead of forwarding each other screenshots.',
      },
      {
        question: 'If my employer pays, can they see my parent’s health data?',
        answer:
          'No. An employer is the payer and nothing more. Their invoice tells them how many employees are enrolled and nothing else — no readings, no visits, no alerts, no reports.',
      },
      {
        question: 'Are you storing my card details?',
        answer:
          'No payment gateway is integrated in the current build, so no card details are collected or stored anywhere in our systems.',
      },
    ],
  },
]

const ALL_ITEMS = GROUPS.flatMap((group) => group.items)

export function Faq() {
  return (
    <>
      <Seo
        title="Frequently asked questions"
        description="Common questions about DoorDoctor: what a visit involves, who the nurses are, how alerts and escalation work, pricing and billing, and who can see your parent's record."
        path="/faq"
        jsonLd={faqJsonLd(ALL_ITEMS)}
      />

      <PageHero
        eyebrow="FAQ"
        title="Questions people actually ask"
        description="If yours is not here, send it — the awkward ones are the ones worth asking before you sign up."
      />

      {GROUPS.map((group, index) => (
        <Section key={group.title} tone={index % 2 === 0 ? 'default' : 'sunken'}>
          <SectionHeading title={group.title} as="h2" />
          <div className="mt-6">
            <FaqList items={group.items} idPrefix={`faq-${index}`} />
          </div>
        </Section>
      ))}

      <CtaBand
        title="Still wondering about something?"
        description="Ask us directly. We will give you a straight answer, including when the answer is that we are not the right fit."
        secondaryLabel="Trust and safety"
        secondaryTo="/trust-and-safety"
      />
    </>
  )
}
