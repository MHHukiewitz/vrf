"""
Pre-commit Hashing for RNG aggregation (Mike)
1. A client requests a random number.
2. All nodes generate a random value, a hash of it and store them.
3. Each node posts its hash to Aleph.im
4. After each node has posted their hash, each node then posts their random number.
5. A verifier/the client checks whether all random numbers correspond to their hashes.
6. Finally, all random numbers are XORed to retrieve the final random number.

If any node fails to produce a hash or number in a given timeout duration,
the other nodes/the client will simply ignore it and proceed with their next step.
The final random number will be determined by the client and for verifiability
be posted on Aleph along with the components it used to generate the XOR random number.

This is a simple and efficient way to aggregate random numbers from multiple sources,
but can be attacked by DDoSing honest nodes.

But due to the property of XOR, as long as one node is honest, the final random number is secure.
"""
import hashlib
from typing import List

from nacl.utils import EncryptedMessage
from utilitybelt import dev_urandom_entropy


from nacl.public import PrivateKey, PublicKey, Box


def xor_all(x: List[bytes]) -> bytes:
    """XORs all the bytes in the list together."""
    result = x[0]
    for i in range(1, len(x)):
        result = bytes([a ^ b for a, b in zip(result, x[i])])
    return result


def int_to_bytes(x: int) -> bytes:
    """Converts an integer to bytes."""
    return x.to_bytes((x.bit_length() + 7) // 8, 'big')


def bytes_to_int(x: bytes) -> int:
    """Converts bytes to an integer."""
    return int.from_bytes(x, 'big')


def bytes_to_binary(x: bytes) -> str:
    """Converts bytes to a binary string."""
    return ''.join(format(b, '08b') for b in x)


def generate(n: int, nonce: int, forged_bytes=None) -> (bytes, bytes):
    """Generates a number of random bytes and hashes them with the nonce."""
    random_bytes = dev_urandom_entropy(n) if forged_bytes is None else forged_bytes
    random_hash = hashlib.sha256(random_bytes + int_to_bytes(nonce)).digest()
    return random_bytes, random_hash


def verify(random_bytes: bytes, nonce: int, random_hash: bytes) -> bool:
    """Verifies that the random bytes were generated by the given nonce."""
    return random_hash == hashlib.sha256(random_bytes + int_to_bytes(nonce)).digest()


def encrypt(random_bytes: bytes, nonce: int, private_key: PrivateKey, public_key: PublicKey) -> EncryptedMessage:
    """
    Encrypts the random bytes and hash with the given public key.
    Returns the encrypted random bytes and nonce.

    :param random_bytes: The random bytes to encrypt.
    :param nonce: The nonce to encrypt.
    :param private_key: The private key of the sender.
    :param public_key: The public key of the recipient.
    """
    box = Box(private_key, public_key)
    return box.encrypt(random_bytes + bytes(nonce))


def decrypt(n: int, encrypted: bytes, private_key: PrivateKey, public_key: PublicKey) -> (bytes, int):
    """
    Decrypts the random bytes and hash with the given private key.
    Returns the random bytes and nonce.

    :param n: The number of random bytes.
    :param encrypted: The encrypted random bytes and nonce.
    :param private_key: The private key of the recipient.
    :param public_key: The public key of the sender.
    """
    box = Box(private_key, public_key)
    decrypted = box.decrypt(encrypted)
    random_bytes = decrypted[:n]
    nonce = int.from_bytes(decrypted[n:], 'big')
    return random_bytes, nonce


def main():
    randy = PrivateKey.generate()  # requestor
    alice = PrivateKey.generate()  # honest node
    bob = PrivateKey.generate()  # malicious node

    # Request a random number
    nonce = 0
    number_bytes = 32
    random_bytes_alice, random_hash_alice = generate(number_bytes, nonce)
    random_bytes_bob, random_hash_bob = generate(number_bytes, nonce, forged_bytes=b'deadbeef' * 4)

    # Encrypt the random number and hash with the requestor's public key
    encrypted_alice = encrypt(random_bytes_alice, nonce, alice, randy.public_key)
    encrypted_bob = encrypt(random_bytes_bob, nonce, bob, randy.public_key)

    # Assume the random hashes are now public
    # Now the requestor can verify the random numbers
    decrypted_alice, nonce_alice = decrypt(number_bytes, encrypted_alice, randy, alice.public_key)
    decrypted_bob, nonce_bob = decrypt(number_bytes, encrypted_bob, randy, bob.public_key)
    assert verify(decrypted_alice, nonce_alice, random_hash_alice)
    assert verify(decrypted_bob, nonce_bob, random_hash_bob)

    # Now the requestor can XOR the random numbers together
    print(bytes_to_int(decrypted_alice))
    print(bytes_to_int(decrypted_bob))
    final_random_number = xor_all([decrypted_alice, decrypted_bob])
    print(bytes_to_int(final_random_number))
    print(len(str(bytes_to_int(final_random_number))))

    # Due to the property of XOR, as long as one node is honest, the final random number is secure

    # Now the requestor can post the random number and the hashes to Aleph.im


if __name__ == '__main__':
    main()