#!/usr/bin/env python3

"""book.py"""

# pylint: disable=C0116 missing-function-docstring

import os

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state
from roboauto.robot import robot_list_dir, waiting_queue_get
from roboauto.order_data import get_currency_string, order_is_public
from roboauto.order_local import \
    get_offer_dic, offer_dic_print, order_dic_from_robot_dir
from roboauto.requests_api import response_is_error, requests_api_book
from roboauto.date_utils import \
    get_hour_offer, get_current_timestamp
from roboauto.utils import \
    json_loads, roboauto_get_multi_coordinators_from_argv, \
    roboauto_get_coordinator_url, file_json_write, file_json_read


def get_offers_per_hour(relative):
    # 24 hours robots online
    # NO robot [n]ot [o]nline
    # WG robot in [w]aiting [q]ueue
    hours_fields = 26

    hours = [[] for _ in range(hours_fields)]

    current_timestamp = get_current_timestamp()

    nicks_waiting = waiting_queue_get()

    hours[hours_fields - 1] = nicks_waiting

    for robot_name in robot_list_dir(roboauto_state["active_home"]):
        if robot_name in nicks_waiting:
            continue

        robot_dir = roboauto_state["active_home"] + "/" + robot_name

        order_dic = order_dic_from_robot_dir(
            robot_dir, order_id=None, error_print=False
        )
        if order_dic is False or order_dic is None:
            continue

        status_id = order_dic["order_info"]["status"]
        if order_is_public(status_id):
            expires_at = order_dic["order_response_json"]["expires_at"]
            date_hour = get_hour_offer(expires_at, current_timestamp, relative)
            if date_hour is False:
                print_err(f"robot {robot_name} getting expire hour")
                return False

            hours[date_hour].append(robot_name)
        else:
            hours[hours_fields - 2].append(robot_name)

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
        elif i == 24:
            print_out("NO", end="")
        elif i == 25:
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

    if roboauto_state["current_command_type"] == "keep-online":
        level_print = 1
    else:
        level_print = 0

    # in keep-online print to the terminal the errors of book requests
    # just when the verbosity is at least 1, but still print in the logs
    book_response_all = requests_api_book(
        base_url, coordinator, options={
            "until_true": until_true,
            "error_print": level_print
        }
    )
    if response_is_error(book_response_all):
        print_err(f"{coordinator} book response", level=level_print)
        return False
    book_response = book_response_all.text

    book_response_json = json_loads(book_response)
    if book_response_json is False:
        print_err(book_response, error=False, date=False, level=level_print)
        print_err(f"{coordinator} getting book", level=level_print)
        return False

    if not isinstance(book_response_json, list):
        if book_response_json != {"not_found": "No orders found, be the first to make one"}:
            print_err(book_response, error=False, date=False, level=level_print)
            print_err(f"{coordinator} book response is not a list", level=level_print)
            return False
        else:
            book_response_json = []

    for offer in book_response_json:
        if not isinstance(offer, dict):
            print_err(book_response, error=False, date=False, level=level_print)
            print_err(
                f"{coordinator} an element of book response is not a dict",
                level=level_print
            )
            return False

    if not file_json_write(
        roboauto_state["coordinators_home"] + "/" + coordinator, book_response_json
    ):
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


def get_multi_book_response_json(coordinators, until_true=False, book_local=False):
    multi_book_response_json = []

    for coordinator in coordinators:
        if book_local is False:
            book_response_json = get_book_response_json(
                coordinator, until_true=until_true
            )
        else:
            book_response_file = roboauto_state["coordinators_home"] + "/" + coordinator
            if os.path.isfile(book_response_file):
                book_response_json = file_json_read(book_response_file)
            else:
                print_err(f"{coordinator} local book not present")
                book_response_json = False
        if book_response_json is False:
            continue

        multi_book_response_json.append({
            "offers": book_response_json,
            "coordinator": coordinator
        })

    if len(multi_book_response_json) < 1:
        print_err("getting all books")
        return False

    return multi_book_response_json


def list_offers_argv(argv: list):
    until_true = False
    book_local = False
    while len(argv) >= 1:
        if argv[0] == "--until-success":
            argv = argv[1:]
            until_true = True
        elif argv[0] == "--local":
            argv = argv[1:]
            book_local = True
        else:
            break

    if until_true is True and book_local is True:
        print_err("--until-success and --local can not be both present")
        return False

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
    if int(get_currency_string(currency, reverse=True)) < 0:
        print_err(f"currency {currency} is not valid")
        return False

    if len(argv) >= 1:
        search_element = argv[0]
        argv = argv[1:]
    else:
        search_element = ""

    multi_book_response_json = get_multi_book_response_json(
        coordinators, until_true=until_true, book_local=book_local
    )
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
