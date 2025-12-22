import tempfile
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

# constants for aes-256
KEY_SIZE = 32  # 256 bits
SALT_SIZE = 16
ITERATIONS = 100000


def encrypt_file(file_path: Path, password: str) -> None:
    """encrypts a file using aes-256"""
    if not file_path.exists():
        return
    plaintext = file_path.read_bytes()
    encrypt_bytes_to_file(plaintext, file_path, password)


def encrypt_bytes_to_file(data: bytes, file_path: Path, password: str) -> None:
    """encrypts writes in file"""
    salt = get_random_bytes(SALT_SIZE)
    key = PBKDF2(password, salt, dkLen=KEY_SIZE, count=ITERATIONS)
    cipher = AES.new(key, AES.MODE_CBC)
    padded_data = pad(data, AES.block_size)
    ciphertext = cipher.encrypt(padded_data)
    iv = cipher.iv
    # write salt, iv, and ciphertext to the file
    file_path.write_bytes(salt + iv + ciphertext)


def decrypt_file(file_path: Path, password: str) -> None:
    """decrypts a file using aes-256"""
    if not file_path.exists():
        return
    encrypted_data = file_path.read_bytes()
    # extract salt, iv, and ciphertext
    salt = encrypted_data[:SALT_SIZE]
    iv = encrypted_data[SALT_SIZE : SALT_SIZE + AES.block_size]
    ciphertext = encrypted_data[SALT_SIZE + AES.block_size :]
    key = PBKDF2(password, salt, dkLen=KEY_SIZE, count=ITERATIONS)
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    try:
        decrypted_padded_data = cipher.decrypt(ciphertext)
        plaintext = unpad(decrypted_padded_data, AES.block_size)
        file_path.write_bytes(plaintext)
    except (ValueError, KeyError) as e:
        # this often happens if the password is wrong
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
    iv = encrypted_data[SALT_SIZE : SALT_SIZE + AES.block_size]
    ciphertext = encrypted_data[SALT_SIZE + AES.block_size :]
    key = PBKDF2(password, salt, dkLen=KEY_SIZE, count=ITERATIONS)
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    try:
        decrypted_padded_data = cipher.decrypt(ciphertext)
        plaintext = unpad(decrypted_padded_data, AES.block_size)
        # create a temporary file to store the decrypted database
        temp_db = tempfile.NamedTemporaryFile(delete=True)
        temp_db.write(plaintext)
        temp_db.seek(0)
        return temp_db
    except (ValueError, KeyError) as e:
        raise ValueError(
            "failed to decrypt file, incorrect password or corrupted file"
        ) from e
