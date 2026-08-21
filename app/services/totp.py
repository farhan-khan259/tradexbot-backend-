import base64
import hashlib
import hmac
import secrets
import struct
import time

def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    return base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)


def code(secret: str, timestamp: int | None = None) -> str:
    counter = int((timestamp or time.time()) // 30)
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def verify(secret: str, submitted: str, timestamp: int | None = None) -> bool:
    if not submitted or len(submitted) != 6 or not submitted.isdigit():
        return False
    current = timestamp or int(time.time())
    return any(hmac.compare_digest(code(secret, current + offset), submitted) for offset in (-30, 0, 30))


def encrypt_secret(secret: str) -> str:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    encrypted = bytes(value ^ key[index % len(key)] for index, value in enumerate(secret.encode()))
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_secret(value: str) -> str:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    encrypted = base64.urlsafe_b64decode(value.encode())
    return bytes(item ^ key[index % len(key)] for index, item in enumerate(encrypted)).decode()


def provisioning_uri(secret: str, email: str) -> str:
    from app.core.config import settings

    issuer = settings.TWO_FACTOR_ISSUER.replace(" ", "%20")
    return f"otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"