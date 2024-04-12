#!/usr/bin/env python3

"""order_local.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

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
from roboauto.order_data import \
    get_currency_string, order_is_pending, get_type_string
from roboauto.robot import \
    robot_list_dir, robot_get_dir_dic, robot_load_from_name


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


def get_order_user(
    type_string, currency_string, min_amount_user, max_amount_user,
    payment_method, premium, public_duration, escrow_duration, bond_size
):
    return {
        "type":                 type_string,
        "currency":             currency_string,
        "min_amount":           min_amount_user,
        "max_amount":           max_amount_user,
        "payment_method":       payment_method,
        "premium":              premium,
        "public_duration":      public_duration,
        "escrow_duration":      escrow_duration,
        "bond_size":            bond_size
    }


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

    if order_id is False or order_id is None:
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
    # pylint: disable=R1702 too-many-nested-blocks

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


def order_info_local_print_ordered_list(robot_list):
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
            one_line=True, full_mode=False
        )

    return True


def order_info_dir(argv):
    if len(argv) < 1:
        print_err("insert arguments")
        return False

    first_arg = argv[0]
    argv = argv[1:]
    if first_arg in ("--active", "--pending", "--paused", "--inactive"):
        destination_dir = robot_get_dir_dic()[first_arg[2:]]

        if order_info_local_print_ordered_list(
            os.listdir(destination_dir)
        ) is False:
            return False
    elif first_arg == "--dir":
        if len(argv) < 1:
            print_err("insert directory")
            return False
        robot_dir = argv[0]
        argv = argv[1:]

        if not os.path.isdir(robot_dir):
            print_err(f"{robot_dir} is not a directory")
            return False
        if order_info_local_print_ordered_list(
            os.listdir(robot_dir)
        ) is False:
            return False
    elif re.match('^-', first_arg) is not None:
        print_err(f"option {first_arg} not recognized")
        return False
    else:
        print_err(f"argument {first_arg} not recognized")
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
            roboauto_state["message_notification_command"], "order-taken",
            robot_name + " " + order_id + " " + other
        ])
        if message_output is False:
            print_err("sending message")
            return False
        print_out(message_output.decode(), end="", date=False)
    else:
        print_err("message notification command not found, no messages will be sent")

    return True


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
