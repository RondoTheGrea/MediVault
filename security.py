"""
Password hashing, login, and field encryption.
"""
import os

import bcrypt
from cryptography.fernet import Fernet


def load_or_create_key(path):
    """Read a secret key from a file, creating the file the first time."""
    if not os.path.exists(path):
        with open(path, "wb") as file:
            file.write(Fernet.generate_key())
    with open(path, "rb") as file:
        return file.read()


class AuthManager:
    """Checks usernames and passwords. Passwords are never stored in plain text."""

    def __init__(self, user_repository):
        self.users = user_repository

    @staticmethod
    def hash_password(plain_password):
        # bcrypt adds a random "salt", so two users with the same password
        # still get different hashes.
        hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def check_password(plain_password, password_hash):
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))

    def login(self, username, password):
        """Return the User if the credentials are valid, otherwise None."""
        user = self.users.find_by_username(username)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not AuthManager.check_password(password, user.get_password_hash()):
            return None
        return user


class Encryptor:
    """
    Encrypts sensitive text before it goes into the database.
    Anyone who copies the .db file without the key file sees only gibberish.
    """

    def __init__(self, key):
        self._fernet = Fernet(key)

    def encrypt(self, plain_text):
        return self._fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_text):
        return self._fernet.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
