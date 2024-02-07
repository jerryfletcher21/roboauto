#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
# pylint: disable=C0302 too-many-lines
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0913 too-many-arguments
# pylint: disable=R0914 too-many-locals
# pylint: disable=R0915 too-many-statements
# pylint: disable=R1703 simplifiable-if-statement
# pylint: disable=R1705 no-else-return

import os
import time
import re
import shutil
import subprocess
import signal

import filelock

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import \
    robot_dir_search, robot_get_lock_file, \
    robot_get_token_base91, robot_list_dir, robot_set_dir, \
    robot_get_coordinator
from roboauto.requests_api import \
    requests_api_order, requests_api_robot, requests_api_cancel, \
    requests_api_make
from roboauto.utils import \
    get_date_short, json_dumps, file_json_read, \
    input_ask_robot, file_is_executable, subprocess_run_command, \
    json_loads, is_float, get_int, dir_make_sure_exists, file_json_write, \
    input_ask, roboauto_get_coordinator_url


def get_type_string(target, reverse=False):
    types = {
        0: "buy",
        1: "sell",
        2: "all"
    }

    if not reverse:
        if target in types:
            return types[target]
        else:
            return "other"
    else:
        for type_id, type_string in types.items():
            if target == type_string:
                return type_id
        return -1


def get_currency_string(target, reverse=False):
    currencies = {
           1: "USD",
           2: "EUR",
           3: "JPY",
           4: "GBP",
           5: "AUD",
           6: "CAD",
           7: "CHF",
           8: "CNY",
           9: "HKD",
          10: "NZD",
          11: "SEK",
          12: "KRW",
          13: "SGD",
          14: "NOK",
          15: "MXN",
          16: "BYN",
          17: "RUB",
          18: "ZAR",
          19: "TRY",
          20: "BRL",
          21: "CLP",
          22: "CZK",
          23: "DKK",
          24: "HRK",
          25: "HUF",
          26: "INR",
          27: "ISK",
          28: "PLN",
          29: "RON",
          30: "ARS",
          31: "VES",
          32: "COP",
          33: "PEN",
          34: "UYU",
          35: "PYG",
          36: "BOB",
          37: "IDR",
          38: "ANG",
          39: "CRC",
          40: "CUP",
          41: "DOP",
          42: "GHS",
          43: "GTQ",
          44: "ILS",
          45: "JMD",
          46: "KES",
          47: "KZT",
          48: "MYR",
          49: "NAD",
          50: "NGN",
          51: "AZN",
          52: "PAB",
          53: "PHP",
          54: "PKR",
          55: "QAR",
          56: "SAR",
          57: "THB",
          58: "TTD",
          59: "VND",
          60: "XOF",
          61: "TWD",
          62: "TZS",
          63: "XAF",
          64: "UAH",
          65: "EGP",
          66: "LKR",
          67: "MAD",
          68: "AED",
          69: "TND",
          70: "ETB",
          71: "GEL",
          72: "UGX",
          73: "RSD",
          74: "IRT",
          75: "BDT",
         300: "XAU",
        1000: "BTC"
    }

    if not reverse:
        if target in currencies:
            return currencies[target]
        else:
            return "???"
    else:
        for currency_id, currency_string in currencies.items():
            if target.upper() == currency_string:
                return currency_id
        return -1


def get_order_string(target, reverse=False):
    status_dic = {
         0: "Waiting for maker bond",
         1: "Public",
         2: "Paused",
         3: "Waiting for taker bond",
         4: "Cancelled",
         5: "Expired",
         6: "Waiting for trade collateral and buyer invoice",
         7: "Waiting only for seller trade collateral",
         8: "Waiting only for buyer invoice",
         9: "Sending fiat - In chatroom",
        10: "Fiat sent - In chatroom",
        11: "In dispute",
        12: "Collaboratively cancelled",
        13: "Sending satoshis to buyer",
        14: "Sucessful trade",
        15: "Failed lightning network routing",
        16: "Wait for dispute resolution",
        17: "Maker lost dispute",
        18: "Taker lost dispute"
    }

    if not reverse:
        if target in status_dic:
            return status_dic[target]
        else:
            return "other"
    else:
        for status_id, status_string in status_dic.items():
            if target == status_string:
                return status_id
        return -1


