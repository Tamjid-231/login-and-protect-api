# Verification notes

## Automated checks

67 tests passed on 27 September 2026, covering the existing task API and new authentication routes. The local run used Python 3.14; Docker uses Python 3.12. Dependency deprecation warnings and a sandbox cache warning are preserved in test-results.txt.

Auth tests use the real Supabase SDK with simulated HTTP responses. They check validation, safe fields, incorrect credentials, missing/malformed/invalid/expired tokens, service outages, caller-specific logout, empty 204 responses, and Swagger security declarations.

## Live Supabase checks

The API ran in Docker with PostgreSQL and the hosted practice project. A disposable example.com account was registered through the API. Actual curl headers and sanitized response bodies are in api-evidence.txt.

| Check | Observed status |
| --- | --- |
| Health and public info | 200 |
| Signup | 201 |
| Missing password | 400 |
| Login | 200, access and refresh tokens returned |
| Valid-token profile and dashboard | 200 |
| Missing token and malformed header | 401 |
| Tampered JWT signature | 401 |
| Wrong password | 401 |
| Logout | 204, empty body |
| Reuse token after logout | 401 in this run |
| Fresh login after logout | 200 |

The post-logout result is specific to this online get_user/session check. It does not guarantee universal instant JWT revocation; see the README's expiry explanation.

## Remaining browser evidence

Swagger loaded with its expected locks and bearer controls. Authorized browser execution was not confirmed before browser policy blocked reconnection to localhost. Complete Authorize + Try it out and add a token-free screenshot before claiming all requirements are met.

## Review

Independent code review found no important functional or security defects. Malformed configuration payload handling and stale root metadata were corrected. Missing Supabase configuration returns 503; complete environment setup before using the endpoints.

Previous-week evidence is archived in docs/week3. Optional stretch goals and the AI-rematch bonus are not included.
