import base64
import json

import pytest
from fastapi import HTTPException

from app.auth_client import get_auth_client


@pytest.mark.parametrize('payload', [None, [], 'not-a-dictionary'])
def test_malformed_configuration_key_fails_with_clear_error(monkeypatch, payload):
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    monkeypatch.setenv('SUPABASE_URL', 'https://test-project.supabase.co')
    monkeypatch.setenv('SUPABASE_KEY', f'header.{encoded}.signature')
    with pytest.raises(HTTPException) as error:
        next(get_auth_client())
    assert error.value.status_code == 503
