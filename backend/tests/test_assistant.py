"""Application assistant tests — field detection logic."""
from app.services.application_assistant import _is_sensitive, _map_field


def test_map_field():
    assert _map_field("Full Name") == "name"
    assert _map_field("Email Address") == "email"
    assert _map_field("Phone Number") == "phone"
    assert _map_field("Your CV (PDF)") == "cv_file"
    assert _map_field("Upload Resume") == "cv_file"
    assert _map_field("Cover Letter") == "cover_letter_file"
    assert _map_field("City") == "location"
    assert _map_field("Years of experience") is None


def test_sensitive_detection():
    assert _is_sensitive("Have you been convicted of a criminal offence?")
    assert _is_sensitive("Salary expectation")
    assert _is_sensitive("TSC Number")
    assert _is_sensitive("ID number")
    assert _is_sensitive("Passport number")
    assert _is_sensitive("Visa status")
    assert _is_sensitive("Legal declaration")
    assert _is_sensitive("I confirm the information is true")
    assert _is_sensitive("reCAPTCHA")
    assert not _is_sensitive("Full Name")
    assert not _is_sensitive("Email Address")
    assert not _is_sensitive("Phone Number")
    assert not _is_sensitive("Education level")
