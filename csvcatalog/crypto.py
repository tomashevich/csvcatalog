import tempfile
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

# constants for aes-256-gcm
KEY_SIZE = 32  # 256 bits
SALT_SIZE = 16
NONCE_SIZE = 16  # gcm standard nonce size
TAG_SIZE = 16  # gcm standard auth tag size
ITERATIONS = 100000


def encrypt_file(file_path: Path, password: str) -> None:
    """encrypts a file using aes-256-gcm"""
    if not file_path.exists():
        return
    plaintext = file_path.read_bytes()
    encrypt_bytes_to_file(plaintext, file_path, password)


def encrypt_bytes_to_file(data: bytes, file_path: Path, password: str) -> None:
    """encrypts and writes in file"""
    salt = get_random_bytes(SALT_SIZE)
    key = PBKDF2(password, salt, dkLen=KEY_SIZE, count=ITERATIONS)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    nonce = cipher.nonce
    # write salt, nonce, tag, and ciphertext to the file
    file_path.write_bytes(salt + nonce + tag + ciphertext)


def decrypt_file(file_path: Path, password: str) -> None:
    """decrypts a file using aes-256-gcm"""
    if not file_path.exists():
        return
    encrypted_data = file_path.read_bytes()
    # extract salt, nonce, tag, and ciphertext
    salt = encrypted_data[:SALT_SIZE]
    nonce = encrypted_data[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    tag = encrypted_data[SALT_SIZE + NONCE_SIZE : SALT_SIZE + NONCE_SIZE + TAG_SIZE]
    ciphertext = encrypted_data[SALT_SIZE + NONCE_SIZE + TAG_SIZE :]
    key = PBKDF2(password, salt, dkLen=KEY_SIZE, count=ITERATIONS)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        file_path.write_bytes(plaintext)
    except (ValueError, KeyError) as e:
        # this happens if the password is wrong or the file is corrupted/tampered with
        raise ValueError(
            "failed to decrypt file, incorrect password or corrupted file"
        ) from e


def decrypt_file_to_temp(
    file_path: Path, password: str
) -> tempfile._TemporaryFileWrapper:
    """
    decrypts a file and returns a temporary file object containing the plaintext
    the temporary file is deleted on close
    """
    if not file_path.exists():
        # return an empty temp file for new db
        temp_db = tempfile.NamedTemporaryFile(delete=True)
        return temp_db
    encrypted_data = file_path.read_bytes()
    salt = encrypted_data[:SALT_SIZE]
    nonce = encrypted_data[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    tag = encrypted_data[SALT_SIZE + NONCE_SIZE : SALT_SIZE + NONCE_SIZE + TAG_SIZE]
    ciphertext = encrypted_data[SALT_SIZE + NONCE_SIZE + TAG_SIZE :]
    key = PBKDF2(password, salt, dkLen=KEY_SIZE, count=ITERATIONS)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        # create a temporary file to store the decrypted database
        temp_db = tempfile.NamedTemporaryFile(delete=True)
        temp_db.write(plaintext)
        temp_db.seek(0)
        return temp_db
    except (ValueError, KeyError) as e:
        raise ValueError(
            "failed to decrypt file, incorrect password or corrupted file"
        ) from e
