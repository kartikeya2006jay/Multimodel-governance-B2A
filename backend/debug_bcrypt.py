from passlib.context import CryptContext
import sys

try:
    import bcrypt
    print(f"Bcrypt version: {bcrypt.__version__ if hasattr(bcrypt, '__version__') else 'unknown'}")
except ImportError:
    print("Bcrypt not installed")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

password = "testpassword"
try:
    print("Attempting to hash password...")
    hashed = pwd_context.hash(password)
    print(f"Hashed: {hashed}")
    
    print("Attempting to verify password...")
    verified = pwd_context.verify(password, hashed)
    print(f"Verified: {verified}")
except Exception as e:
    print(f"\nCaught Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
