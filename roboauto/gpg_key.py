#!/usr/bin/env python3

"""gpg_key.py"""

# pylint: disable=C0116 missing-function-docstring

import datetime

import gnupg

from roboauto.global_state import roboauto_state
from roboauto.logger import print_err
from roboauto.utils import token_get_double_sha256


def gpg_get():
    if roboauto_state["gpg"] is None:
        roboauto_state["gpg"] = \
            gnupg.GPG(gnupghome=roboauto_state["gnupg_home"], verbose=False)

    return roboauto_state["gpg"]


def gpg_generate_robot(token):
    gpg = gpg_get()

    token_double_sha256 = token_get_double_sha256(token)

    key_passphrase = token

    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # stupid python-gnupg put by default Name-Email in gen_key_input and no option to remove it
    input_data = f"""\
Key-Type: EDDSA
Key-Curve: ed25519
Key-Usage: sign
Subkey-Type: ECC
Subkey-Curve: cv25519
SubKey-Usage: encrypt
Passphrase: {key_passphrase}
Name-Real: RoboSats ID {token_double_sha256}
Creation-Date: {yesterday}
%commit
"""

    key = gpg.gen_key(input_data)

    fingerprint = key.fingerprint

    public_key = gpg.export_keys(fingerprint, secret=False, armor=True)
    private_key = gpg.export_keys(
        fingerprint, secret=True, armor=True,
        passphrase=key_passphrase
    )

    return fingerprint, public_key, private_key


def gpg_import_key(key, set_trust=True, passphrase=None, error_print=True):
    gpg = gpg_get()

    key = gpg.import_keys(key, passphrase=passphrase)

    if not hasattr(key, "count") or key.count != 1:
        if error_print:
            print_err("imported key is multiple keys")
        return False

    fingerprint = key.fingerprints[0]

    if set_trust is True:
        gpg.trust_keys(fingerprint, "TRUST_ULTIMATE")

    return fingerprint


def gpg_encrypt_sign_message(
    message, fingerprints, sender_fingerprint, passphrase=None, error_print=True
):
    gpg = gpg_get()

    # also set yesterday date (maybe ?) (how ?) as in robosats/frontend/src/pgp/index.ts
    encrypted_data = gpg.encrypt(
        message, fingerprints, sign=sender_fingerprint, passphrase=passphrase
    )

    if encrypted_data.ok is not True:
        if error_print:
            print_err("encrypting and signing message")
        return False

    message_enc = str(encrypted_data)

    return message_enc


def gpg_decrypt_check_message(message, passphrase=None, error_print=True):
    gpg = gpg_get()

    decrypted_data = gpg.decrypt(message, passphrase=passphrase)

    if decrypted_data.ok is not True:
        if error_print:
            print_err("decrypting and checking message")
        return False

    decrypted_message = str(decrypted_data)

    return decrypted_message


def gpg_sign_message(message, fingerprint, passphrase=None, error_print=True):
    gpg = gpg_get()

    signed_data = gpg.sign(message, keyid=fingerprint, passphrase=passphrase)

    if hasattr(signed_data, "status_detail") and signed_data.status_detail is not None:
        if error_print:
            print_err("signing message")
        return False

    signed_message = str(signed_data)

    return signed_message
