import datetime
import hashlib
import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.getenv(
    "JWT_SECRET", "super_secure_tamper_evident_key_prod_2026"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def get_password_hash(password: str) -> str:
  salt = secrets.token_hex(16)
  pwd_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
  return f"{salt}${pwd_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
  try:
    salt, original_hash = hashed_password.split("$")
    test_hash = hashlib.sha256(
        (salt + plain_password).encode("utf-8")
    ).hexdigest()
    return test_hash == original_hash
  except Exception:
    return False


def create_access_token(data: dict):
  to_encode = data.copy()
  expire = datetime.datetime.utcnow() + datetime.timedelta(
      minutes=ACCESS_TOKEN_EXPIRE_MINUTES
  )
  to_encode.update({"exp": expire})
  return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
  try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload
  except JWTError:
    return None