def order_is_waiting_maker_bond(data):
    if data == 0:
        return True
    else:
        return False


def order_is_waiting_taker_bond(data):
    if data == 3:
        return True
    else:
        return False


def order_is_public(data):
    if data == 1:
        return True
    else:
        return False


def order_is_paused(data):
    if data == 2:
        return True
    else:
        return False


def order_is_expired(data):
    if data == 5:
        return True
    else:
        return False


def order_is_finished(data):
    if data in (4, 12, 14, 17, 18):
        return True
    else:
        return False


def get_offer_dic(offer):
    offer_id = offer.get("id", "")
    expires_at = offer.get("expires_at", "")
    order_type_bool = offer.get("type", "")
    currency_id = offer.get("currency", "")
    amount = offer.get("amount", "")
    has_range = offer.get("has_range", "")
    min_amount = offer.get("min_amount", "")
    max_amount = offer.get("max_amount", "")
    payment_method = offer.get("payment_method", "")
    premium = offer.get("premium", "")
    escrow_duration_seconds = offer.get("escrow_duration", "")
    bond_size = offer.get("bond_size", "")
    maker_nick = offer.get("maker_nick", "")

    if order_type_bool == 0:
        order_type = "buy"
    elif order_type_bool == 1:
        order_type = "sell"
    elif order_type_bool == 2:
        order_type = "all"

    date_end = get_date_short(expires_at)

    currency = get_currency_string(currency_id).lower()

    if not has_range:
        min_amount = amount
        max_amount = amount

    if currency != "btc":
        amount_format = "%7.0f"
    else:
        amount_format = "%7.3f"

    duration = str(int(escrow_duration_seconds / 3600))
    if maker_nick in robot_list_dir(roboauto_state["active_home"]):
        ours = " * "
    else:
        ours = " - "

    offer_dic = {
        "offer_id": offer_id,
        "maker_nick": maker_nick,
        "order_type": order_type,
        "currency": currency,
        "duration": duration,
        "bond_size": bond_size,
        "premium": premium,
        "ours": ours,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "date_end": date_end,
        "payment_method": payment_method,
        "amount_format": amount_format
    }

    return offer_dic


def offer_dic_print(offer_dic):
    printf_string = \
        "%-6s %-24s %-4s %-3s %3sh %5s %6.2f%% %3s " + \
        offer_dic["amount_format"] + " " + offer_dic["amount_format"] + \
        " %5s %s"
    print_out(
        printf_string % (
        offer_dic["offer_id"], offer_dic["maker_nick"],
        offer_dic["order_type"], offer_dic["currency"],
        offer_dic["duration"], offer_dic["bond_size"], float(offer_dic["premium"]),
        offer_dic["ours"],
        float(offer_dic["min_amount"]), float(offer_dic["max_amount"]),
        offer_dic["date_end"],
        offer_dic["payment_method"]
    ))


def print_robot_order(robot, robot_dir, order_id, one_line):
    order_id_error = "------"

    orders_dir = robot_dir + "/orders"
    if not os.path.isdir(orders_dir):
        if not one_line:
            print_out(json_dumps({"error": "no order dir"}))
        else:
            print_out("%-6s %-24s no order dir" % (order_id_error, robot))
        return True

    if order_id is False:
        order_file = orders_dir + "/" + sorted(os.listdir(orders_dir))[-1]
        if not os.path.isfile(order_file):
            print_err("%s is not a file" % order_file)
            return False
    else:
        order_file = orders_dir + "/" + order_id
        if not os.path.isfile(order_file):
            print_err("%s does not have order %s" % (robot, order_id))
            return False

    order_dic = file_json_read(order_file)
    if order_dic is False:
        return False

    if not one_line:
        if "order_user" in order_dic:
            print_out(json_dumps(order_dic["order_user"]))
        else:
            print_out(json_dumps({"error": "no order user"}))
    else:
        if "order_response_json" in order_dic:
            offer_dic_print(get_offer_dic(order_dic["order_response_json"]))
        else:
            print_out("%-6s %-24s no order response" % (order_id_error, robot))

    return True


