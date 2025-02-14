#!/usr/bin/env python3

"""requests_api.py"""

# pylint: disable=C0116 missing-function-docstring

import time

import requests
import filelock

from roboauto.logger import print_err
from roboauto.utils import json_dumps, lock_file_name_get
from roboauto.global_state import roboauto_options, roboauto_state


def response_is_error(response):
    if response is False or response is None:
        return True

    if not hasattr(response, "ok") or not hasattr(response, "status_code"):
        return True

    if not response.ok and int(response.status_code / 100) != 4:
        return True

    return False


def requests_tor_response(
    url: str, user, timeout, headers, data, error_print=True
) -> requests.Response | bool | None:
    if not url.startswith("http://127.0.0.1"):
        tor_socks = \
            user + ":" + user + "@" + \
            roboauto_options["tor_host"] + ":" + str(roboauto_options["tor_port"])
        proxies = {
            "http": "socks5h://" + tor_socks,
            "https": "socks5h://" + tor_socks
        }
    else:
        proxies = None

    # one concurrent connection per circuit
    try:
        filelock_timeout = roboauto_state["filelock_timeout"]
        try:
            with filelock.FileLock(
                lock_file_name_get(user),
                timeout=filelock_timeout
            ):
                if data is None:
                    return requests.get(
                        url, proxies=proxies, timeout=timeout,
                        headers=headers
                    )
                else:
                    return requests.post(
                        url, proxies=proxies, timeout=timeout,
                        headers=headers, data=data
                    )
        except filelock.Timeout:
            if error_print is not False and error_print is not None:
                print_err(f"{user} filelock timeout {filelock_timeout}", level=error_print)

            return False
    except requests.exceptions.RequestException as e:
        error_string = str(e)

        if error_print is not False and error_print is not None:
            print_err(error_string, date=False, error=False, level=error_print)

        if "0x04: Host unreachable" in error_string:
            return None
        else:
            return False


def requests_tor(url, user, headers, data=None, options=None):
    requests_options = {
        "until_true": True,
        "error_print": True,
        "timeout": roboauto_options["requests_timeout"],
        "max_retries": roboauto_state["requests_max_retries"]
    }

    if options is not None and options is not False:
        for option in options:
            if option not in requests_options:
                print_err(f"requests option {option} not recognied")
                return False
            else:
                requests_options[option] = options[option]

    until_true = requests_options["until_true"]
    error_print = requests_options["error_print"]
    timeout = requests_options["timeout"]
    max_retries = requests_options["max_retries"]

    if until_true:
        error_happened = False
        response = requests_tor_response(
            url, user, timeout, headers, data, error_print=error_print
        )
        request_failed = 0
        while response_is_error(response):
            error_happened = True
            if error_print is not False and error_print is not None:
                status_code = "error"
                if not isinstance(response, bool) and response is not None:
                    if hasattr(response, "text"):
                        print_err(response.text, date=False, error=False, level=error_print)
                    if hasattr(response, "status_code"):
                        status_code = str(response.status_code)

                print_err(
                    "requests retrying " + url + " status code " + status_code,
                    error=False, level=error_print
                )

            request_failed += 1
            if request_failed >= max_retries:
                if error_print is not False and error_print is not None:
                    print_err("maximum retries reached", level=error_print)
                return False

            time.sleep(roboauto_options["error_interval"])
            response = requests_tor_response(
                url, user, timeout, headers, data, error_print=error_print
            )
        if error_happened:
            if error_print is not False and error_print is not None:
                print_err("requests success " + url, error=False, level=error_print)
        return response
    else:
        response = requests_tor_response(
            url, user, timeout, headers, data, error_print=error_print
        )
        if response_is_error(response):
            if error_print is not False and error_print is not None:
                if \
                    not isinstance(response, bool) and \
                    response is not None and \
                    hasattr(response, "text"):
                    print_err(response.text, date=False, error=False, level=error_print)
        return response


def requests_api_base(base_url, user, url_path, options=None):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": base_url,
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": roboauto_state["fetch_site"]
    }

    return requests_tor(
        base_url + url_path, user, headers, options=options
    )


def requests_api_info(base_url, user, options=None):
    return requests_api_base(
        base_url, user, "/api/info/",
        options=options
    )


def requests_api_book(base_url, user, options=None):
    return requests_api_base(
        base_url, user, "/api/book/?currency=0&type=2",
        options=options
    )


def requests_api_historical(base_url, user, options=None):
    return requests_api_base(
        base_url, user, "/api/historical/",
        options=options
    )


def requests_api_limits(base_url, user, options=None):
    return requests_api_base(
        base_url, user, "/api/limits/",
        options=options
    )


def requests_api_price(base_url, user, options=None):
    return requests_api_base(
        base_url, user, "/api/price/",
        options=options
    )


def requests_api_ticks(
    base_url, user, start_date, end_date, options=None
):
    return requests_api_base(
        base_url, user, f"/api/ticks/?end={end_date}&start={start_date}",
        options=options
    )


