"""Shared enumerations used by the ORM models and the API schemas."""

from enum import Enum


class UserRole(str, Enum):
    FAMILY = "family"
    CAREGIVER = "caregiver"
    COORDINATOR = "coordinator"


class PatientStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CaregiverStatus(str, Enum):
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
