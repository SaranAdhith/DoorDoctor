import { LegalPage, type LegalSection } from './LegalPage'

/**
 * Terms of service.
 *
 * The clinical-limits section is the one that matters and it is placed early
 * rather than buried: someone should not have to reach clause eleven to learn
 * that this is not an emergency service.
 */

const SECTIONS: LegalSection[] = [
  {
    heading: 'These terms',
    paragraphs: [
      'These terms govern your use of DoorDoctor’s home-care and monitoring service and this website. By subscribing to the service or submitting an enquiry, you accept them. DoorDoctor is operated from Bengaluru, India.',
    ],
  },
  {
    heading: 'What the service is',
    paragraphs: [
      'DoorDoctor provides scheduled visits to a patient’s home by a qualified nurse, records the observations made during those visits, compares recorded readings against monitoring thresholds configured for that patient, raises alerts when a reading falls outside them, and makes the resulting record available to the family members authorised to see it.',
    ],
  },
  {
    heading: 'What the service is not',
    paragraphs: ['These limits are part of the agreement, not disclaimers appended to it.'],
    list: [
      'DoorDoctor is not an emergency service. If a person requires immediate medical attention, call 108. Do not rely on DoorDoctor, an alert, or a message to us to summon emergency help.',
      'DoorDoctor does not provide medical diagnosis. An alert indicates that a recorded reading fell outside a configured threshold. It is not a clinical finding and must not be treated as one.',
      'DoorDoctor does not prescribe medication and does not alter any prescription. Our nurses supervise doses already prescribed by a treating doctor and record what was taken.',
      'DoorDoctor does not provide continuous or live-in care. The service consists of visits at the frequency your plan covers.',
      'DoorDoctor does not provide hospital-level treatment at home.',
    ],
  },
  {
    heading: 'Your responsibilities',
    list: [
      'Give us accurate information about the patient, including their conditions and current medicines, and tell us when it changes. Threshold monitoring is only as good as the information the thresholds were set from.',
      'Ensure the patient consents to being visited. A nurse cannot provide care to someone who does not wish to receive it.',
      'Provide safe access to the home at the scheduled time, and a local emergency contact — particularly if you live outside India.',
      'Keep your account credentials to yourself. Anyone signed in to your account can see your relative’s complete health record.',
    ],
  },
  {
    heading: 'Subscriptions and billing',
    list: [
      'Plans are sold per patient, monthly or annually. An annual plan is charged for ten months rather than twelve.',
      'You are invoiced at the start of each billing period. Invoices are available to download from your account.',
      'You may change plan at any time. Moving to a higher plan takes effect immediately and the unused portion of the current period is credited against the change.',
      'You may cancel at any time. Cancellation takes effect at the end of the period you have already paid for; we do not refund a period part-way through unless we have failed to deliver the service.',
      'Credits earned from referrals or from the loyalty reward are applied automatically to your next invoice. They have no cash value and are not refundable.',
      'No payment gateway is integrated in the current build of this service, and no card details are collected or stored.',
    ],
  },
  {
    heading: 'Cancellation by us',
    paragraphs: [
      'We may end a subscription where a home is unsafe for our staff to enter, where a patient does not consent to being visited, where an account is used to obtain information about someone other than the patient it covers, or where invoices go unpaid after we have asked. Where we end a subscription for any reason other than misuse, we refund the unused part of the period.',
    ],
  },
  {
    heading: 'Availability',
    paragraphs: [
      'We aim to keep the platform available continuously, but we do not guarantee uninterrupted access, and you must not treat the absence of an alert as confirmation that a patient is well. Alerts depend on a reading having been taken; between visits, no reading exists to evaluate.',
    ],
  },
  {
    heading: 'Liability',
    paragraphs: [
      'Nothing in these terms limits liability for death or personal injury caused by our negligence, for fraud, or for anything else that cannot lawfully be limited. Subject to that, our liability arising from the service is limited to the fees you paid in the twelve months before the claim, and we are not liable for indirect or consequential loss.',
      'You accept that the service is a monitoring and coordination layer and not a substitute for medical care, emergency services, or the clinical judgement of a treating doctor.',
    ],
  },
  {
    heading: 'Your information',
    paragraphs: [
      'How we handle personal and health information is set out in our privacy policy, which forms part of these terms.',
    ],
  },
  {
    heading: 'Changes',
    paragraphs: [
      'We may update these terms. If a change materially affects your rights or what the service does, we will tell account holders directly and give reasonable notice before it takes effect.',
    ],
  },
  {
    heading: 'Governing law',
    paragraphs: [
      'These terms are governed by the laws of India, and the courts at Bengaluru have exclusive jurisdiction over any dispute arising from them.',
    ],
  },
  {
    heading: 'Contact',
    paragraphs: ['Questions about these terms can be sent through the contact form on this site.'],
  },
]

export function Terms() {
  return (
    <LegalPage
      title="Terms of service"
      path="/terms"
      description="The terms governing DoorDoctor's home nursing and monitoring service, including what the service does and does not do, billing, cancellation and liability."
      intro="What you are agreeing to, and — just as importantly — what this service does not do. The clinical limits are stated near the top rather than buried."
      sections={SECTIONS}
    />
  )
}
