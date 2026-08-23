export type Role = 'family' | 'nurse' | 'admin'

export interface User {
  id: number
  name: string
  email: string
  phone: string | null
  role: Role
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ForgotPasswordResponse {
  message: string
  /** Development builds only, so the demo works without a mail provider. */
  debug_reset_url: string | null
}

export interface ResetPasswordResponse {
  message: string
}

export interface ResetTokenStatus {
  valid: boolean
}

export interface Patient {
  id: number
  name: string
  age: number
  gender: string
  address: string
  emergency_contact: string | null
  family_user_id: number
  status: string
  created_at: string
}

export type VitalMetric =
  | 'systolic_bp'
  | 'diastolic_bp'
  | 'heart_rate'
  | 'blood_glucose'
  | 'spo2'
  | 'temperature'
  | 'weight'

export interface Vitals {
  id: number
  patient_id: number
  visit_id: number | null
  systolic_bp: number
  diastolic_bp: number
  heart_rate: number
  blood_glucose: number
  spo2: number
  temperature: number
  weight: number
  threshold_breached: boolean
  recorded_at: string
}

export interface Threshold {
  id?: number
  patient_id?: number
  metric: VitalMetric
  low_threshold: number | null
  high_threshold: number | null
  enabled: boolean
}

export type VisitStatus = 'scheduled' | 'in_progress' | 'completed' | 'missed' | 'cancelled'

export interface Visit {
  id: number
  patient_id: number
  nurse_id: number | null
  scheduled_at: string
  status: VisitStatus
  checkin_at: string | null
  checkout_at: string | null
  location_source: string
  notes: string | null
  patient?: { id: number; name: string; age: number; address: string }
  nurse?: { id: number; name: string; credential: string; phone: string | null }
  nurse_name?: string | null
}

export interface VisitDetail extends Visit {
  vitals: Vitals[]
  medications: Medication[]
  medication_logs: MedicationLog[]
}

export interface Medication {
  id: number
  patient_id: number
  name: string
  dosage: string
  frequency: string
  scheduled_time: string
  active: boolean
}

export type MedicationLogStatus = 'administered' | 'skipped' | 'refused'

export interface MedicationLog {
  id: number
  medication_id: number
  medication_name?: string | null
  visit_id: number | null
  status: MedicationLogStatus
  reason: string | null
  recorded_at: string
}

export interface Adherence {
  percentage: number | null
  administered: number
  skipped: number
  refused: number
  total: number
}

export type AlertSeverity = 'info' | 'warning' | 'critical'
export type AlertStatus = 'active' | 'acknowledged' | 'resolved'

export interface BreachedParameter {
  metric: VitalMetric
  value: number
  threshold: number
  direction: 'above' | 'below'
  unit: string
}

export interface Alert {
  id: number
  patient_id: number
  vitals_id: number | null
  alert_type: string
  severity: AlertSeverity
  title: string
  message: string
  breached_parameters: BreachedParameter[]
  status: AlertStatus
  acknowledged_by: number | null
  acknowledged_at: string | null
  resolved_at: string | null
  created_at: string
}

export interface AlertDetail extends Alert {
  patient_name: string | null
  nurse_name: string | null
  vitals: Vitals | null
  thresholds: Threshold[]
}

export interface Nurse {
  id: number
  user_id: number
  name: string
  email: string
  phone: string | null
  credential: string
  verification_status: string
  status: string
  open_visits?: number
}

export interface Notification {
  id: number
  user_id: number
  patient_id: number | null
  alert_id: number | null
  type: string
  title: string
  message: string
  read: boolean
  created_at: string
}

export interface Dashboard {
  patient: Patient
  current_vitals: Vitals | null
  vitals_history: Vitals[]
  medication_adherence: Adherence
  medications: Medication[]
  upcoming_visits: Visit[]
  recent_visits: Visit[]
  active_alerts: Alert[]
  nurse: Nurse | null
  overall_status: 'Stable' | 'Attention Required' | 'Critical Alert'
  thresholds: Threshold[]
}

// ---------------------------------------------------------------------------
// Plain-language summary and reports (Phase 6)
// ---------------------------------------------------------------------------

export type SummaryWindow = '7d' | '30d' | '90d'

/** `tone` drives colour, so it is a closed set on the server too. */
export interface SummaryHighlight {
  tone: 'good' | 'watch' | 'attention'
  text: string
}

export interface PlainSummary {
  patient_id: number
  patient_name: string
  window: SummaryWindow
  window_label: string
  headline: string
  paragraphs: string[]
  highlights: SummaryHighlight[]
  what_happens_next: string[]
  reading_count: number
  dose_count: number
  visit_count: number
  flagged_count: number
  open_alert_count: number
  generated_at: string
  /**
   * Honest provenance. `deterministic` is the normal case, not a degraded one —
   * the platform is built to run with no model configured at all.
   */
  source: 'deterministic' | 'assisted'
  disclaimer: string
}

export type ReportKind = 'weekly' | 'monthly' | 'on_demand'

export interface Report {
  id: number
  patient_id: number
  patient_name: string | null
  kind: ReportKind
  title: string
  period_start: string
  period_end: string
  headline: string
  paragraphs: string[]
  highlights: SummaryHighlight[]
  what_happens_next: string[]
  reading_count: number
  dose_count: number
  visit_count: number
  generated_at: string
}

export interface AdminSummary {
  patients: number
  nurses: number
  today_visits: number
  active_alerts: number
  completed_today: number
}

export interface VitalsSubmission {
  systolic_bp: number
  diastolic_bp: number
  heart_rate: number
  blood_glucose: number
  spo2: number
  temperature: number
  weight: number
}

export interface VitalsRecordResult {
  vitals: Vitals
  threshold_breached: boolean
  breached_parameters: BreachedParameter[]
  alerts_created: Alert[]
}

// ---------------------------------------------------------------------------
// Subscriptions and billing (Phase 4)
//
// Every money field is an integer count of paise and is named `*_paise`, so the
// unit is impossible to mistake. Format them with `lib/money.ts`, never by hand.
// ---------------------------------------------------------------------------

export type PlanAudience = 'individual' | 'corporate' | 'institution'
export type BillingCycle = 'monthly' | 'annual'
export type SubscriptionStatus = 'active' | 'past_due' | 'cancelled' | 'expired'
export type InvoiceStatus = 'draft' | 'issued' | 'paid' | 'void'
export type ReferralStatus = 'pending' | 'joined' | 'rewarded' | 'expired'

/**
 * Entitlements are data on the plan, so this is an open record rather than a
 * fixed shape — Phase 9 adds keys without changing this type. The keys Phase 4
 * defines are declared explicitly for the screens that read them.
 */
export interface Entitlements {
  visits_per_month?: number | null
  telemedicine_per_month?: number | null
  lab_panels_per_year?: number | null
  care_manager?: 'shared' | 'dedicated' | null
  care_manager_ratio?: number
  report_cadence?: 'monthly' | 'weekly'
  family_seats?: number
  priority_escalation?: boolean
  ai_assistant?: boolean
  [key: string]: string | number | boolean | null | undefined
}

export interface Plan {
  id: number
  code: string
  name: string
  audience: PlanAudience
  tagline: string
  monthly_paise: number
  annual_paise: number | null
  recommended: boolean
  unit_label: string | null
  unit_included: number | null
  unit_paise: number | null
  unit_period: string | null
  entitlements: Entitlements
}

export interface Quota {
  quota: string
  label: string
  period: 'month' | 'year'
  /** `null` means unlimited — for the allowance and for what is left of it. */
  limit: number | null
  used: number
  remaining: number | null
  unlimited: boolean
  period_start: string
  period_end: string
}

export interface Subscription {
  id: number
  status: SubscriptionStatus
  billing_cycle: BillingCycle
  seats: number
  started_at: string
  current_period_start: string
  current_period_end: string
  /** Null once a cancellation is pending — there is nothing left to renew. */
  renews_at: string | null
  paid_months: number
  cancel_at_period_end: boolean
  cancelled_at: string | null
  owner_label: string
  family_user_id: number | null
  organization_id: number | null
  period_price_paise: number
  credit_balance_paise: number
  months_to_loyalty_reward: number
  plan: Plan
  quotas: Quota[]
}

export interface InvoiceLine {
  id: number
  description: string
  kind: string
  quantity: number
  unit_paise: number
  amount_paise: number
}

export interface AppliedCredit {
  id: number
  kind: 'referral' | 'loyalty' | 'adjustment'
  reason: string
  amount_paise: number
}

export interface Invoice {
  id: number
  number: string
  subscription_id: number
  plan_name: string
  billed_to: string
  period_start: string
  period_end: string
  issued_at: string
  due_at: string
  subtotal_paise: number
  credit_paise: number
  total_paise: number
  status: InvoiceStatus
  paid_at: string | null
  payment_reference: string | null
  lines: InvoiceLine[]
  credits: AppliedCredit[]
}

export interface Referral {
  id: number
  /** Partially masked by the server. */
  email: string
  status: ReferralStatus
  reward_paise: number
  created_at: string
  joined_at: string | null
  rewarded_at: string | null
}

export interface ReferralSummary {
  code: string
  share_url: string
  reward_months: number
  reward_paise: number
  friend_credit_paise: number
  total_earned_paise: number
  joined_count: number
  pending_count: number
  referrals: Referral[]
}

export interface PlanRevenue {
  plan: string
  subscribers: number
  mrr_paise: number
}

export interface RevenueSummary {
  mrr_paise: number
  arr_paise: number
  active_subscriptions: number
  cancelled_subscriptions: number
  pending_cancellations: number
  collected_all_time_paise: number
  collected_this_month_paise: number
  outstanding_paise: number
  overdue_paise: number
  credits_outstanding_paise: number
  arpu_paise: number
  by_plan: PlanRevenue[]
}

// --- Assistant (Phase 7) ---------------------------------------------------

/** Honest provenance. `deterministic` is the normal case, not a degraded one. */
export type AssistantSource = 'deterministic' | 'assisted'

export interface AssistantAnswer {
  id: number
  question: string
  answer: string
  intent: string
  intent_title: string
  source: AssistantSource
  /** Matched deterministically and never sent to a model. Drives the alert treatment. */
  is_emergency: boolean
  patient_id: number | null
  disclaimer: string
  suggestions: string[]
  created_at: string
}

export interface AssistantMessage {
  id: number
  question: string
  answer: string
  intent: string
  intent_title: string
  source: AssistantSource
  is_emergency: boolean
  patient_id: number | null
  created_at: string
}

export interface AssistantSuggestion {
  intent: string
  title: string
  question: string
}

// --------------------------------------------------------------------------
// Public site and lead capture (Phase 8, §2.6)
// --------------------------------------------------------------------------

export interface AddOn {
  code: string
  name: string
  price_paise: number
  unit: string
}

/**
 * The payload behind every public pricing page.
 *
 * The pricing pages render *this*, never a number typed into a component —
 * `backend/app/core/pricing.py` is the only place a price is written down, and
 * the whole point of fetching it is that a marketing page cannot drift from the
 * invoice.
 */
export interface PublicPlans {
  plans: Plan[]
  add_ons: AddOn[]
  /** Behind the "2 months free" claim, so the words cannot outlive the offer. */
  annual_months_free: number
}

export type LeadKind = 'family' | 'corporate' | 'institution' | 'nri' | 'other'
export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'closed'

export interface Lead {
  id: number
  name: string
  email: string
  phone: string | null
  city: string | null
  kind: LeadKind
  message: string | null
  source_page: string | null
  status: LeadStatus
  admin_note: string | null
  handled_by: string | null
  handled_at: string | null
  created_at: string
}

export interface LeadSummary {
  total: number
  new: number
  contacted: number
  qualified: number
  closed: number
  by_kind: Record<string, number>
}

/** What the public form sends. `company_website` is the honeypot — never filled. */
export interface LeadSubmission {
  name: string
  email: string
  phone?: string
  city?: string
  kind: LeadKind
  message?: string
  source_page?: string
  company_website?: string
}

/* ------------------------------------------------------------------ */
/* Clinical (Phase 9, §4.2-4.9)                                        */
/*                                                                     */
/* No clinical constant is written on this side. Weights, reference    */
/* ranges, SLA durations and the emergency ladder are all served from  */
/* `backend/app/core/clinical.py`, exactly as no rupee figure is typed */
/* into the frontend. These are the shapes they arrive in.             */
/* ------------------------------------------------------------------ */

export type SafetyBandTone = 'good' | 'watch' | 'attention' | 'critical'

export interface SafetyComponent {
  key: string
  label: string
  blurb: string
  weight: number
  /** Null when this component had no data — which is not zero. */
  value: number | null
  points: number | null
  detail: string
  has_data: boolean
}

export interface SafetyScore {
  patient_id: number
  /** False when too little of the scale had data to publish a score at all. */
  available: boolean
  score: number | null
  band: string | null
  band_label: string | null
  band_tone: SafetyBandTone | null
  band_blurb: string | null
  window_days: number
  covered_weight: number
  total_weight: number
  previous_score: number | null
  delta: number | null
  components: SafetyComponent[]
  calculated_at: string
  unavailable_reason: string | null
}

export interface SafetyHistoryPoint {
  id: number
  score: number
  band: string
  calculated_at: string
}

export type LabFlag = 'normal' | 'low' | 'high' | 'critical_low' | 'critical_high' | 'unknown'
export type LabOrderStatus = 'ordered' | 'collected' | 'resulted' | 'cancelled'

export interface LabAnalyte {
  code: string
  label: string
  unit: string
  ref_low: number | null
  ref_high: number | null
}

export interface LabPanel {
  code: string
  name: string
  description: string
  turnaround_hours: number
  price_paise: number
  addon_code: string
  analytes: LabAnalyte[]
}

export interface LabResult {
  id: number
  analyte_code: string
  label: string
  value: number
  unit: string
  /** The range this value was judged against, stored at result time. */
  ref_low: number | null
  ref_high: number | null
  flag: LabFlag
  is_abnormal: boolean
  description: string
}

export interface LabOrder {
  id: number
  patient_id: number
  patient_name: string | null
  panel_code: string
  panel_name: string
  status: LabOrderStatus
  billing: 'entitlement' | 'addon'
  price_paise: number
  invoice_line_id: number | null
  ordered_at: string
  collected_at: string | null
  reported_at: string | null
  cancelled_at: string | null
  notes: string | null
  abnormal_count: number
  results: LabResult[]
}

export type ConsultStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'

export interface Consult {
  id: number
  patient_id: number
  patient_name: string | null
  scheduled_for: string
  duration_minutes: number
  status: ConsultStatus
  reason: string
  doctor_name: string
  cancelled_at: string | null
  cancellation_reason: string | null
  quota_released: boolean
  completed_at: string | null
  summary: string | null
  created_at: string
}

export interface ConsultAllowance {
  subscribed: boolean
  included: number | null
  used: number
  remaining: number | null
  unlimited: boolean
  period_start: string | null
  period_end: string | null
  duration_minutes: number
  cancellation_hours: number
}

export type CareManagerKind = 'shared' | 'dedicated'
export type CareChannel = 'call' | 'visit' | 'message' | 'video' | 'note'

export interface CareManager {
  id: number
  user_id: number
  name: string
  email: string | null
  phone: string | null
  kind: string
  /** The recorded 1:20 shared / 1:10 dedicated ratio, served not restated. */
  capacity: number
  caseload: number
  available: number
  at_capacity: boolean
  languages: string
  active: boolean
}

export interface CareAssignment {
  id: number
  patient_id: number
  care_manager_id: number
  care_manager_name: string | null
  care_manager_kind: string | null
  languages: string | null
  assigned_at: string
  ended_at: string | null
  ended_reason: string | null
}

export interface CareInteraction {
  id: number
  patient_id: number
  care_manager_id: number | null
  care_manager_name: string | null
  channel: CareChannel
  direction: 'outbound' | 'inbound'
  subject: string
  note: string
  minutes: number | null
  occurred_at: string
  visible_to_family: boolean
}

export interface CareTeam {
  patient_id: number
  entitled_kind: string | null
  assignment: CareAssignment | null
  interactions: CareInteraction[]
}

export interface ScreeningAnswerOption {
  value: number
  label: string
}

export interface ScreeningInstrument {
  code: string
  name: string
  preamble: string
  questions: string[]
  answers: ScreeningAnswerOption[]
  max_total: number
  positive_cutoff: number
  cadence_days: number
  disclaimer: string
}

export interface Screening {
  id: number
  patient_id: number
  instrument: string
  /** Both answers, paired with the question each belongs to. */
  answers: { question: string; value: number }[]
  score: number
  max_score: number
  positive: boolean
  administered_by: number
  administered_by_name: string | null
  visit_id: number | null
  administered_at: string
  note: string | null
}

export interface ScreeningStatus {
  patient_id: number
  due: boolean
  cadence_days: number
  latest: Screening | null
}

export type DeviceKind =
  | 'pulse_oximeter'
  | 'bp_monitor'
  | 'smartwatch'
  | 'glucometer'
  | 'weighing_scale'

export interface Device {
  id: number
  patient_id: number
  kind: DeviceKind
  label: string
  serial: string
  status: 'active' | 'inactive'
  online: boolean
  last_seen_at: string | null
  registered_at: string
}

/** The one response that ever carries the plaintext key. */
export interface RegisteredDevice extends Device {
  api_key: string
}

export interface DeviceReading {
  id: number
  device_id: number
  metric: VitalMetric
  /** Already in the family's vocabulary — "oxygen level", not "spo2". */
  label: string
  value: number
  recorded_at: string
  triggered: boolean
}

export type EscalationStatus = 'open' | 'acknowledged' | 'resolved'

export interface EscalationStep {
  id: number
  /** Steps sharing a sequence went out together — a fan-out, not a queue. */
  sequence: number
  actor: string
  channel: string
  target: string
  recipient_user_id: number | null
  status: string
  detail: string
  occurred_at: string
}

export interface Escalation {
  id: number
  patient_id: number
  patient_name: string | null
  trigger: string
  trigger_id: number | null
  alert_id: number | null
  severity: AlertSeverity
  status: EscalationStatus
  summary: string
  detail: string
  opened_at: string
  sla_minutes: number
  sla_due_at: string
  breached_sla: boolean
  acknowledged_by: number | null
  acknowledged_at: string | null
  resolved_by: number | null
  resolved_at: string | null
  resolution_note: string | null
  ladder: string[]
  steps: EscalationStep[]
}

export type HospitalBookingStatus =
  | 'requested'
  | 'coordinating'
  | 'confirmed'
  | 'admitted'
  | 'cancelled'

export interface HospitalBooking {
  id: number
  patient_id: number
  patient_name: string | null
  hospital_name: string
  department: string | null
  reason: string
  ambulance_required: boolean
  preferred_at: string | null
  status: HospitalBookingStatus
  requested_by: number
  requested_at: string
  sla_minutes: number
  sla_due_at: string
  breached_sla: boolean
  confirmed_at: string | null
  confirmation_detail: string | null
  handled_by: number | null
  escalation_event_id: number | null
  notes: string | null
}

export type TaskStatus = 'open' | 'done' | 'cancelled'

export interface FollowUpTask {
  id: number
  patient_id: number
  patient_name: string | null
  kind: string
  title: string
  detail: string
  due_at: string
  status: TaskStatus
  is_overdue: boolean
  source_type: string | null
  source_id: number | null
  assigned_user_id: number | null
  assigned_user_name: string | null
  completed_by: number | null
  completed_at: string | null
  completion_note: string | null
  created_at: string
}

export interface TaskSummary {
  open: number
  overdue: number
}

/** The permanent "call 108" block, served so eight screens cannot drift. */
export interface EmergencyBlock {
  number: string
  title: string
  body: string
  ladder: string[]
}
