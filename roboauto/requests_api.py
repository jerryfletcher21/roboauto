#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=R1705 no-else-return

import time

import requests

from roboauto.logger import print_err
from roboauto.global_state import roboauto_options


def requests_tor(url, headers, data="", until_true=True):
    proxies = {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050"
    }

    timeout = 120

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

    def response_is_error(response):
        if response is False:
            return True
        if not response.ok:
            if response.status_code not in (400, 403, 404, 409):
                return True

        return False

    if until_true:
        error_happened = False
        response = requests_tor_response(url, proxies, timeout, headers, data)
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
            time.sleep(roboauto_options["error_interval"])
            response = requests_tor_response(url, proxies, timeout, headers, data)
        if error_happened:
            print_err("requests success " + url, error=False)
        return response
    else:
        return requests_tor_response(url, proxies, timeout, headers, data)


def requests_api_base(url):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": roboauto_options["robosats_url"],
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    return requests_tor(url, headers)


def requests_api_info():
    return requests_api_base(roboauto_options["robosats_url"] + "/api/info/")


def requests_api_book():
    return requests_api_base(roboauto_options["robosats_url"] + "/api/book/?currency=0&type=2")


def requests_api_limits():
    return requests_api_base(roboauto_options["robosats_url"] + "/api/limits/")


def requests_api_token(token_base91, referer, url):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": referer,
        "Content-Type": "application/json",
        "Authorization": "Token " + token_base91,
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    return requests_tor(url, headers)


def requests_api_robot(token_base91):
    return requests_api_token(
        token_base91,
        roboauto_options["robosats_url"] + "/robot/",
        roboauto_options["robosats_url"] + "/api/robot/"
    )


def requests_api_order(token_base91, order_id):
    return requests_api_token(
        token_base91,
        roboauto_options["robosats_url"] + "/order/" + order_id,
        roboauto_options["robosats_url"] + "/api/order/?order_id=" + order_id
    )


def requests_api_chat(token_base91, order_id):
    offset = "2"

    return requests_api_token(
        token_base91,
        roboauto_options["robosats_url"] + "/order/" + order_id,
        roboauto_options["robosats_url"] + "api/chat/?order_id=" + order_id + "&offset=" + offset
    )


def requests_api_post(token_base91, referer, url, data):
    headers = {
        "User-Agent": roboauto_options["user_agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Content-Type": "application/json",
        "Authorization": "Token " + token_base91,
        "Origin": roboauto_options["robosats_url"],
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    return requests_tor(url, headers, data=data)


def requests_api_order_post(token_base91, order_id, order_action):
    return requests_api_post(
        token_base91,
        roboauto_options["robosats_url"] + "/order/" + order_id,
        roboauto_options["robosats_url"] + "/api/order/?order_id=" + order_id,
        order_action
)


def requests_api_cancel(token_base91, order_id):
    return requests_api_order_post(token_base91, order_id, '{ "action": "cancel" }')


def requests_api_make(token_base91, order_id, make_data):
    if order_id:
        referer = roboauto_options["robosats_url"] + "/order/" + order_id
    else:
        referer = roboauto_options["robosats_url"]
    return requests_api_post(
        token_base91,
        referer,
        roboauto_options["robosats_url"] + "/api/make/",
        make_data
    )
