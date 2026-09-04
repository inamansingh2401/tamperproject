import datetime
import os
from typing import Optional

import bcrypt
import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-change-me-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # New bcrypt hashes
        if hashed_password.startswith("$2"):
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

        # Backward compatibility for existing demo DB hashes
        if "$" in hashed_password:
            import hashlib
            salt, original_hash = hashed_password.split("$", 1)
            test_hash = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
            return test_hash == original_hash
    except Exception:
        pass
    return False

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
