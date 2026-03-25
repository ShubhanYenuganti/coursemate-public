"""Pytest configuration: stub out heavy/unavailable dependencies so unit tests
that only exercise pure helper functions in api.quiz can import successfully
without needing psycopg, cryptography, boto3, etc."""
import sys
from unittest.mock import MagicMock

# Stub modules that are unavailable in the test environment
_stubs = [
    'psycopg',
    'psycopg.rows',
    'psycopg_pool',
    'cryptography',
    'cryptography.fernet',
    'boto3',
    'pgvector',
    'google.auth',
    'google.auth.transport',
    'google.auth.transport.requests',
    'google.oauth2',
    'google.oauth2.id_token',
]

for mod in _stubs:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
