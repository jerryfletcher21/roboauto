#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=R0913 too-many-arguments
# pylint: disable=R1705 no-else-return

import time

import requests

from roboauto.logger import print_err
from roboauto.global_state import roboauto_options


def response_is_error(response):
    if response is False:
        return True
    if not response.ok:
        if response.status_code not in (400, 403, 404, 409):
            return True

    return False


def requests_tor_response(url, proxies, timeout, headers, data):
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
        print_err(e, error=False, date=False)
        return False


def requests_tor(url, headers, data="", until_true=True):
    proxies = {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050"
    }

    timeout = 120
    max_retries = 8

    if until_true:
        error_happened = False
        response = requests_tor_response(url, proxies, timeout, headers, data)
        request_failed = 0
        while response_is_error(response):
            error_happened = True
            if hasattr(response, "text"):
                print_err(response.text, error=False)
            if hasattr(response, "status_code"):
                status_code = str(response.status_code)
            else:
                status_code = "error"
            print_err(
                "requests retrying " + url + " status code " + status_code,
                error=False
            )

            request_failed += 1
            if request_failed >= max_retries:
                print_err("maximum retries reached")
                return response

            time.sleep(roboauto_options["error_interval"])
            response = requests_tor_response(url, proxies, timeout, headers, data)
        if error_happened:
            print_err("requests success " + url, error=False)
        return response
    else:
        return requests_tor_response(url, proxies, timeout, headers, data)


def requests_api_base(base_url, url_path, until_true=True):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": base_url,
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    return requests_tor(base_url + url_path, headers, until_true=until_true)


def requests_api_info(base_url, until_true=True):
    return requests_api_base(base_url, "/api/info/", until_true=until_true)


def requests_api_book(base_url, until_true=True):
    return requests_api_base(base_url, "/api/book/?currency=0&type=2", until_true=until_true)


def requests_api_limits(base_url, until_true=True):
    return requests_api_base(base_url, "/api/limits/", until_true=until_true)


def requests_api_token(token_base91, base_url, referer_path, url_path, until_true=True):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": base_url + referer_path,
        "Content-Type": "application/json",
        "Authorization": "Token " + token_base91,
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    return requests_tor(base_url + url_path, headers, until_true=until_true)


def requests_api_robot(token_base91, base_url, until_true=True):
    return requests_api_token(
        token_base91, base_url,
        "/robot/",
        "/api/robot/",
        until_true=until_true
    )


def requests_api_order(token_base91, order_id, base_url, until_true=True):
    return requests_api_token(
        token_base91, base_url,
        "/order/" + order_id,
        "/api/order/?order_id=" + order_id,
        until_true=until_true
    )


def requests_api_chat(token_base91, order_id, base_url, until_true=True):
    offset = "2"

    return requests_api_token(
        token_base91, base_url,
        "/order/" + order_id,
        "api/chat/?order_id=" + order_id + "&offset=" + offset,
        until_true=until_true
    )


def requests_api_post(token_base91, base_url, referer_path, url_path, data, until_true=True):
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
        "Sec-Fetch-Site": "same-origin"
    }

    return requests_tor(base_url + url_path, headers, data=data, until_true=until_true)


def requests_api_order_post(token_base91, order_id, base_url, order_action, until_true=True):
    return requests_api_post(
        token_base91, base_url,
        "/order/" + order_id,
        "/api/order/?order_id=" + order_id,
        order_action,
        until_true=until_true
)


def requests_api_cancel(token_base91, order_id, base_url, until_true=True):
    return requests_api_order_post(
        token_base91, order_id, base_url,
        '{ "action": "cancel" }',
        until_true=until_true
    )


def requests_api_make(token_base91, order_id, base_url, make_data, until_true=True):
    if order_id:
        referer_path = "/order/" + order_id
    else:
        referer_path = ""
    return requests_api_post(
        token_base91,
        base_url, referer_path,
        "/api/make/",
        make_data,
        until_true=until_true
    )