def requests_api_robot_generate(
    token_base91, public_key, private_key, base_url, user,
    options=None
):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Authorization":
            "Token " + token_base91 +
            " | Public " + public_key +
            " | Private " + private_key,
        "Origin": "null",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": roboauto_state["fetch_site"]
    }

    return requests_tor(
        base_url + "/api/robot/", user, headers,
        options=options
    )


def requests_api_token(
    token_base91, base_url, user, referer_path, url_path,
    options=None
):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": base_url + referer_path,
        "Content-Type": "application/json",
        "Authorization": "Token " + token_base91,
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": roboauto_state["fetch_site"]
    }

    return requests_tor(
        base_url + url_path, user, headers,
        options=options
    )


def requests_api_robot(token_base91, base_url, user, options=None):
    return requests_api_token(
        token_base91, base_url, user,
        "/robot/",
        "/api/robot/",
        options=options
    )


def requests_api_order(
    token_base91, order_id, base_url, user, options=None
):
    return requests_api_token(
        token_base91, base_url, user,
        "/order/" + order_id,
        "/api/order/?order_id=" + order_id,
        options=options
    )


def requests_api_chat(
    token_base91, order_id, base_url, user, offset=0, options=None
):
    return requests_api_token(
        token_base91, base_url, user,
        "/order/" + order_id,
        "/api/chat/?order_id=" + order_id + "&offset=" + str(offset),
        options=options
    )


def requests_api_post(
    token_base91, base_url, user, referer_path, url_path, data,
    options=None
):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": base_url + referer_path,
        "Content-Type": "application/json",
        "Authorization": "Token " + token_base91,
        "Origin": base_url,
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": roboauto_state["fetch_site"]
    }

    return requests_tor(
        base_url + url_path, user, headers, data=data,
        options=options
    )


def requests_api_make(
    token_base91, base_url, user, make_data,
    options=None
):
    referer_path = ""
    return requests_api_post(
        token_base91,
        base_url, user, referer_path,
        "/api/make/",
        make_data,
        options=options
    )


def requests_api_chat_post(
    token_base91, order_id, base_url, user, message, offset=None,
    options=None
):
    data_json = {
        "PGP_message": message,
        "order_id": order_id
    }
    if offset is not None and offset is not False:
        data_json.update({
            "offset": offset
        })

    return requests_api_post(
        token_base91, base_url, user,
        "/order/" + order_id,
        "/api/chat/",
        json_dumps(data_json),
        options=options
    )


def requests_api_reward(
    token_base91, base_url, user, signed_invoice,
    options=None
):
    return requests_api_post(
        token_base91, base_url, user,
        "/robot/",
        "/api/reward/",
        json_dumps({
            "invoice": signed_invoice
        }),
        options=options
    )


def requests_api_stealth(
    token_base91, base_url, user, wants_stealth,
    options=None
):
    return requests_api_post(
        token_base91, base_url, user,
        "/robot/",
        "/api/stealth/",
        json_dumps({
            "wantsStealth": wants_stealth
        }),
        options=options
    )


def requests_api_order_post(
    token_base91, order_id, base_url, user, order_action,
    options=None
):
    return requests_api_post(
        token_base91, base_url, user,
        "/order/" + order_id,
        "/api/order/?order_id=" + order_id,
        order_action,
        options=options
)


def requests_api_order_invoice(
    token_base91, order_id, base_url, user, signed_invoice, budget_ppm,
    options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "update_invoice",
            "invoice": signed_invoice,
            "routing_budget_ppm": budget_ppm
        }),
        options=options
    )


def requests_api_order_address(
    token_base91, order_id, base_url, user, signed_address, sat_per_vb,
    options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "update_address",
            "address": signed_address,
            "mining_fee_rate": sat_per_vb
        }),
        options=options
    )


def requests_api_order_rate(
    token_base91, order_id, base_url, user, rating,
    options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "rate_platform",
            "rating": rating
        }),
        options=options
    )


def requests_api_order_submit_statement(
    token_base91, order_id, base_url, user, statement, options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "submit_statement",
            "statement": statement
        }),
        options=options
    )


def requests_api_order_take(
    token_base91, order_id, base_url, user, take_amount=None,
    options=None
):
    data_json = {
        "action": "take"
    }
    if take_amount is not None and take_amount is not False:
        data_json.update({
            "amount": take_amount
        })

    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps(data_json),
        options=options
    )


def requests_api_order_pause(
    token_base91, order_id, base_url, user, options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "pause"
        }),
        options=options
    )


def requests_api_order_cancel(
    token_base91, order_id, base_url, user, options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "cancel"
        }),
        options=options
    )


def requests_api_order_confirm(
    token_base91, order_id, base_url, user, options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "confirm"
        }),
        options=options
    )


def requests_api_order_undo_confirm(
    token_base91, order_id, base_url, user, options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "undo_confirm"
        }),
        options=options
    )


def requests_api_order_dispute(
    token_base91, order_id, base_url, user, options=None
):
    return requests_api_order_post(
        token_base91, order_id, base_url, user,
        json_dumps({
            "action": "dispute"
        }),
        options=options
    )
