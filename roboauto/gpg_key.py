#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring

import datetime

import gnupg

from roboauto.global_state import roboauto_state
from roboauto.utils import token_get_double_sha256


def gpg_generate_robot(token):
    gpg = gnupg.GPG(gnupghome=roboauto_state["gnupg_home"], verbose=False)

    token_double_sha256 = token_get_double_sha256(token)

    key_passphrase = token

    date_yesterday = (
        datetime.datetime.now() - datetime.timedelta(days=1)
    ).strftime("%Y%m%dT%H%M%S")

    input_data = gpg.gen_key_input(
        key_type="EDDSA",
        key_curve="ed25519",
        name_real="RoboSats ID " + token_double_sha256,
        creation_date=date_yesterday,
        passphrase=key_passphrase
    )

    key = gpg.gen_key(input_data)
    fingerprint = key.fingerprint

    public_key = gpg.export_keys(fingerprint, secret=False, armor=True)
    private_key = gpg.export_keys(
        fingerprint, secret=True, armor=True,
        passphrase=key_passphrase
    )

    return fingerprint, public_key, private_key
