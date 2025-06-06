#!/usr/bin/env python3

"""nostr.py"""

# pylint: disable=C0116 missing-function-docstring

import datetime
import asyncio
from nostr_sdk import \
    PublicKey, SecretKey, Keys, Client, EventBuilder, Kind, \
    RelayOptions, ConnectionMode, Tag, TagKind, Timestamp

from roboauto.logger import print_out, print_err
from roboauto.utils import roboauto_options, roboauto_get_coordinator_url, sha256_single
from roboauto.date_utils import get_current_timestamp


def nostr_pubkey_from_token(token):
    nostr_seckey = SecretKey.parse(sha256_single(token))
    nostr_pubkey = Keys(nostr_seckey).public_key().to_hex()

    return nostr_pubkey


def coordinator_relays_get():
    relays_list = []

    for coord_name in list(roboauto_options["federation"]):
        coord_url = roboauto_get_coordinator_url(coord_name)
        if not coord_url:
            continue
        relays_list.append("ws://" + coord_url.split("/", 2)[2] + "/relay")

    return relays_list


def nostr_create_publish_event(
    token, coord_pubkey, coord_token, coord_short_alias, order_id, rating
):
    async def _nostr_create_publish_event():
        review_id = 31986

        client = Client()

        for relay in coordinator_relays_get():
            await client.add_relay_with_opts(
                relay, RelayOptions().connection_mode(
                    ConnectionMode.PROXY("127.0.0.1", 9050) # pyright: ignore reportArgumentType
            ))

        connection_output = await client.try_connect(
            datetime.timedelta(seconds=roboauto_options["requests_timeout"])
        )
        for key, value in connection_output.failed.items():
            print_err(f"{key} connecting {value}", error=False)

        nostr_keys = Keys(SecretKey.parse(sha256_single(token)))

        # pylint: disable=C0301 line-too-long
        event_builder = EventBuilder(Kind(review_id), "")\
            .custom_created_at(Timestamp.from_secs(get_current_timestamp()))\
            .tags([
                Tag.custom(TagKind.UNKNOWN("sig"), [coord_token]), # pyright: ignore reportArgumentType
                Tag.identifier(f"{coord_short_alias}:{order_id}"),
                Tag.public_key(PublicKey.parse(coord_pubkey)),
                Tag.custom(TagKind.UNKNOWN("rating"), [str(rating)]), # pyright: ignore reportArgumentType
            ])

        event = event_builder.sign_with_keys(nostr_keys)

        event_output = await client.send_event(event)
        for key, value in event_output.failed.items():
            print_err(f"{key} sending event {value}", error=False)

        await client.disconnect()

        print_out(event.as_pretty_json())

        return True

    return asyncio.run(_nostr_create_publish_event())
