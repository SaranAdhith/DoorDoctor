import { LegalPage, type LegalSection } from './LegalPage'

/**
 * Privacy policy.
 *
 * Written to describe what this build actually does — role-checked access,
 * hashed passwords, hashed and expiring reset links, no payment gateway — rather
 * than a generic template making promises the code does not keep. Where a right
 * is not yet self-service, it says so and gives the address to write to instead
 * of implying a button exists.
 */

const SECTIONS: LegalSection[] = [
  {
    heading: 'Who we are',
    paragraphs: [
      'DoorDoctor is an elderly home-care and monitoring service operating in Bengaluru, India, founded by Saran Adhith and Darren D’Souza. This policy explains what personal information we collect, why, who can see it, and what you can ask us to do with it.',
    ],
  },
  {
    heading: 'What we collect',
    paragraphs: ['We collect three kinds of information, and no more than we need for each.'],
    list: [
      'Account information — the name, email address and phone number of the family member who holds the account, and a hash of the password. We never store your password in a form we can read.',
      'Patient information — the name, age, address, conditions and prescribed medicines of the person receiving care, together with the monitoring ranges configured for them.',
      'Care records — visit times and check-ins, recorded vitals, medication doses marked as given, skipped or refused, nurse notes, and the alerts raised and how they were resolved.',
      'Enquiries — if you contact us through this website, the name, email, phone number, city and message you submit.',
    ],
  },
  {
    heading: 'Why we hold it',
    paragraphs: [
      'To deliver the care you are paying for, to check every recorded reading against the ranges set for that patient, to escalate anything outside them, to produce your summaries and reports, and to invoice you. We do not sell personal information, and we do not use your family’s care records to advertise to you.',
    ],
  },
  {
    heading: 'Who can see it',
    paragraphs: [
      'Access is enforced on our servers on every request, not merely hidden in the interface.',
    ],
    list: [
      'You, and any family members you have been given logins for, can see your own relative’s record and nothing else.',
      'The nurses assigned to your relative’s visits can see the information they need to carry out those visits.',
      'The DoorDoctor care team can see the records they need in order to work alerts and run the service.',
      'If your employer pays for your subscription, they are the payer and nothing more. They never see a reading, a visit, an alert or a report.',
    ],
  },
  {
    heading: 'The assistant',
    paragraphs: [
      'You can ask questions about your relative’s care in your own words. Those questions are answered from a package of information the server assembles for you, scoped to what you are permitted to see — another family’s patient is never part of it. Questions and answers are stored so you can look back at them, and only the person who asked can read them; there is no route that lets our staff read your conversation history.',
    ],
  },
  {
    heading: 'Where an external model is used',
    paragraphs: [
      'Some written summaries and answers can optionally be improved by a third-party language model. When that happens, only the already-assembled summary text is sent, and every result is checked before you see it — a result containing a number that was not in the source information is discarded rather than shown. The service is designed to work entirely without this, and it does: if the external model is unavailable or not configured, you get the same information, written by our own software.',
    ],
  },
  {
    heading: 'Payments',
    paragraphs: [
      'No payment gateway is integrated in the current build of this service. We do not collect, process or store card details anywhere in our systems. Invoices record what is owed and what has been paid; they contain no payment instrument data.',
    ],
  },
  {
    heading: 'Security',
    paragraphs: ['Specific measures, rather than a general assurance:'],
    list: [
      'Passwords are stored only as a one-way hash and are never recoverable by us.',
      'Password-reset links are stored only as a hash, expire after thirty minutes, work once, and are invalidated when a newer link is requested.',
      'Every request is authorised against the signed-in account’s role and its relationship to the record being asked for.',
      'Sensitive values such as reset links are redacted before any record of a message being sent is stored.',
    ],
  },
  {
    heading: 'How long we keep it',
    paragraphs: [
      'Care records are kept for as long as we are providing care to that person, and afterwards for as long as we are required to retain medical records. Enquiries submitted through this website are kept until they have been dealt with. Account information is kept while the account is open.',
    ],
  },
  {
    heading: 'Your rights',
    paragraphs: [
      'You can ask us for a copy of the information we hold about you and your relative, ask us to correct anything inaccurate, or ask us to delete information where we are not required to keep it. Self-service export and deletion are not yet built into the account area — until they are, write to us and we will handle the request by hand rather than pretending a button exists.',
    ],
  },
  {
    heading: 'Changes to this policy',
    paragraphs: [
      'If we change this policy in a way that affects what we do with your information, we will tell account holders directly rather than relying on you to re-read this page.',
    ],
  },
  {
    heading: 'Contact',
    paragraphs: [
      'Questions about this policy, or a request about your information, can be sent through the contact form on this site.',
    ],
  },
]

export function Privacy() {
  return (
    <LegalPage
      title="Privacy policy"
      path="/privacy"
      description="What personal and health information DoorDoctor collects, why we hold it, who can see it, how it is protected, and what you can ask us to do with it."
      intro="This describes what this service actually does with your information. Where something is not yet built, it says so rather than promising it."
      sections={SECTIONS}
    />
  )
}
