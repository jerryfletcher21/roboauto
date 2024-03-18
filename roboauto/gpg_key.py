#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring

import gnupg

from roboauto.global_state import roboauto_state
from roboauto.utils import token_get_double_sha256


def gpg_generate_robot(token):
    gpg = gnupg.GPG(gnupghome=roboauto_state["gnupg_home"], verbose=False)

    token_double_sha256 = token_get_double_sha256(token)

    key_passphrase = token

    # stupid python-gnupg put by default Name-Email which can not be removed
    # fortunatly gen_key_input simply returns a string
    # input_data = gpg.gen_key_input(
    #     key_type="EDDSA",
    #     key_curve="ed25519",
    #     key_usage="sign",
    #     name_real="RoboSats ID " + token_double_sha256,
    #     passphrase=key_passphrase
    # )
    input_data = f"""\
Key-Type: EDDSA
Key-Curve: ed25519
Key-Usage: sign
Name-Real: RoboSats ID {token_double_sha256}
Passphrase: {key_passphrase}
%commit
"""

    key = gpg.gen_key(input_data)

    fingerprint = key.fingerprint

    gpg.add_subkey(fingerprint, key_passphrase, algorithm="cv25519", usage="encrypt")

    public_key = gpg.export_keys(fingerprint, secret=False, armor=True)
    private_key = gpg.export_keys(
        fingerprint, secret=True, armor=True,
        passphrase=key_passphrase
    )

    return fingerprint, public_key, private_key