def order_info_local(argv):
    if len(argv) >= 1:
        robot = argv[0]
        argv = argv[1:]
    else:
        robot = input_ask_robot()
        if robot is False:
            return False
    if robot == "":
        print_err("robot name not set")
        return False

    if re.match('^-', robot) is None:
        if len(argv) >= 1:
            order_id = argv[0]
            argv = argv[1:]
        else:
            order_id = False

        robot_dir = robot_dir_search(robot)
        if robot_dir is False:
            return False

        return print_robot_order(robot, robot_dir, order_id, one_line=False)
    elif robot in ("--active", "--paused", "--inactive"):
        if robot == "--active":
            destination_dir = roboauto_state["active_home"]
        elif robot == "--paused":
            destination_dir = roboauto_state["paused_home"]
        elif robot == "--inactive":
            destination_dir = roboauto_state["inactive_home"]

        for robot in os.listdir(destination_dir):
            if not print_robot_order(
                robot, destination_dir + "/" + robot,
                order_id=False, one_line=True
            ):
                return False
    else:
        print_err("option %s not recognized" % robot)
        return False

    return True


def robot_set_inactive(robot, order_id, other):
    robot_dir = roboauto_state["active_home"] + "/" + robot
    if not os.path.isdir(robot_dir):
        print_err(robot + " is not active")
        return False

    try:
        shutil.move(robot_dir, roboauto_state["inactive_home"])
    except OSError:
        print_err(
            "moving %s to %s" %
            (robot_dir, roboauto_state["inactive_home"])
        )
        return False

    print_out("something happened with " + robot + " " + order_id)

    if file_is_executable(roboauto_state["message_command"]):
        message_output = subprocess_run_command(
            [roboauto_state["message_command"], robot, order_id, other]
        )
        if message_output is False:
            print_err("sending message")
            return False
        print_out(message_output.decode(), end="", date=False)
    else:
        print_err("message-command not found, no messages will be sent")

    return True


def get_empty_order_user():
    return {
        "type":                 False,
        "currency":             False,
        "min_amount":           False,
        "max_amount":           False,
        "payment_method":       False,
        "premium":              False,
        "public_duration":      False,
        "escrow_duration":      False,
        "bond_size":            False
    }


def api_order_get_dic(robot, token_base91, robot_url, order_id):
    order_response_all = requests_api_order(token_base91, order_id, robot_url)
    if order_response_all.status_code == 400:
        return None
    order_response = order_response_all.text
    order_response_json = json_loads(order_response)
    if order_response_json is False:
        print_err(order_response, end="", error=False, date=False)
        print_err("getting order info for " + robot + " " + order_id)
        return False

    status_id = order_response_json.get("status", False)
    type_id = order_response_json.get("type", False)
    currency_id = order_response_json.get("currency", False)
    amount = order_response_json.get("amount", False)
    has_range = order_response_json.get("has_range", False)
    min_amount = order_response_json.get("min_amount", False)
    max_amount = order_response_json.get("max_amount", False)
    payment_method = order_response_json.get("payment_method", False)
    premium = order_response_json.get("premium", False)
    invoice = order_response_json.get("bond_invoice", False)
    satoshis_now = order_response_json.get("satoshis_now", False)
    public_duration = order_response_json.get(
        "public_duration", roboauto_options["default_duration"]
    )
    escrow_duration = order_response_json.get(
        "escrow_duration", roboauto_options["default_escrow"]
    )
    bond_size = order_response_json.get(
        "bond_size", roboauto_options["default_bond_size"]
    )

    status_string = get_order_string(status_id)

    type_string = get_type_string(type_id)

    currency_string = get_currency_string(currency_id).lower()
    if currency_string != "btc":
        amount_format = "%.0f"
    else:
        amount_format = "%.3f"

    if not has_range:
        min_amount_user = amount
        max_amount_user = amount
        amount_string = amount_format % float(amount)
        if not amount_string:
            print_err(order_response, end="", error=False, date=False)
            print_err("format amount: " + amount)
            return False
    else:
        min_amount_user = min_amount
        max_amount_user = max_amount
        min_amount_string = amount_format % float(min_amount)
        max_amount_string = amount_format % float(max_amount)
        if not min_amount_string or not max_amount_string:
            print_err(order_response, end="", error=False, date=False)
            print_err("format amount: " + min_amount + " " + max_amount)
            return False
        amount_string = min_amount_string + "-" + max_amount_string

    order_description = \
        type_string + " " + currency_string + " " + amount_string + " " + \
        premium + " " + payment_method + " " + status_string

    return {
        "order_data": {
            "type":                 type_id,
            "currency":             currency_id,
            "amount":               amount,
            "has_range":            has_range,
            "min_amount":           min_amount,
            "max_amount":           max_amount,
            "payment_method":       payment_method,
            "premium":              premium,
            "public_duration":      public_duration,
            "escrow_duration":      escrow_duration,
            "bond_size":            bond_size
        },
        "order_user": {
            "type":                 type_string,
            "currency":             currency_string,
            "min_amount":           min_amount_user,
            "max_amount":           max_amount_user,
            "payment_method":       payment_method,
            "premium":              premium,
            "public_duration":      str(public_duration),
            "escrow_duration":      str(escrow_duration),
            "bond_size":            bond_size
        },
        "order_info": {
            "order_id":             order_id,
            "status":               status_id,
            "status_string":        status_string,
            "amount_string":        amount_string,
            "order_description":    order_description,
            "invoice":              invoice,
            "satoshis_now":         satoshis_now
        },
        "order_response_json":      order_response_json
    }


