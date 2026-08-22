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
