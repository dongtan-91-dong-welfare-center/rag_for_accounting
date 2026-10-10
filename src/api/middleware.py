"""HTTP 보안 헤더 미들웨어 (#449).

CSP, MIME 스니핑 방지, 프레임 삽입 제한 등 기본 보안 헤더를 모든 HTTP 응답에 주입한다.
PDF 뷰어 iframe 및 프론트엔드 구글 폰트 동작을 보장하도록 정책을 수립한다.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

DEFAULT_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-ancestors 'self'; "
        "frame-src 'self'; "
        "object-src 'self';"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """모든 HTTP 응답에 웹 보안 헤더를 추가하는 미들웨어."""

    def __init__(self, app, headers: dict[str, str] | None = None) -> None:
        super().__init__(app)
        self.headers = headers or DEFAULT_SECURITY_HEADERS

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for key, value in self.headers.items():
            response.headers[key] = value
        return response