def order_data_from_order_user(order_user):
    type_string = order_user.get("type", False)
    if not type_string:
        print_err("type not present")
        return False

    currency_string = order_user.get("currency", False)
    if not currency_string:
        print_err("currency not present")
        return False

    min_amount = order_user.get("min_amount", False)
    if not min_amount:
        print_err("min_amount not present")
        return False

    max_amount = order_user.get("max_amount", False)
    if not max_amount:
        print_err("max_amount not present")
        return False

    payment_method = order_user.get("payment_method", False)
    if not payment_method:
        print_err("payment_method not present")
        return False

    premium = order_user.get("premium", False)
    if not premium:
        print_err("premium not present")
        return False

    public_duration_str = order_user.get("public_duration", False)
    if not public_duration_str:
        print_err("public_duration not present")
        return False

    escrow_duration_str = order_user.get("escrow_duration", False)
    if not escrow_duration_str:
        print_err("escrow_duration not present")
        return False

    bond_size = order_user.get("bond_size", False)
    if not bond_size:
        print_err("bond_size not present")
        return False

    type_id = get_type_string(type_string, reverse=True)
    if type_id < 0:
        print_err("type %s is not valid" % type_string)
        return False

    currency_id = get_currency_string(currency_string, reverse=True)
    if currency_id < 0:
        print_err("currency %s is not valid" % currency_string)
        return False

    if not is_float(min_amount, additional_check="positive"):
        print_err("min amount %s is not a positive number" % min_amount)
        return False

    if not is_float(max_amount, additional_check="positive"):
        print_err("max amount %s is not a positive number" % max_amount)
        return False

    if min_amount != max_amount:
        has_range = True
        amount = None
    else:
        has_range = False
        amount = min_amount

    if len(payment_method) > 70:
        print_err("payment method is longer than 70 characters")
        return False

    if not is_float(premium):
        print_err("premium %s is not a number" % premium)
        return False

    public_duration = get_int(public_duration_str)
    if public_duration is False:
        return False
    min_public_duration = 600
    max_public_duration = 86400
    if public_duration < min_public_duration or public_duration > max_public_duration:
        print_err("public duration should be between %d and %d" % (
            min_public_duration, max_public_duration
        ))
        return False

    escrow_duration = get_int(escrow_duration_str)
    if escrow_duration is False:
        return False
    min_escrow_duration = 1800
    max_escrow_duration = 28800
    if escrow_duration < min_escrow_duration or escrow_duration > max_escrow_duration:
        print_err("escrow duration should be between %d and %d" % (
            min_escrow_duration, max_escrow_duration
        ))
        return False

    if not is_float(bond_size, additional_check="percentage"):
        print_err("bond size %s is not a number between 0 and 100" % bond_size)
        return False

    return {
        "type":                 type_id,
        "currency":             currency_id,
        "amount":               amount,
        "has_range":            has_range,
        "min_amount":           min_amount,
        "max_amount":           max_amount,
        "payment_method":       payment_method,
        "premium":              premium,
        "public_duration":      public_duration,
        "escrow_duration":      escrow_duration,
        "bond_size":            bond_size
    }


