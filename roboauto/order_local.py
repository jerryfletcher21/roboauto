#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0913 too-many-arguments
# pylint: disable=R0914 too-many-locals
# pylint: disable=R0915 too-many-statements
# pylint: disable=R1702 too-many-nested-blocks
# pylint: disable=R1703 simplifiable-if-statement
# pylint: disable=R1705 no-else-return

import os
import re
import shutil

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state
from roboauto.utils import \
    get_date_short, json_dumps, file_json_read, \
    file_is_executable, subprocess_run_command, \
    is_float, get_int, dir_make_sure_exists, file_json_write, \
    directory_get_last_number_file
from roboauto.robot import \
    robot_list_dir, robot_get_coordinator, robot_input_ask, \
    robot_dir_search


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


def get_offer_dic(offer, coordinator):
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
        "coordinator": str(coordinator),
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
        "%-3s %-6s %-24s %-4s %-3s %3sh %5s %6.2f%% %3s " + \
        offer_dic["amount_format"] + " " + offer_dic["amount_format"] + \
        " %5s %s"
    print_out(printf_string % (
        offer_dic["coordinator"][:3],
        offer_dic["offer_id"], offer_dic["maker_nick"],
        offer_dic["order_type"], offer_dic["currency"],
        offer_dic["duration"], offer_dic["bond_size"], float(offer_dic["premium"]),
        offer_dic["ours"],
        float(offer_dic["min_amount"]), float(offer_dic["max_amount"]),
        offer_dic["date_end"],
        offer_dic["payment_method"]
    ))


def print_robot_order(robot, robot_dir, order_id, one_line, full_mode):
    order_id_error = "------"

    coordinator = robot_get_coordinator(robot, robot_dir, warning_print=False)
    coordinator_str = str(coordinator)[:3]

    orders_dir = robot_dir + "/orders"
    if not os.path.isdir(orders_dir):
        if not one_line:
            print_out(json_dumps({"error": "no order dir"}))
        else:
            print_out("%-3s %-6s %-24s no order dir" % (
                coordinator_str, order_id_error, robot
            ))
        return True

    if order_id is False:
        order_file = directory_get_last_number_file(orders_dir)
        if order_file is False:
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
        if full_mode:
            print_out(json_dumps(order_dic))
        else:
            if "order_user" not in order_dic and "order_info" not in order_dic:
                print_out(json_dumps({"error": "no order user and info"}))
            else:
                order_dic_print = {}
                if "order_info" in order_dic:
                    for key in ("coordinator", "order_id", "status_string"):
                        if key in order_dic["order_info"]:
                            order_dic_print.update({key: order_dic["order_info"][key]})
                if "order_user" in order_dic:
                    order_dic_print.update(order_dic["order_user"])
                print_out(json_dumps(order_dic_print))
    else:
        if "order_response_json" in order_dic:
            offer_dic_print(get_offer_dic(
                order_dic["order_response_json"], coordinator
            ))
        else:
            print_out("%-3s %-6s %-24s no order response" % (
                coordinator_str, order_id_error, robot
            ))

    return True


def order_info_local(argv):
    full_mode = False
    if len(argv) > 0:
        if argv[0] == "--full":
            full_mode = True
            argv = argv[1:]

    robot, argv = robot_input_ask(argv)
    if robot is False:
        return False

    if re.match('^-', robot) is None:
        robot_dir = robot_dir_search(robot, error_print=False)
        if robot_dir is False:
            robot_dir = robot
            if os.path.isdir(robot_dir):
                for robot in os.listdir(robot_dir):
                    if not print_robot_order(
                        robot, robot_dir + "/" + robot, False,
                        one_line=True, full_mode=full_mode
                    ):
                        return False
                return True
            else:
                print_err("%s is not a robot and not a directory" % robot)
                return False

        if len(argv) >= 1:
            order_id = argv[0]
            argv = argv[1:]
        else:
            order_id = False

        return print_robot_order(
            robot, robot_dir, order_id, one_line=False, full_mode=full_mode
        )
    elif robot in ("--active", "--paused", "--inactive"):
        if robot == "--active":
            destination_dir = roboauto_state["active_home"]
        elif robot == "--paused":
            destination_dir = roboauto_state["paused_home"]
        elif robot == "--inactive":
            destination_dir = roboauto_state["inactive_home"]

        for robot in os.listdir(destination_dir):
            if not print_robot_order(
                robot, destination_dir + "/" + robot, False,
                one_line=True, full_mode=full_mode
            ):
                return False
    else:
        print_err("option %s not recognized" % robot)
        return False

    return True


def order_save_order_file(robot_dir, order_id, order_dic):
    orders_dir = robot_dir + "/orders"
    if not dir_make_sure_exists(orders_dir):
        return False
    order_file = orders_dir + "/" + order_id
    if not file_json_write(order_file, order_dic):
        print_err("saving order %s to file" % order_id)
        return False

    return True


def order_get_order_dic(orders_dir):
    order_file = directory_get_last_number_file(orders_dir)
    if order_file is False:
        return False

    order_dic = file_json_read(order_file)
    if order_dic is False:
        return False

    return order_dic


def order_get_robot(robot, destination_dir):
    robot_dir = destination_dir + "/" + robot

    orders_dir = robot_dir + "/orders"
    if not os.path.isdir(orders_dir):
        return False

    order_dic = order_get_order_dic(orders_dir)
    if order_dic is False:
        return False

    return order_dic


def orders_get_directory(destination_dir):
    orders = []
    for robot in os.listdir(destination_dir):
        order_dic = order_get_robot(robot, destination_dir)
        if order_dic is False:
            continue

        orders.append(order_dic)

    return orders


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


def get_order_data(
    type_id, currency_id,
    amount, has_range, min_amount, max_amount,
    payment_method, premium,
    public_duration, escrow_duration, bond_size
):
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

    return get_order_data(
        type_id, currency_id,
        amount, has_range, min_amount, max_amount,
        payment_method, premium,
        public_duration, escrow_duration, bond_size
    )
