import pytest
import httpx
from supabase import create_client, ClientOptions

USER = {'id': '11111111-1111-4111-8111-111111111111', 'email': 'student@example.com',
        'aud': 'authenticated', 'created_at': '2026-09-26T00:00:00Z',
        'app_metadata': {}, 'user_metadata': {}}


@pytest.fixture(autouse=True)
def auth_service(monkeypatch):
    from app.main import app
    from app.auth_client import get_auth_client
    state = {'offline': False, 'reject_login': False, 'logout': [], 'verified': []}

    def provider(request):
        if state['offline']:
            raise httpx.ConnectError('offline', request=request)
        path = request.url.path
        if path.endswith('/signup'):
            return httpx.Response(200, json=USER)
        if path.endswith('/token'):
            if state['reject_login']:
                return httpx.Response(400, json={'msg': 'Invalid login credentials', 'code': 'invalid_credentials'})
            return httpx.Response(200, json={'access_token': 'valid-token', 'refresh_token': 'refresh-token',
                'token_type': 'bearer', 'expires_in': 3600, 'user': USER})
        token = request.headers.get('authorization')
        if path.endswith('/user'):
            state['verified'].append(token)
            if token not in ('Bearer valid-token', 'Bearer second-token'):
                return httpx.Response(401, json={'msg': 'Invalid JWT', 'code': 'bad_jwt'})
            return httpx.Response(200, json=USER)
        if path.endswith('/logout'):
            state['logout'].append((token, request.url.params.get('scope')))
            return httpx.Response(204)
        raise AssertionError(f'Unexpected request: {request.method} {path}')

    def isolated_client():
        with httpx.Client(transport=httpx.MockTransport(provider)) as http:
            yield create_client('https://test-project.supabase.co', 'sb_publishable_test',
                options=ClientOptions(persist_session=False, auto_refresh_token=False, httpx_client=http))

    app.dependency_overrides[get_auth_client] = isolated_client
    yield state
    app.dependency_overrides.clear()


def test_signup_and_login_contract(client):
    body = {'email': 'student@example.com', 'password': 'example-only-password'}
    result = client.post('/auth/signup', json=body)
    assert result.status_code == 201
    assert result.json()['user']['id'] == USER['id']
    result = client.post('/auth/login', json=body)
    assert result.status_code == 200
    assert result.json()['access_token'] == 'valid-token'
    assert result.json()['refresh_token'] == 'refresh-token'
    assert result.headers['cache-control'] == 'no-store'


def test_wrong_credentials_are_401(client, auth_service):
    auth_service['reject_login'] = True
    result = client.post('/auth/login', json={'email': 'student@example.com', 'password': 'wrong'})
    assert result.status_code == 401
    assert result.json() == {'error': 'Invalid login credentials'}


@pytest.mark.parametrize('route', ['/auth/signup', '/auth/login'])
@pytest.mark.parametrize('body', [{}, {'email': 'a@example.com'}, {'password': 'long-password'}, {'email': '', 'password': 'x'}, {'email': 'a@example.com', 'password': ''}])
def test_missing_credentials_are_bad_requests(client, route, body):
    response = client.post(route, json=body)
    assert response.status_code == 400
    assert 'error' in response.json()


def test_public_information_needs_no_token(client):
    response = client.get('/public/info')
    assert response.status_code == 200
    assert response.json() == {'message': 'Welcome stranger! This info is public.'}


@pytest.mark.parametrize('header', [None, '', 'Basic abc', 'Bearer', 'Bearer ', 'valid-token', 'Bearer one two'])
def test_profile_rejects_missing_or_malformed_header(client, header):
    response = client.get('/protected/profile', headers={} if header is None else {'Authorization': header})
    assert response.status_code == 401
    assert response.json() == {'error': 'Access token required'}


def test_verified_profile_only_returns_safe_metadata(client, auth_service):
    result = client.get('/protected/profile', headers={'Authorization': 'Bearer valid-token'})
    assert result.status_code == 200
    assert set(result.json()) == {'id', 'email', 'created_at'}
    assert result.json()['id'] == USER['id']
    assert auth_service['verified'] == ['Bearer valid-token']


@pytest.mark.parametrize('token', ['tampered-token', 'expired-token'])
def test_provider_rejection_is_401(client, token):
    result = client.get('/protected/profile', headers={'Authorization': f'Bearer {token}'})
    assert result.status_code == 401
    assert result.json() == {'error': 'Invalid or expired token'}


def test_provider_outage_is_not_an_authentication_failure(client, auth_service):
    auth_service['offline'] = True
    result = client.get('/protected/profile', headers={'Authorization': 'Bearer valid-token'})
    assert result.status_code == 503