def robot_cancel_order(robot, token_base91):
    robot_dir = roboauto_state["active_home"] + "/" + robot
    if not os.path.isdir(robot_dir):
        print_err("robot %s is not in the active directory" % robot)
        return False
    robot_url = roboauto_get_coordinator_url(
        robot_get_coordinator(robot, robot_dir)
    )

    # except filelock.Timeout
    # timeout=
    with filelock.SoftFileLock(robot_get_lock_file(robot)):
        robot_response = requests_api_robot(token_base91, robot_url).text
        robot_response_json = json_loads(robot_response)
        if robot_response_json is False:
            print_err(robot_response, end="", error=False, date=False)
            print_err("getting robot response")
            return False

        order_id_number = robot_response_json.get("active_order_id", False)
        if order_id_number is False:
            print_err(robot_response, end="", error=False, date=False)
            print_err("getting active order_id for " + robot)
            return False

        order_id = str(order_id_number)

        order_dic = api_order_get_dic(robot, token_base91, robot_url, order_id)
        if order_dic is False:
            print_err("order data is false %s %s" % (robot, order_id))
            return False
        elif order_dic is None:
            print_err("order data is none %s %s" % (robot, order_id))
            return False

        orders_dir = robot_dir + "/orders"
        if not dir_make_sure_exists(orders_dir):
            return False
        order_file = orders_dir + "/" + order_id
        if not file_json_write(order_file, order_dic):
            print_err("saving order %s to file" % order_id)
            return False

        status_id = order_dic["order_info"]["status"]

        if \
            not order_is_public(status_id) and \
            not order_is_paused(status_id):
            print_err("robot order %s %s is not public or paused" % (robot, order_id))
            return False

        print_out("robot %s cancel order %s" % (robot, order_id))

        order_post_response = requests_api_cancel(token_base91, order_id, robot_url).text
        order_post_response_json = json_loads(order_post_response)
        if order_post_response_json is False:
            print_err(order_post_response, end="", error=False, date=False)
            print_err("cancelling order %s %s" % (robot, token_base91))
            return False

        bad_requets = order_post_response_json.get("bad_request", False)
        if bad_requets is False:
            print_err(order_post_response, end="", error=False, date=False)
            print_err("getting cancel response %s %s" % (robot, order_id))
            return False

        print_out(bad_requets)

    return True


