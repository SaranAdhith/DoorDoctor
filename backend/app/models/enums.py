"""Shared enumerations used by the ORM models and the API schemas."""

from enum import Enum


class UserRole(str, Enum):
    FAMILY = "family"
    NURSE = "nurse"
    ADMIN = "admin"


class PatientStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class NurseStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class VisitStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    CANCELLED = "cancelled"


class MedicationLogStatus(str, Enum):
    ADMINISTERED = "administered"
    SKIPPED = "skipped"
    REFUSED = "refused"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class DeliveryChannelName(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class DeliveryStatus(str, Enum):
    """No provider is wired in this build, so a handed-off message is `simulated`."""

    SIMULATED = "simulated"
    SENT = "sent"
    FAILED = "failed"


class NotificationType(str, Enum):
    ALERT = "alert"
    VISIT = "visit"
    SYSTEM = "system"


class VitalMetric(str, Enum):
    SYSTOLIC_BP = "systolic_bp"
    DIASTOLIC_BP = "diastolic_bp"
    HEART_RATE = "heart_rate"
    BLOOD_GLUCOSE = "blood_glucose"
    SPO2 = "spo2"
    TEMPERATURE = "temperature"
    WEIGHT = "weight"


class PlanAudience(str, Enum):
    """Who a plan is sold to. Mirrors `core.pricing.AUDIENCE_*`."""

    INDIVIDUAL = "individual"
    CORPORATE = "corporate"
    INSTITUTION = "institution"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


class InvoiceLineKind(str, Enum):
    SUBSCRIPTION = "subscription"
    ADDON = "addon"
    PRORATION = "proration"


class CreditKind(str, Enum):
    """Why a credit exists. Referral and loyalty rewards are the same mechanism."""

    REFERRAL = "referral"
    LOYALTY = "loyalty"
    ADJUSTMENT = "adjustment"


class ReferralStatus(str, Enum):
    PENDING = "pending"
    JOINED = "joined"
    REWARDED = "rewarded"
    EXPIRED = "expired"


class OrganizationType(str, Enum):
    CORPORATE = "corporate"
    INSTITUTION = "institution"


class ReportKind(str, Enum):
    """Why a report exists. Drives its period and its title, nothing else."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"


class PaymentStatus(str, Enum):
    """No gateway is wired in this build, so a captured charge is `simulated`."""

    SIMULATED = "simulated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AssistantSource(str, Enum):
    """Where an assistant answer came from.

    Reported honestly in the payload. `deterministic` is the normal case and not
    a degraded one — it is what the platform ships with no API key at all.
    """

    DETERMINISTIC = "deterministic"
    ASSISTED = "assisted"


class LeadKind(str, Enum):
    """What a public enquiry is about (§2.6).

    Mirrors the audiences in `core/pricing.py` plus `nri`, which is not a
    separate price list but is a distinct conversation — a family abroad buying
    for a parent in India. `other` exists so the contact form never has to
    refuse an enquiry it cannot classify.
    """

    FAMILY = "family"
    CORPORATE = "corporate"
    INSTITUTION = "institution"
    NRI = "nri"
    OTHER = "other"


class LeadStatus(str, Enum):
    """How far an enquiry has been worked. `new` is the only state a stranger can create."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CLOSED = "closed"


# --------------------------------------------------------------------------
# Phase 9 — clinical (§4.2–4.9)
#
# Every *value* these enums describe is defined in `core/clinical.py`. These are
# only the state machines; no threshold, weight or duration appears here.
# --------------------------------------------------------------------------


class SafetyBand(str, Enum):
    """How a Senior Safety Score reads. Mirrors `core.clinical.SAFETY_BANDS`."""

    STEADY = "steady"
    WATCH = "watch"
    ATTENTION = "attention"
    CONCERN = "concern"


class LabOrderStatus(str, Enum):
    ORDERED = "ordered"
    COLLECTED = "collected"
    RESULTED = "resulted"
    CANCELLED = "cancelled"


class LabBilling(str, Enum):
    """How a panel was paid for. Recorded on the order so an invoice can be traced back."""

    ENTITLEMENT = "entitlement"
    ADDON = "addon"


class LabFlag(str, Enum):
    """A result against its reference range. `unknown` when no range is configured."""

    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"
    UNKNOWN = "unknown"

    @property
    def is_abnormal(self) -> bool:
        return self not in (LabFlag.NORMAL, LabFlag.UNKNOWN)

    @property
    def is_critical(self) -> bool:
        return self in (LabFlag.CRITICAL_LOW, LabFlag.CRITICAL_HIGH)


class TaskKind(str, Enum):
    """Why a follow-up task exists.

    General from the start: labs, screenings, wearables and escalations all
    create tasks, and a lab-specific table would have been rewritten twice.
    """

    LAB_FOLLOW_UP = "lab_follow_up"
    SCREENING_FOLLOW_UP = "screening_follow_up"
    WEARABLE_CHECK = "wearable_check"
    ESCALATION_FOLLOW_UP = "escalation_follow_up"
    SAFETY_REVIEW = "safety_review"
    GENERAL = "general"


class TaskStatus(str, Enum):
    OPEN = "open"
    DONE = "done"
    CANCELLED = "cancelled"


class ConsultStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CareManagerKind(str, Enum):
    """RECORDED ratios: shared is 1:20, dedicated is 1:10 (`core.pricing`)."""

    SHARED = "shared"
    DEDICATED = "dedicated"


class CareChannel(str, Enum):
    CALL = "call"
    VISIT = "visit"
    MESSAGE = "message"
    VIDEO = "video"
    NOTE = "note"


class CareDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class ScreeningInstrument(str, Enum):
    """PHQ-2 is a published instrument; its wording and scoring live in `core.clinical`."""

    PHQ2 = "phq2"


class DeviceKind(str, Enum):
    PULSE_OXIMETER = "pulse_oximeter"
    BP_MONITOR = "bp_monitor"
    SMARTWATCH = "smartwatch"
    GLUCOMETER = "glucometer"
    WEIGHING_SCALE = "weighing_scale"


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EscalationTrigger(str, Enum):
    """What opened an escalation. Paired with a row id in `trigger_id`."""

    WEARABLE_BREACH = "wearable_breach"
    LAB_CRITICAL = "lab_critical"
    VITAL_BREACH = "vital_breach"
    SAFETY_DROP = "safety_drop"
    HOSPITAL_BOOKING = "hospital_booking"
    MANUAL = "manual"


class EscalationStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class EscalationStepStatus(str, Enum):
    """One contact attempt. `simulated` mirrors `DeliveryStatus` — no provider is bought."""

    PENDING = "pending"
    SIMULATED = "simulated"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"


class HospitalBookingStatus(str, Enum):
    REQUESTED = "requested"
    COORDINATING = "coordinating"
    CONFIRMED = "confirmed"
    ADMITTED = "admitted"
    CANCELLED = "cancelled"
