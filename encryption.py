from Crypto.Cipher import AES
from base64 import b64encode, b64decode

PRIVATE_AES_KEY = '0123456789abcdef'.encode(
    "utf8")  # Random generated key for AES
PRIVATE_AES_IV = (16 * '\x00').encode("utf8")  # Initialization vector for AES

def encrypt_data(data):
    aes = AES.new(PRIVATE_AES_KEY, AES.MODE_CFB, PRIVATE_AES_IV)
    data_encoded = b64encode(data)
    return aes.encrypt(data_encoded)


def decrypt_data(data):
    aes = AES.new(PRIVATE_AES_KEY, AES.MODE_CFB, PRIVATE_AES_IV)
    return b64decode(aes.decrypt(data))
