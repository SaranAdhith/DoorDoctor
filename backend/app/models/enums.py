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
