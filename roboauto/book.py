#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

import os
import datetime

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state
from roboauto.robot import robot_list_dir
from roboauto.order import get_offer_dic, offer_dic_print, get_order_file
from roboauto.requests_api import requests_api_book
from roboauto.utils import json_loads, file_json_read


def get_offers_per_hour(relative):
    hours = [[] for _ in range(24)]

    if relative:
        current_timestamp = int(datetime.datetime.now().timestamp())

    for robot in robot_list_dir(roboauto_state["active_home"]):
        robot_dir = roboauto_state["active_home"] + "/" + robot

        orders_dir = robot_dir + "/orders"
        if not os.path.isdir(orders_dir):
            continue
        order_file = get_order_file(orders_dir)
        if order_file is False:
            return False

        order_dic = file_json_read(order_file)
        if order_dic is False:
            return False

        created_at = order_dic["order_response_json"]["created_at"]
        try:
            robosats_date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
            if relative:
                unix_time = int(
                    datetime.datetime.strptime(
                        created_at, robosats_date_format
                    ).replace(
                        tzinfo=datetime.timezone(datetime.timedelta(hours=0))
                    ).timestamp()
                )
                date_hour = (23 - int((current_timestamp - unix_time) / 3600)) % 24
            else:
                date_hour = int(
                    datetime.datetime.strptime(
                        created_at, robosats_date_format
                    ).replace(
                        tzinfo=datetime.timezone(datetime.timedelta(hours=-1))
                    ).astimezone(datetime.timezone.utc).strftime(
                        "%H"
                    )
                )
                # date_hour = int(get_date_short(created_at).split(":")[0])
        except (ValueError, TypeError):
            print_err("getting hour")
            return False

        hours[date_hour].append(robot)

    return hours


def list_offers_per_hour(relative):
    hours = get_offers_per_hour(relative)
    if hours is False:
        return False

    for i, hour in enumerate(hours):
        if i < 10:
            print_out("0", end="")
        print_out("%d %2s" % (i, len(hour)), end="")
        for nick in hour:
            print_out(" %s" % nick, end="")
        print_out("\n", end="")

    return True


def get_book_response_json():
    book_response = requests_api_book().text
    book_response_json = json_loads(book_response)
    if not book_response_json:
        print_err(book_response, error=False, date=False)
        print_err("getting book")
        return False

    for offer in book_response_json:
        if not isinstance(offer, dict):
            print_err(book_response, error=False, date=False)
            print_err("strange book response")
            return False

    return book_response_json


def get_offers_unsorted(book_response_json, book_type, book_currency):
    offers = []
    for offer in book_response_json:
        offer_dic = get_offer_dic(offer)

        if offer_dic["order_type"] == "buy" and book_type == 1:
            continue
        if offer_dic["order_type"] == "sell" and book_type == 0:
            continue

        if book_currency not in ("all", offer_dic["currency"]):
            continue

        offers.append(offer_dic)

    return offers


def list_offers_general(book_response_json, book_type, book_currency, search_element=""):
    offers_unsorted = get_offers_unsorted(book_response_json, book_type, book_currency)
    if offers_unsorted is False:
        print_err("getting unsorted offers")
        return False

    if book_type == 0:
        reverse = True
    elif book_type == 1:
        reverse = False
    else:
        print_err("book type is not 0 or 1")
        return False

    offers_sorted = sorted(offers_unsorted, key=lambda x: float(x["premium"]), reverse=reverse)

    if search_element != "":
        offers_sorted = [
            d for d in offers_sorted \
                if search_element.lower() in d.get("payment_method", "").lower()
        ]

    if len(offers_sorted) >= 1:
        for offer in offers_sorted:
            offer_dic_print(offer)

    return True


def list_offers_buy(argv):
    if len(argv) >= 1:
        currency = argv[0]
        argv = argv[1:]
    else:
        currency = "all"
    if len(argv) >= 1:
        search_element = argv[0]
        argv = argv[1:]
    else:
        search_element = ""

    book_response_json = get_book_response_json()
    if book_response_json is False:
        return False

    return list_offers_general(book_response_json, 0, currency, search_element)


def list_offers_sell(argv):
    if len(argv) >= 1:
        currency = argv[0]
        argv = argv[1:]
    else:
        currency = "all"
    if len(argv) >= 1:
        search_element = argv[0]
        argv = argv[1:]
    else:
        search_element = ""

    book_response_json = get_book_response_json()
    if book_response_json is False:
        return False

    return list_offers_general(book_response_json, 1, currency, search_element)


def list_offers_all(argv):
    if len(argv) >= 1:
        currency = argv[0]
        argv = argv[1:]
    else:
        currency = "all"
    if len(argv) >= 1:
        search_element = argv[0]
        argv = argv[1:]
    else:
        search_element = ""

    book_response_json = get_book_response_json()
    if book_response_json is False:
        return False

    return_status = True

    if list_offers_general(book_response_json, 0, currency, search_element) is False:
        return_status = False

    print_out("\n", end="")

    if list_offers_general(book_response_json, 1, currency, search_element) is False:
        return_status = False

    return return_status
