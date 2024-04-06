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
    robot_list_dir, robot_input_from_argv, \
    robot_get_dir_dic, robot_load_from_name


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


def order_is_waiting_taker_bond(data):
    if data == 3:
        return True
    else:
        return False


def order_is_cancelled(data):
    if data == 4:
        return True
    else:
        return False


def order_is_expired(data):
    if data == 5:
        return True
    else:
        return False


def order_is_waiting_seller_buyer(data):
    if data == 6:
        return True
    else:
        return False


def order_is_waiting_seller(data):
    if data == 7:
        return True
    else:
        return False


def order_is_waiting_buyer(data):
    if data == 8:
        return True
    else:
        return False


def order_is_in_dispute(data):
    if data in (11, 16):
        return True
    else:
        return False


def order_is_pending(data):
    if data in (6, 7, 8, 9, 10, 11, 13, 15, 16):
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
        " %8s %s"
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


def order_dic_from_robot_dic(robot_dic, order_id):
    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]

    orders_dir = robot_dir + "/orders"
    if not os.path.isdir(orders_dir):
        return None

    if order_id is False:
        order_file = directory_get_last_number_file(orders_dir)
        if order_file is False:
            return False
    else:
        order_file = orders_dir + "/" + order_id
        if not os.path.isfile(order_file):
            print_err("%s does not have order %s" % (robot_name, order_id))
            return False

    order_dic = file_json_read(order_file)
    if order_dic is False:
        return False

    return order_dic


def robot_order_not_complete_print(robot_name, coordinator, error_string):
    print_out(
        "%-3s %-6s %-24s %4s %3s %4s %5s %7s %3s %7s %7s %8s %s" % (
            str(coordinator)[:3], "------", robot_name,
            "----", "---", "----", "-----", "-------",
            "---", "-------", "-------", "--------",
            error_string
        )
    )


def robot_no_order_dir_print(robot_name, coordinator):
    robot_order_not_complete_print(robot_name, coordinator, "no order dir")


def robot_no_order_response_print(robot_name, coordinator):
    robot_order_not_complete_print(robot_name, coordinator, "no order response")


def order_dic_print(order_dic, robot_name, coordinator, one_line, full_mode):
    if not one_line:
        if full_mode:
            print_out(json_dumps(order_dic))
        else:
            if "order_user" not in order_dic and "order_info" not in order_dic:
                print_out(json_dumps({"error": "no order user and info"}))
            else:
                order_dic_list = {}
                if "order_info" in order_dic:
                    for key in ("coordinator", "order_id", "status_string"):
                        if key in order_dic["order_info"]:
                            order_dic_list.update({key: order_dic["order_info"][key]})
                if "order_user" in order_dic:
                    order_dic_list.update(order_dic["order_user"])
                print_out(json_dumps(order_dic_list))
    else:
        if "order_response_json" in order_dic:
            offer_dic_print(get_offer_dic(
                order_dic["order_response_json"], coordinator
            ))
        else:
            robot_no_order_response_print(robot_name, coordinator)


def robot_order_print(robot_dic, order_id, one_line, full_mode):
    robot_name = robot_dic["name"]
    coordinator = robot_dic["coordinator"]

    order_dic = order_dic_from_robot_dic(robot_dic, order_id)
    if order_dic is None:
        if not one_line:
            print_out(json_dumps({"error": "no order dir"}))
        else:
            robot_no_order_dir_print(robot_name, coordinator)
        return True
    elif order_dic is False:
        return False

    order_dic_print(order_dic, robot_name, coordinator, one_line, full_mode)

    return True


