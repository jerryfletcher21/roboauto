#!/usr/bin/env python3

"""requests_api.py"""

# pylint: disable=C0116 missing-function-docstring

import time

import requests

from roboauto.logger import print_err
from roboauto.utils import json_dumps
from roboauto.global_state import roboauto_options, roboauto_state


def response_is_error(response):
    if response is False:
        return True
    if not response.ok:
        if response.status_code not in (400, 403, 404, 409):
            return True

    return False


def requests_tor_response(url, proxies, timeout, headers, data, error_print=True):
    try:
        if data == "":
            return requests.get(
                url, proxies=proxies, timeout=timeout,
                headers=headers
            )
        else:
            return requests.post(
                url, proxies=proxies, timeout=timeout,
                headers=headers, data=data
            )
    except requests.exceptions.RequestException as e:
        if error_print is not False and error_print is not None:
            terminal = error_print != "file"
            print_err(e, date=False, error=False, terminal=terminal)
        return False


def requests_tor(url, headers, data="", until_true=True, error_print=True):
    proxies = {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050"
    }

    timeout = 120
    max_retries = 8

    if error_print is not False and error_print is not None:
        terminal = error_print != "file"

    if until_true:
        error_happened = False
        response = requests_tor_response(
            url, proxies, timeout, headers, data, error_print=error_print
        )
        request_failed = 0
        while response_is_error(response):
            error_happened = True
            if error_print is not False and error_print is not None:
                if hasattr(response, "text"):
                    print_err(response.text, date=False, error=False, terminal=terminal)
                if hasattr(response, "status_code"):
                    status_code = str(response.status_code)
                else:
                    status_code = "error"
                print_err(
                    "requests retrying " + url + " status code " + status_code,
                    error=False, terminal=terminal
                )

            request_failed += 1
            if request_failed >= max_retries:
                if error_print is not False and error_print is not None:
                    print_err("maximum retries reached", terminal=terminal)
                return False

            time.sleep(roboauto_options["error_interval"])
            response = requests_tor_response(
                url, proxies, timeout, headers, data, error_print=error_print
            )
        if error_happened:
            if error_print is not False and error_print is not None:
                print_err("requests success " + url, error=False, terminal=terminal)
        return response
    else:
        return requests_tor_response(
            url, proxies, timeout, headers, data, error_print=error_print
        )


def requests_api_base(base_url, url_path, until_true=True, error_print=True):
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
        base_url + url_path, headers, until_true=until_true, error_print=error_print
    )


def requests_api_info(base_url, until_true=True, error_print=True):
    return requests_api_base(
        base_url, "/api/info/", until_true=until_true, error_print=error_print
    )


def requests_api_book(base_url, until_true=True, error_print=True):
    return requests_api_base(
        base_url, "/api/book/?currency=0&type=2",
        until_true=until_true, error_print=error_print
    )


def requests_api_historical(base_url, until_true=True, error_print=True):
    return requests_api_base(
        base_url, "/api/historical/", until_true=until_true, error_print=error_print
    )


def requests_api_limits(base_url, until_true=True, error_print=True):
    return requests_api_base(
        base_url, "/api/limits/", until_true=until_true, error_print=error_print
    )


def requests_api_price(base_url, until_true=True, error_print=True):
    return requests_api_base(
        base_url, "/api/price/", until_true=until_true, error_print=error_print
    )


def requests_api_ticks(base_url, start_date, end_date, until_true=True, error_print=True):
    return requests_api_base(
        base_url, f"/api/ticks/?end={end_date}&start={start_date}",
        until_true=until_true, error_print=error_print
    )


def requests_api_robot_generate(
    token_base91, public_key, private_key, base_url, until_true=True, error_print=True
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
        base_url + "/api/robot/", headers, until_true=until_true, error_print=error_print
    )


def requests_api_token(
    token_base91, base_url, referer_path, url_path, until_true=True, error_print=True
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
        base_url + url_path, headers, until_true=until_true, error_print=error_print
    )


def requests_api_robot(token_base91, base_url, until_true=True, error_print=True):
    return requests_api_token(
        token_base91, base_url,
        "/robot/",
        "/api/robot/",
        until_true=until_true, error_print=error_print
    )


def requests_api_order(token_base91, order_id, base_url, until_true=True, error_print=True):
    return requests_api_token(
        token_base91, base_url,
        "/order/" + order_id,
        "/api/order/?order_id=" + order_id,
        until_true=until_true, error_print=error_print
    )


def requests_api_chat(
    token_base91, order_id, base_url, offset=0, until_true=True, error_print=True
):
    return requests_api_token(
        token_base91, base_url,
        "/order/" + order_id,
        "/api/chat/?order_id=" + order_id + "&offset=" + str(offset),
        until_true=until_true, error_print=error_print
    )


def requests_api_post(
    token_base91, base_url, referer_path, url_path, data, until_true=True, error_print=True
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
        base_url + url_path, headers, data=data, until_true=until_true, error_print=error_print
    )


def requests_api_make(
    token_base91, order_id, base_url, make_data, until_true=True, error_print=True
):
    if order_id:
        referer_path = "/order/" + order_id
    else:
        referer_path = ""
    return requests_api_post(
        token_base91,
        base_url, referer_path,
        "/api/make/",
        make_data,
        until_true=until_true, error_print=error_print
    )


def requests_api_chat_post(
    token_base91, order_id, base_url, message, offset=None, until_true=True, error_print=True
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
        token_base91, base_url,
        "/order/" + order_id,
        "/api/chat/",
        json_dumps(data_json),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_post(
    token_base91, order_id, base_url, order_action, until_true=True, error_print=True
):
    return requests_api_post(
        token_base91, base_url,
        "/order/" + order_id,
        "/api/order/?order_id=" + order_id,
        order_action,
        until_true=until_true, error_print=error_print
)


def requests_api_order_invoice(
    token_base91, order_id, base_url, signed_invoice, budget_ppm,
    until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "update_invoice",
            "invoice": signed_invoice,
            "routing_budget_ppm": budget_ppm
        }),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_rate(
    token_base91, order_id, base_url, rating, until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "rate_platform",
            "rating": rating
        }),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_take(
    token_base91, order_id, base_url, take_amount=None, until_true=True, error_print=True
):
    data_json = {
        "action": "take"
    }
    if take_amount is not None and take_amount is not False:
        data_json.update({
            "amount": take_amount
        })

    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps(data_json),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_pause(
    token_base91, order_id, base_url, until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "pause"
        }),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_cancel(
    token_base91, order_id, base_url, until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "cancel"
        }),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_confirm(
    token_base91, order_id, base_url, until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "confirm"
        }),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_undo_confirm(
    token_base91, order_id, base_url, until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "undo_confirm"
        }),
        until_true=until_true, error_print=error_print
    )


def requests_api_order_dispute(
    token_base91, order_id, base_url, until_true=True, error_print=True
):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        json_dumps({
            "action": "dispute"
        }),
        until_true=until_true, error_print=error_print
    )
