"""Create an isolated Supabase client for each request; never share user sessions."""
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import HTTPException
from supabase import ClientOptions, create_client

load_dotenv(Path(__file__).resolve().parents[1] / '.env')


def get_auth_client():
    url = os.getenv('SUPABASE_URL', '')
    key = os.getenv('SUPABASE_KEY', '')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or not key:
        raise HTTPException(503, 'Configure SUPABASE_URL and SUPABASE_KEY in .env')
    if key.startswith('sb_secret_'):
        raise HTTPException(503, 'Use a Supabase anon or publishable key')
    if key.count('.') == 2:
        try:
            part = key.split('.')[1]
            payload = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
            if payload.get('role') != 'anon':
                raise HTTPException(503, 'Use a Supabase anon or publishable key')
        except (ValueError, UnicodeError):
            raise HTTPException(503, 'Invalid Supabase key configuration') from None
    # Decoding above only rejects the wrong configuration key. User JWTs are
    # always verified remotely with get_user(), never trusted after decoding.
    client = create_client(url, key, options=ClientOptions(
        persist_session=False, auto_refresh_token=False,
    ))
    try:
        yield client
    finally:
        client.auth.close()
