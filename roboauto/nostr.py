#!/usr/bin/env python3

"""nostr.py"""

# pylint: disable=C0116 missing-function-docstring

import datetime
import asyncio
from nostr_sdk import \
    PublicKey, SecretKey, Keys, ClientBuilder, Proxy, RelayUrl, \
    EventBuilder, Kind, Tag, Timestamp

from roboauto.logger import print_out, print_err
from roboauto.utils import \
    roboauto_options, sha512_sha256, \
    roboauto_get_coordinator_url, roboauto_get_coordinator_nostr_pubkey
from roboauto.date_utils import get_current_timestamp


def nostr_pubkey_from_token(token):
    # https://github.com/RoboSats/robosats/pull/2055/files
    nostr_seckey = SecretKey.parse(sha512_sha256(token))
    nostr_pubkey = Keys(nostr_seckey).public_key().to_hex()

    return nostr_pubkey


def coordinator_relays_get():
    relays_list = []

    for coord_name in list(roboauto_options["federation"]):
        coord_url = roboauto_get_coordinator_url(coord_name)
        nostr_pubkey = roboauto_get_coordinator_nostr_pubkey(coord_name)
        if not coord_url or not nostr_pubkey:
            continue
        relays_list.append("ws://" + coord_url.split("/", 2)[2] + "/relay")

    return relays_list


def nostr_create_publish_event(
    token, coord_pubkey, coord_token, coord_short_alias, order_id, rating
):
    async def _nostr_create_publish_event():
        review_id = 31986

        tor_host = roboauto_options["tor_host"]
        tor_port = roboauto_options["tor_port"]
        client = ClientBuilder().proxy(Proxy.all(
            f"{tor_host}:{tor_port}"
        )).build()

        for relay in coordinator_relays_get():
            await client.add_relay(RelayUrl.parse(relay))

        connection_output = await client.try_connect(
            datetime.timedelta(seconds=roboauto_options["requests_timeout"])
        )
        for key, value in connection_output.failed.items():
            print_err(f"{key} connecting {value}", error=False)

        nostr_keys = Keys(SecretKey.parse(sha512_sha256(token)))

        event_builder = EventBuilder(Kind(review_id), "")\
            .custom_created_at(Timestamp.from_secs(get_current_timestamp()))\
            .tags([
                Tag.custom("sig", [coord_token]),
                Tag.identifier(f"{coord_short_alias}:{order_id}"),
                Tag.public_key(PublicKey.parse(coord_pubkey)),
                Tag.custom("rating", [str(rating)]),
            ])

        event = event_builder.finalize(nostr_keys)

        event_output = await client.send_event(event)
        for key, value in event_output.failed.items():
            print_err(f"{key} sending event {value}", error=False)

        await client.disconnect()

        print_out(event.as_pretty_json())

        return True

    return asyncio.run(_nostr_create_publish_event())