def order_info_local_print_ordered_list(robot_list, full_mode):
    order_list_unsorted = []
    robot_list_no_response = []
    robot_list_no_dir = []
    for robot_name in robot_list:
        robot_dic = robot_load_from_name(robot_name, error_print=False)
        if robot_dic is False:
            continue

        order_dic = order_dic_from_robot_dic(robot_dic, False)
        if order_dic is None:
            robot_list_no_dir.append(robot_dic)
        elif order_dic is not False:
            if order_dic.get("order_response_json", False) is not False:
                order_list_unsorted.append({
                    "order_dic": order_dic,
                    "robot_name": robot_name,
                    "coordinator": robot_dic["coordinator"]
                })
            else:
                robot_list_no_response.append(robot_dic)

    for robot_dic in robot_list_no_dir:
        robot_no_order_dir_print(robot_dic["name"], robot_dic["coordinator"])
    for robot_dic in robot_list_no_response:
        robot_no_order_response_print(robot_dic["name"], robot_dic["coordinator"])

    order_list_sorted = sorted(
        order_list_unsorted,
        key=lambda order_data: float(order_data["order_dic"]["order_response_json"]["premium"])
    )
    for order_data in order_list_sorted:
        order_dic_print(
            order_data["order_dic"], order_data["robot_name"], order_data["coordinator"],
            one_line=True, full_mode=full_mode
        )

    return True


def order_info_local(argv):
    full_mode = False
    if len(argv) > 0:
        if argv[0] == "--full":
            full_mode = True
            argv = argv[1:]

    first_arg = argv[0]
    if first_arg in ("--active", "--pending", "--paused", "--inactive"):
        argv = argv[1:]
        destination_dir = robot_get_dir_dic()[first_arg[2:]]

        if order_info_local_print_ordered_list(
            os.listdir(destination_dir), full_mode
        ) is False:
            return False
    elif first_arg == "--dir":
        argv = argv[1:]
        if len(argv) < 1:
            print_err("insert directory")
            return False
        robot_dir = argv[0]
        argv = argv[1:]

        if not os.path.isdir(robot_dir):
            print_err(f"{robot_dir} is not a directory")
            return False
        if order_info_local_print_ordered_list(
            os.listdir(robot_dir), full_mode
        ) is False:
            return False
    elif re.match('^-', first_arg) is not None:
        argv = argv[1:]
        print_err("option %s not recognized" % first_arg)
        return False
    else:
        robot_dic, argv = robot_input_from_argv(argv)
        if robot_dic is False:
            return False

        if len(argv) >= 1:
            order_id = argv[0]
            argv = argv[1:]
        else:
            order_id = False

        if not robot_order_print(
            robot_dic, order_id, one_line=False, full_mode=full_mode
        ):
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


def order_get_order_dic(robot_dir, error_print=True):
    orders_dir = robot_dir + "/orders"
    if not os.path.isdir(orders_dir):
        if error_print:
            print_err("%s is not a dir" % orders_dir)
        return False

    order_file = directory_get_last_number_file(orders_dir, error_print=error_print)
    if order_file == 0:
        if error_print:
            print_err("orders dir is empty")
        return False
    elif order_file is False:
        return False

    order_dic = file_json_read(order_file)
    if order_dic is False:
        return False

    return order_dic


def robot_handle_taken(robot_name, status_id, order_id, other):
    robot_dir = roboauto_state["active_home"] + "/" + robot_name
    if not os.path.isdir(robot_dir):
        print_err(robot_name + " is not active")
        return False

    if order_is_pending(status_id):
        dest_dir = roboauto_state["pending_home"]
        dest_name = "pending"
    else:
        dest_dir = roboauto_state["inactive_home"]
        dest_name = "inactive"

    print_out("something happened with " + robot_name + " " + order_id)
    print_out("%s moved to %s" % (robot_name, dest_name))

    try:
        shutil.move(robot_dir, dest_dir)
    except OSError:
        print_err(
            "moving %s to %s" %
            (robot_dir, dest_dir)
        )
        return False

    if file_is_executable(roboauto_state["message_notification_command"]):
        message_output = subprocess_run_command([
            roboauto_state["message_notification_command"],
            robot_name + " " + order_id + " " + other
        ])
        if message_output is False:
            print_err("sending message")
            return False
        print_out(message_output.decode(), end="", date=False)
    else:
        print_err("message notification command not found, no messages will be sent")

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
