# auth_utils.py

from passlib.context import CryptContext

# Set up the password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    default="bcrypt",
    deprecated="auto"
)

def hash_password(password: str) -> str:
    """
    Hash a password using the configured hashing algorithm.

    Args:
        password (str): The plaintext password to hash.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a hashed password.

    Args:
        plain_password (str): The plaintext password provided by the user.
        hashed_password (str): The hashed password stored in the database.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)
