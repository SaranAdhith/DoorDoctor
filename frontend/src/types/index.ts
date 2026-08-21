export type Role = 'family' | 'caregiver' | 'coordinator'

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
  caregiver_id: number | null
  scheduled_at: string
  status: VisitStatus
  checkin_at: string | null
  checkout_at: string | null
  location_source: string
  notes: string | null
  patient?: { id: number; name: string; age: number; address: string }
  caregiver?: { id: number; name: string; credential: string; phone: string | null }
  caregiver_name?: string | null
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
  caregiver_name: string | null
  vitals: Vitals | null
  thresholds: Threshold[]
}

export interface Caregiver {
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
  caregiver: Caregiver | null
  overall_status: 'Stable' | 'Attention Required' | 'Critical Alert'
  thresholds: Threshold[]
}

export interface CoordinatorSummary {
  patients: number
  caregivers: number
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
