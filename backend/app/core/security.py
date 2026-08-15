from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
import jwt
from app.core.config import settings

PBKDF2_ITERATIONS = 600_000

def hash_password(password: str) -> str:
    """Portable password hashing without the Python 3.14/passlib bcrypt incompatibility."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )

def verify_password(password: str, hashed: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = hashed.split("$", 3)
        if scheme != "pbkdf2_sha256": return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.urlsafe_b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.urlsafe_b64decode(digest_b64))
    except (ValueError, TypeError):
        return False
def create_token(subject: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": exp}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
def decode_token(token: str) -> str:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])["sub"]
