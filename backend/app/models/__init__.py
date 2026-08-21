"""ORM models. Importing this package registers every table on the declarative Base."""

from .alert import Alert
from .caregiver import Caregiver
from .enums import (
    AlertSeverity,
    AlertStatus,
    CaregiverStatus,
    MedicationLogStatus,
    NotificationType,
    PatientStatus,
    UserRole,
    VerificationStatus,
    VisitStatus,
    VitalMetric,
)
from .medication import Medication, MedicationLog
from .notification import Notification
from .patient import Patient, PatientThreshold
from .user import User
from .visit import Visit
from .vital import Vital

__all__ = [
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "Caregiver",
    "CaregiverStatus",
    "Medication",
    "MedicationLog",
    "MedicationLogStatus",
    "Notification",
    "NotificationType",
    "Patient",
    "PatientStatus",
    "PatientThreshold",
    "User",
    "UserRole",
    "VerificationStatus",
    "Visit",
    "VisitStatus",
    "Vital",
    "VitalMetric",
]
