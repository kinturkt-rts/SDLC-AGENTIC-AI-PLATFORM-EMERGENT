"""Sensitive data detection service."""
import re

# SSN pattern: NNN-NN-NNNN
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Keywords that indicate sensitive data requests
_SENSITIVE_KEYWORDS = [
    "social security",
    "ssn",
    "date of birth",
    "my symptoms",
    "my diagnosis",
    "my prescription",
    "my medication dosage",
    "store my",
    "save my medical",
    "remember my health",
]

REDIRECT_MESSAGE = (
    "I'm not able to collect or store personal medical information such as "
    "Social Security numbers, dates of birth, or detailed symptoms. "
    "For personal medical questions, please contact the clinic directly at (555) 123-4567."
)


def contains_sensitive_data(message: str) -> bool:
    """Return True if the message contains or requests sensitive personal data."""
    if _SSN_PATTERN.search(message):
        return True
    lower = message.lower()
    return any(kw in lower for kw in _SENSITIVE_KEYWORDS)
