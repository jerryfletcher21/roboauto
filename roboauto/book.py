#!/usr/bin/env python3

"""book.py"""

# pylint: disable=C0116 missing-function-docstring

import datetime

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import robot_list_dir, waiting_queue_get
from roboauto.order_data import get_currency_string
from roboauto.order_local import \
    get_offer_dic, offer_dic_print, order_get_order_dic
from roboauto.requests_api import response_is_error, requests_api_book
from roboauto.utils import \
    json_loads, roboauto_get_multi_coordinators_from_argv, roboauto_get_coordinator_url


def get_hour_offer(hour_timestamp, current_timestamp, relative):
    """get the hour from the timestamp, if relative the hour relative
    to current timestamp"""
    try:
        robosats_date_format = roboauto_state["robot_date_format"]
        if relative:
            unix_time = int(
                datetime.datetime.strptime(
                    hour_timestamp, robosats_date_format
                ).replace(
                    tzinfo=datetime.timezone(datetime.timedelta(hours=0))
                ).timestamp()
            )
            date_hour = (23 - int((current_timestamp - unix_time) / 3600)) % 24
        else:
            time_zone = roboauto_options["time_zone"]
            date_hour = int(
                datetime.datetime.strptime(
                    hour_timestamp, robosats_date_format
                ).replace(
                    tzinfo=datetime.timezone(datetime.timedelta(hours=time_zone))
                ).astimezone(datetime.timezone.utc).strftime(
                    "%H"
                )
            )
    except (ValueError, TypeError):
        print_err("getting hour")
        return False

    return date_hour


def get_current_timestamp():
    return int(datetime.datetime.now().timestamp())


def get_current_hour_from_timestamp(timestamp):
    return int(
        datetime.datetime.fromtimestamp(timestamp).replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=0))
        ).astimezone(datetime.timezone.utc).strftime(
            "%H"
        )
    )


def get_current_minutes_from_timestamp(timestamp):
    return int(
        datetime.datetime.fromtimestamp(timestamp).replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=0))
        ).astimezone(datetime.timezone.utc).strftime(
            "%M"
        )
    )


def get_offers_per_hour(relative):
    hours = [[] for _ in range(25)]

    current_timestamp = get_current_timestamp()

    nicks_waiting = waiting_queue_get()

    hours[24] = nicks_waiting

    for robot_name in robot_list_dir(roboauto_state["active_home"]):
        if robot_name in nicks_waiting:
            continue

        robot_dir = roboauto_state["active_home"] + "/" + robot_name

        order_dic = order_get_order_dic(robot_dir, error_print=False)
        if order_dic is False:
            continue

        expires_at = order_dic["order_response_json"]["expires_at"]
        date_hour = get_hour_offer(expires_at, current_timestamp, relative)
        if date_hour is False:
            print_err(f"robot {robot_name} getting expire hour")
            return False

        hours[date_hour].append(robot_name)

    return hours


def list_offers_per_hour(relative):
    hours = get_offers_per_hour(relative)
    if hours is False:
        return False

    for i, hour in enumerate(hours):
        if i < 10:
            print_out("0", end="")
        if i < 24:
            # pylint: disable=C0209 consider-using-f-string
            print_out("%d" % i, end="")
        else:
            print_out("WQ", end="")
        # pylint: disable=C0209 consider-using-f-string
        print_out(" %2s" % len(hour), end="")
        for nick in hour:
            # pylint: disable=C0209 consider-using-f-string
            print_out(" %s" % nick, end="")
        print_out("\n", end="")

    return True


def list_offers_per_hour_argv(argv):
    hour_relative = False
    if len(argv) > 0 and argv[0] == "--relative":
        hour_relative = True
        argv = argv[1:]

    return list_offers_per_hour(hour_relative)


def get_book_response_json(coordinator, until_true=False):
    """wrap around requests_api_book to check if the response
    is correct"""
    base_url = roboauto_get_coordinator_url(coordinator)
    if base_url is False:
        return False

    # if quiet do not print to the terminal when there are errors
    # making the book requests, but still print in the logs
    if roboauto_state["quiet"] is True:
        error_print_book = "file"
        terminal = False
    else:
        error_print_book = True
        terminal = True
    book_response_all = requests_api_book(
        base_url, until_true=until_true, error_print=error_print_book
    )
    if response_is_error(book_response_all):
        print_err(f"connecting to coordinator {coordinator}", terminal=terminal)
        return False
    book_response = book_response_all.text

    book_response_json = json_loads(book_response)
    if book_response_json is False:
        print_err(book_response, error=False, date=False)
        print_err("getting book")
        return False

    if not isinstance(book_response_json, list):
        if book_response_json == {"not_found": "No orders found, be the first to make one"}:
            return []

        print_err(book_response, error=False, date=False)
        print_err("book response is not a list")
        return False

    for offer in book_response_json:
        if not isinstance(offer, dict):
            print_err(book_response, error=False, date=False)
            print_err("an element of book response is not a dict")
            return False

    return book_response_json


def get_offers_unsorted(multi_book_response_json, book_type, book_currency):
    """get offers unsorted from multi responses,
    filtering type and currency"""
    offers = []
    for book in multi_book_response_json:
        book_response_json = book["offers"]
        coordinator = book["coordinator"]
        for offer in book_response_json:
            offer_dic = get_offer_dic(offer, coordinator)

            if offer_dic["order_type"] == "buy" and book_type == 1:
                continue
            if offer_dic["order_type"] == "sell" and book_type == 0:
                continue

            if book_currency not in ("all", offer_dic["currency"]):
                continue

            offers.append(offer_dic)

    return offers


def list_offers_general(
    multi_book_response_json, book_type, book_currency, search_element=""
):
    offers_unsorted = get_offers_unsorted(multi_book_response_json, book_type, book_currency)
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


def get_multi_book_response_json(coordinators):
    multi_book_response_json = []

    for coordinator in coordinators:
        book_response_json = get_book_response_json(coordinator, until_true=False)

        if book_response_json is False:
            print_err(f"getting book coordinator {coordinator}")
            continue

        multi_book_response_json.append({
            "offers": book_response_json,
            "coordinator": coordinator
        })

    if len(multi_book_response_json) < 1:
        print_err("getting all books")
        return False

    return multi_book_response_json


def list_offers_argv(argv):
    coordinators, argv = roboauto_get_multi_coordinators_from_argv(argv)
    if coordinators is False:
        return False

    which_offers = "all"
    if len(argv) >= 1:
        if argv[0] == "--sell":
            which_offers = "sell"
            argv = argv[1:]
        elif argv[0] == "--buy":
            which_offers = "sell"
            argv = argv[1:]

    if len(argv) >= 1:
        currency = argv[0]
        argv = argv[1:]
    else:
        currency = "all"
    if get_currency_string(currency, reverse=True) < 0:
        print_err(f"currency {currency} is not valid")
        return False

    if len(argv) >= 1:
        search_element = argv[0]
        argv = argv[1:]
    else:
        search_element = ""

    multi_book_response_json = get_multi_book_response_json(coordinators)
    if multi_book_response_json is False:
        return False

    return_status = True

    if which_offers in ("all", "buy"):
        if list_offers_general(
            multi_book_response_json, 0, currency, search_element
        ) is False:
            return_status = False

    if which_offers == "all":
        print_out("\n", end="")

    if which_offers in ("all", "sell"):
        if list_offers_general(
            multi_book_response_json, 1, currency, search_element
        ) is False:
            return_status = False

    return return_status
