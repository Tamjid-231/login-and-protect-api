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


@router.get('/protected/profile', tags=['Protected'])
def profile(request: Request):
    parts = request.headers.get('Authorization', '').split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(401, 'Access token required', headers={'WWW-Authenticate': 'Bearer'})
    # Stage 2 is deliberately fail-closed until remote verification is added.
    raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'})


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