def bond_order(robot, token_base91, robot_url, order_id, bond_amount):
    order_dic = api_order_get_dic(robot, token_base91, robot_url, order_id)
    if order_dic is False or order_dic is None:
        return False

    order_user = order_dic["order_user"]
    order_info = order_dic["order_info"]

    if not order_is_waiting_maker_bond(order_info["status"]):
        print_err(robot + " " + order_id + " is not expired")
        return False

    print_out(robot + " " + order_id + " " + order_info["order_description"])

    if bond_amount is not False:
        if not file_is_executable(roboauto_state["check_command"]):
            print_err(roboauto_state["check_command"] + " is not an executable script")
            return False
        check_output = subprocess_run_command(
            [roboauto_state["check_command"], order_info["invoice"], str(bond_amount)]
        )
        if check_output is False:
            print_err(
                "check-command returned false, "
                "invoce will not be paid and robot will be moved to inactive"
            )
            return False
        print_out(check_output.decode(), end="", date=False)
        print_out("invoice checked successfully")
    else:
        print_out("%s %s invoice will not be checked" % (robot, order_id))

    if not file_is_executable(roboauto_state["pay_command"]):
        print_err(roboauto_state["pay_command"] + " is not an executable script")
        return False

    pay_subprocess_command = [
        roboauto_state["pay_command"], order_info["invoice"], robot, order_id,
        order_user["type"], order_user["currency"],
        order_info["amount_string"]
    ]
    try:
        with subprocess.Popen(pay_subprocess_command, start_new_session=True) as pay_subprocess:
            while True:
                print_out("checking if order is bonded...")

                order_response = requests_api_order(token_base91, order_id, robot_url).text
                order_response_json = json_loads(order_response)
                if order_response_json is False:
                    print_err(order_response, end="", error=False, date=False)
                    print_err("getting order response of " + robot + " " + order_id)
                    return False

                order_status = order_response_json.get("status", False)
                if order_status is False:
                    print_err(order_response, end="", error=False, date=False)
                    print_err("getting order_status of " + robot + " " + order_id)
                    return False

                if not order_is_waiting_maker_bond(order_status):
                    if not order_is_expired(order_status):
                        print_out("bonded successfully, order is public for " + robot)
                        return_status = True
                    else:
                        print_err("bond expired, will retry next loop for " + robot)
                        return_status = False
                    try:
                        os.killpg(os.getpgid(pay_subprocess.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass

                    return return_status

            time.sleep(roboauto_options["bond_interval"])
    except FileNotFoundError:
        print_err("command %s does not exists" % pay_subprocess_command[0])
        return False

    return False


def make_order(robot, token_base91, robot_url, order_id, make_data, satoshis_now):
    if not make_data["bond_size"]:
        print_err("bond size percentage not defined")
        return False

    if satoshis_now:
        try:
            bond_amount = int(satoshis_now * float(make_data["bond_size"]) / 100)
        except TypeError:
            print_err("bond size not a float")
            return False
    else:
        bond_amount = False

    make_response = requests_api_make(
        token_base91, order_id, robot_url, make_data=json_dumps(make_data)
    ).text
    make_response_json = json_loads(make_response)
    if make_response_json is False:
        print_err(make_data, error=False, date=False)
        print_err("getting response make order for " + robot)
        return False
    order_id_number = make_response_json.get("id", False)
    if order_id_number is False:
        bad_request = make_response_json.get("bad_request", False)
        if bad_request is not False:
            print_err(bad_request, error=False)
            print_err("making order")
        else:
            print_err(make_response, end="", error=False, date=False)
            print_err(make_data, error=False, date=False)
            print_err("getting id of new order for " + robot)
        return False

    order_id = str(order_id_number)

    return bond_order(robot, token_base91, robot_url, order_id, bond_amount)


def order_user_from_argv(argv):
    order_user = get_empty_order_user()

    while len(argv) > 0:
        param = argv[0]
        argv = argv[1:]
        key_value = param.split("=", 1)
        if len(key_value) != 2:
            print_err("parameter %s is not key=value" % param)
            return False
        key, value = key_value
        if key in order_user:
            order_user[key] = value
        else:
            print_err("%s is not a valid key" % key)
            return False

    return order_user


def create_order(argv):
    if len(argv) >= 1:
        robot = argv[0]
        argv = argv[1:]
    else:
        robot = input_ask_robot()
        if robot is False:
            return False
    if robot == "":
        print_err("robot name not set")
        return False

    robot_dir = roboauto_state["active_home"] + "/" + robot
    if not os.path.isdir(robot_dir):
        print_err("robot %s is not in the active directory" % robot)
        return False

    token_base91 = robot_get_token_base91(robot, robot_dir)
    if token_base91 is False:
        print_err("getting token base91 for " + robot)
        return False

    robot_url = roboauto_get_coordinator_url(
        robot_get_coordinator(robot, robot_dir)
    )

    order_user = order_user_from_argv(argv)
    if order_user is False:
        return False

    for key, value in order_user.items():
        if value is False:
            answer = input_ask("-%24s" % (key + ":"))
            if answer is False:
                return False
            order_user[key] = answer

    order_data = order_data_from_order_user(order_user)
    if order_data is False:
        return False

    return make_order(
        robot, token_base91, robot_url,
        False, order_data, False
    )


def cancel_order(argv):
    if len(argv) >= 1:
        robot = argv[0]
        argv = argv[1:]
    else:
        robot = input_ask_robot()
        if robot is False:
            return False
    if robot == "":
        print_err("robot name not set")
        return False

    robot_dir = roboauto_state["active_home"] + "/" + robot
    if not os.path.isdir(robot_dir):
        print_err("robot %s is not in the active directory" % robot)
        return False

    token_base91 = robot_get_token_base91(robot, robot_dir)
    if token_base91 is False:
        print_err("getting token base91 for " + robot)
        return False

    if not robot_cancel_order(robot, token_base91):
        return False

    if not robot_set_dir(roboauto_state["inactive_home"], [robot]):
        return False

    print_out("%s moved to inactive" % robot)

    return True


def recreate_order(argv):
    should_cancel = True
    if len(argv) >= 1:
        if argv[0] == "--no-cancel":
            should_cancel = False
            argv = argv[1:]
        elif re.match('^-', argv[0]) is not None:
            print_err("option %s not recognized" % argv[0])
            return False
    if len(argv) >= 1:
        robot = argv[0]
        argv = argv[1:]
    else:
        robot = input_ask_robot()
        if robot is False:
            return False
    if robot == "":
        print_err("robot name not set")
        return False

    if should_cancel:
        robot_dir = roboauto_state["active_home"] + "/" + robot
        if not os.path.isdir(robot_dir):
            print_err("robot %s is not in the active directory" % robot)
            return False
    else:
        robot_dir = roboauto_state["paused_home"] + "/" + robot
        if not os.path.isdir(robot_dir):
            robot_dir = roboauto_state["inactive_home"] + "/" + robot
            if not os.path.isdir(robot_dir):
                print_err("robot %s is not in the paused or inactive directories" % robot)
                return False

    token_base91 = robot_get_token_base91(robot, robot_dir)
    if token_base91 is False:
        print_err("getting token base91 for " + robot)
        return False

    robot_url = roboauto_get_coordinator_url(
        robot_get_coordinator(robot, robot_dir)
    )

    if len(argv) > 0:
        order_user_changed = True
    else:
        order_user_changed = False

    order_user = order_user_from_argv(argv)
    if order_user is False:
        return False

    if should_cancel:
        if not robot_cancel_order(robot, token_base91):
            return False

    orders_dir = robot_dir + "/orders"
    if not os.path.isdir(orders_dir):
        print_err("%s is not a dir" % orders_dir)
        return False

    order_file = orders_dir + "/" + sorted(os.listdir(orders_dir))[-1]
    if not os.path.isfile(order_file):
        print_err("%s is not a file" % order_file)
        return False

    order_dic = file_json_read(order_file)
    if order_dic is False:
        return False

    order_info = order_dic["order_info"]
    order_id = order_info["order_id"]
    if order_user_changed or not should_cancel:
        satoshis_now = False
    else:
        satoshis_now = order_info["satoshis_now"]

    order_user_old = order_dic["order_user"]
    for key, value in order_user.items():
        if value is False:
            order_user[key] = order_user_old[key]

    order_data = order_data_from_order_user(order_user)
    if order_data is False:
        return False

    if not make_order(
        robot, token_base91, robot_url,
        order_id, order_data, satoshis_now
    ):
        return False

    if should_cancel is False:
        if not robot_set_dir(roboauto_state["active_home"], [robot]):
            return False

    return True


def wait_order(robot):
    if os.path.isfile(roboauto_state["waiting_queue_file"]):
        nicks_waiting = file_json_read(roboauto_state["waiting_queue_file"])
        if nicks_waiting is False:
            print_err("reading waiting queue")
            return False
    else:
        nicks_waiting = []

    nicks_waiting.append(robot)
    print_out(robot + " added to waiting queue")
    if file_json_write(roboauto_state["waiting_queue_file"], nicks_waiting) is False:
        print_err("writing waiting queue")
        return False

    return False
