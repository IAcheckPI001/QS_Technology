from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from app.core.security.visitor_token import (
    InvalidVisitorToken,
    VisitorClaims,
    issue_visitor_token,
    verify_visitor_token,
)
from app.modules.chatbot.schemas.security.principal import PrincipalContext


@dataclass(frozen=True)
class IssuedVisitorToken:
    token: str
    guest_id: str
    expires_at: datetime


class VisitorIdentityService:
    """Cấp và xác minh danh tính khách website (principal_type="guest")."""

    def __init__(self, *, secret: str, issuer: str, ttl: timedelta) -> None:
        self._secret = secret
        self._issuer = issuer
        self._ttl = ttl

    def issue(self, current_token: str | None) -> IssuedVisitorToken:
        """Token hiện tại còn hợp lệ → làm mới cùng guest_id; còn lại → khách mới."""
        guest_id = None
        if current_token:
            try:
                guest_id = self._verify(current_token).guest_id
            except InvalidVisitorToken:
                guest_id = None
        token, claims = issue_visitor_token(
            guest_id or str(uuid4()),
            secret=self._secret,
            issuer=self._issuer,
            ttl=self._ttl,
        )
        return IssuedVisitorToken(token=token, guest_id=claims.guest_id, expires_at=claims.expires_at)

    def authenticate(self, token: str) -> PrincipalContext:
        """Raise InvalidVisitorToken nếu token sai/hết hạn."""
        claims = self._verify(token)
        return PrincipalContext(
            subject_id=claims.guest_id,
            principal_type="guest",
            authn_method="guest_token",
        )

    def _verify(self, token: str) -> VisitorClaims:
        return verify_visitor_token(token, secret=self._secret, issuer=self._issuer)
