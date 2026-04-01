"""
conftest.py — shared pytest configuration for unit tests.

Google API libraries are not installed in the test environment.
Stub them out at import time so modules that import them can be loaded.
"""

import sys
from unittest.mock import MagicMock

# Stub Google API libraries before any test module imports claude-code modules
for mod in [
    "google",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.credentials",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.errors",
]:
    sys.modules.setdefault(mod, MagicMock())

# Stub linkedin-api library
for mod in [
    "linkedin_api",
    "requests",
    "requests.cookies",
]:
    sys.modules.setdefault(mod, MagicMock())
