"""Generate a Fernet key for PII encryption.

Usage:  python scripts/gen_key.py
Copy the printed key into ENCRYPTION_KEY= in your .env file.
"""
from __future__ import annotations

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
    print("Add the line above to your .env as: ENCRYPTION_KEY=<key>")
