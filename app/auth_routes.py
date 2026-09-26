"""Authentication endpoints backed by Supabase Auth."""
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from httpx import HTTPError
from pydantic import BaseModel, ConfigDict, StrictStr, field_validator
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app.auth_client import get_auth_client

router = APIRouter()


@router.get('/public/info', tags=['Public'])
def public_info():
    return {'message': 'Welcome stranger! This info is public.'}


def require_user(request: Request, client=Depends(get_auth_client)):
    parts = request.headers.get('Authorization', '').split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(401, 'Access token required', headers={'WWW-Authenticate': 'Bearer'})
    try:
        result = client.auth.get_user(parts[1])
    except (HTTPError, AuthRetryableError):
        raise HTTPException(503, 'Authentication service unavailable') from None
    except AuthApiError:
        raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'}) from None
    if result is None or result.user is None:
        raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'})
    return result.user, parts[1]


@router.get('/protected/profile', tags=['Protected'])
def profile(identity=Depends(require_user)):
    return safe_user(identity[0])


@router.get('/protected/dashboard', tags=['Protected'])
def dashboard(identity=Depends(require_user)):
    return {'message': 'Welcome to your dashboard!', 'user_id': identity[0].id}


@router.post('/auth/logout', status_code=204, tags=['Authentication'])
def logout(identity=Depends(require_user), client=Depends(get_auth_client)):
    try:
        # This SDK method posts the verified caller's JWT to /logout. Unlike
        # sign_out(), it works without a stored session and propagates errors.
        # No service-role key or shared server session is used.
        client.auth.admin.sign_out(identity[1], scope='local')
    except (HTTPError, AuthRetryableError):
        raise HTTPException(503, 'Authentication service unavailable') from None
    except AuthApiError:
        raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'}) from None
    return Response(status_code=204)


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: StrictStr
    password: StrictStr

    @field_validator('email', 'password')
    @classmethod
    def required(cls, value):
        if not value.strip():
            raise ValueError('Email and password are required')
        return value


def safe_user(user):
    return {'id': user.id, 'email': user.email, 'created_at': user.created_at}


@router.post('/auth/signup', status_code=201, tags=['Authentication'])
def signup(body: Credentials, client=Depends(get_auth_client)):
    try:
        result = client.auth.sign_up(body.model_dump())
    except (HTTPError, AuthRetryableError):
        raise HTTPException(503, 'Authentication service unavailable') from None
    except AuthApiError:
        raise HTTPException(400, 'Unable to create account. Check email and password requirements.') from None
    if result.user is None:
        raise HTTPException(400, 'Unable to create account')
    return {'user': safe_user(result.user), 'email_confirmation_required': result.session is None}


@router.post('/auth/login', tags=['Authentication'])
def login(body: Credentials, response: Response, client=Depends(get_auth_client)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        result = client.auth.sign_in_with_password(body.model_dump())
    except (HTTPError, AuthRetryableError):
        raise HTTPException(503, 'Authentication service unavailable') from None
    except AuthApiError:
        raise HTTPException(401, 'Invalid login credentials') from None
    if result.session is None:
        raise HTTPException(401, 'Invalid login credentials')
    session = result.session
    return {'access_token': session.access_token, 'refresh_token': session.refresh_token,
            'token_type': session.token_type, 'expires_in': session.expires_in}
