#!/usr/bin/env python3

"""order_argv.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

import os
import re

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_options
from roboauto.order import \
    order_user_empty_get, make_order, robot_cancel_order, order_write_initial_message_to_file, \
    order_read_initial_message_from_file, order_remove_initial_message_file
from roboauto.order_data import \
    get_all_currencies, get_fiat_payment_methods, get_swap_payment_methods, \
    order_is_finished, order_is_finished_for_seller
from roboauto.order_local import \
    order_data_from_order_user, order_dic_from_robot_dir
from roboauto.robot import \
    robot_input_from_argv, robot_change_dir, robot_load_from_name, \
    robot_var_from_dic
from roboauto.requests_api import \
    requests_api_review, response_is_error
from roboauto.utils import \
    json_dumps, get_int, json_loads, input_ask, get_uint, \
    file_json_read, file_json_write, file_remove, roboauto_get_coordinator
from roboauto.nostr import nostr_pubkey_from_token, nostr_create_publish_event


def list_currencies():
    currencies = get_all_currencies()
    for _, currency in currencies.items():
        print_out(currency.lower())

    return True


def list_payment_methods(argv):
    fiat_present = True
    swap_present = True
    if len(argv) > 0:
        if argv[0] == "--fiat":
            swap_present = False
            argv = argv[1:]
        elif argv[0] == "--swap":
            fiat_present = False
            argv = argv[1:]

    payment_methods = []

    if fiat_present:
        payment_methods += get_fiat_payment_methods()

    if swap_present:
        payment_methods += get_swap_payment_methods()

    for method in payment_methods:
        print_out(method)

    return True


def list_order_fields():
    empty_order_user = order_user_empty_get()
    for item in empty_order_user:
        print_out(item)

    return True


def order_user_from_argv(argv, with_default=False, only_set=False):
    """get order_user's fields from argv"""
    order_user = order_user_empty_get()
    order_user_old = order_user_empty_get()

    if len(argv) > 0 and argv[0] == "--from-robot":
        argv = argv[1:]
        if len(argv) < 1:
            print_err("insert robot")
            return False
        robot_name = argv[0]
        argv = argv[1:]

        robot_dic = robot_load_from_name(robot_name)
        if robot_dic is False:
            return False

        order_dic = order_dic_from_robot_dir(robot_dic["dir"])
        if order_dic is False or order_dic is None:
            return False

        order_user_old = order_dic.get("order_user", False)
        if order_user_old is False:
            print_err(f"{robot_name} does not have order user")
            return False

    while len(argv) > 0:
        param = argv[0]
        argv = argv[1:]
        key_value = param.split("=", 1)
        if len(key_value) != 2:
            print_err("parameter %s is not key=value" % param)
            return False
        key, value = key_value
        if key in order_user:
            if order_user[key] is False:
                order_user[key] = value
            else:
                if key != "payment_method":
                    print_err(f"{key} can not be set multiple times")
                    return False
                else:
                    order_user[key] += " " + value
        else:
            print_err("%s is not a valid key" % key)
            return False

    for key, value in order_user.items():
        if value is False:
            order_user[key] = order_user_old[key]

    if with_default:
        default_mapping = {
            "public_duration": "default_duration",
            "escrow_duration": "default_escrow",
            "bond_size": "default_bond_size",
        }

        for key, value in default_mapping.items():
            if key not in order_user or order_user[key] is False:
                order_user[key] = str(roboauto_options[value])

    if only_set is False:
        return order_user
    else:
        return {k: v for k, v in order_user.items() if v is not False}


def create_order(argv):
    should_bond = True
    use_node = True
    should_set_active = True
    while len(argv) > 0:
        if argv[0] == "--no-bond":
            should_bond = False
            argv = argv[1:]
        elif argv[0] == "--no-node":
            use_node = False
            argv = argv[1:]
        elif argv[0] == "--no-active":
            should_set_active = False
            argv = argv[1:]
        elif re.match('^-', argv[0]) is not None:
            print_err("option %s not recognized" % argv[0])
            return False
        else:
            break

    if not should_bond and not use_node:
        print_err("--no-bond and --no-node should not both be present")
        return False

    # pylint: disable=R0801 duplicate-code
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name = robot_dic["name"]

    if robot_dic["state"] != "paused":
        print_err("robot %s is not in the paused directory" % robot_name)
        return False

    order_user = order_user_from_argv(argv, with_default=True)
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

    make_order_result = make_order(
        robot_dic,
        order_data,
        should_bond=should_bond,
        use_node=use_node
    )
    if make_order_result is False or make_order_result is None:
        return False

    if use_node:
        print_out(f"{robot_name} order created successfully")

    if should_set_active is True:
        if not robot_change_dir(robot_name, "active"):
            return False

    return True


def cancel_order(argv):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name = robot_dic["name"]

    if robot_dic["state"] != "active":
        print_err("robot %s is not in the active directory" % robot_name)
        return False

    if not robot_cancel_order(robot_dic):
        return False

    if not robot_change_dir(robot_name, "inactive"):
        return False

    print_out("%s moved to inactive" % robot_name)

    return True


def recreate_order(argv):
    should_cancel = True
    use_node = True
    should_bond = True
    while len(argv) >= 1:
        if argv[0] == "--no-bond":
            should_bond = False
            argv = argv[1:]
        if argv[0] == "--no-node":
            use_node = False
            argv = argv[1:]
        elif argv[0] == "--no-cancel":
            should_cancel = False
            argv = argv[1:]
        elif re.match('^-', argv[0]) is not None:
            print_err("option %s not recognized" % argv[0])
            return False
        else:
            break

    if not should_bond and not use_node:
        print_err("--no-bond and --no-node should not both be present")
        return False

    # pylint: disable=R0801 duplicate-code
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]

    if should_cancel:
        if robot_dic["state"] != "active":
            print_err("robot %s is not in the active directory" % robot_name)
            return False
    else:
        if robot_dic["state"] not in ("paused", "inactive"):
            print_err("robot %s is not in the paused or inactive directories" % robot_name)
            return False

    order_user = order_user_from_argv(argv)
    if order_user is False:
        return False

    if should_cancel:
        if not robot_cancel_order(robot_dic):
            return False

    order_dic = order_dic_from_robot_dir(robot_dir, order_id=None)
    if order_dic is False or order_dic is None:
        return False

    order_user_old = order_dic["order_user"]
    for key, value in order_user.items():
        if value is False:
            order_user[key] = order_user_old[key]

    order_data = order_data_from_order_user(order_user)
    if order_data is False:
        return False

    make_order_result = make_order(
        robot_dic,
        order_data,
        should_bond=should_bond,
        use_node=use_node
    )
    if make_order_result is False or make_order_result is None:
        return False

    if use_node:
        print_out(f"{robot_name} order recreated successfully")

    if not robot_change_dir(robot_name, "active", error_is_already=not should_cancel):
        return False

    return True


def order_change_next_expire(argv):
    action = "set"
    if len(argv) > 0:
        first_arg = argv[0]
        if first_arg in ("--print", "--remove"):
            argv = argv[1:]
            action = first_arg.split("-", 2)[2]

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, robot_dir, _, _, _, _ = robot_var_from_dic(robot_dic)

    change_order_file = robot_dir + "/change-next-order"

    if action in ("print", "remove"):
        if not os.path.isfile(change_order_file):
            print_out(f"{robot_name} change order not set")
        else:
            change_order = file_json_read(change_order_file)
            if change_order is False:
                return False
            print_out(json_dumps(change_order))

            if action == "remove":
                if not file_remove(change_order_file):
                    return False
    elif action == "set":
        order_user = order_user_from_argv(argv, only_set=True)
        if order_user is False:
            return False

        something_set = False
        for _, value in order_user.items():
            if value is not False:
                something_set = True
                break
        if something_set is False:
            print_err("nothing set to change")
            return False

        if not file_json_write(change_order_file, order_user):
            return False

        print_out(json_dumps(order_user))

    return True


def order_initial_message(argv):
    action = "set"
    if len(argv) > 0:
        first_arg = argv[0]
        if first_arg in ("--print", "--remove"):
            argv = argv[1:]
            action = first_arg.split("-", 2)[2]

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, robot_dir, _, _, _, _ = robot_var_from_dic(robot_dic)

    if action in ("print", "remove"):
        initial_message = order_read_initial_message_from_file(robot_dir)
        if initial_message is None:
            print_out(f"{robot_name} initial message not set")
        elif initial_message is False:
            return False
        else:
            print_out(json_dumps(initial_message))

            if action == "remove":
                if not order_remove_initial_message_file(robot_dir):
                    return False
    elif action == "set":
        if len(argv) < 1:
            print_err("insert timing")
            return False
        timing_str = argv[0]
        argv = argv[1:]
        timing = get_int(timing_str)
        if timing is False:
            return False

        if len(argv) < 1:
            print_err("insert message")
            return False
        message = argv[0]
        argv = argv[1:]

        initial_message = {
            "timing": timing,
            "message": message
        }

        if not order_write_initial_message_to_file(robot_dir, initial_message):
            return False

        print_out(json_dumps(initial_message))

    return True


def order_nostr_rate_coordinator(argv):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, robot_dir, token, coord_nick, token_base91, robot_url = \
        robot_var_from_dic(robot_dic)
    order_dic = order_dic_from_robot_dir(robot_dir)
    if order_dic is False or order_dic is None:
        return False

    if len(argv) < 1:
        print_err("insert rating")
        return False
    rating = argv[0]
    argv = argv[1:]

    rating_uint = get_uint(rating)
    if rating_uint is False:
        return False
    if rating_uint < 1 or rating_uint > 5:
        print_err("rating should be between 1 and 5")
        return False
    rating_float = 5 / rating_uint

    order_info = order_dic["order_info"]
    order_id = order_info["order_id"]
    order_status = order_info["status"]

    if not order_is_finished(order_status) and not order_is_finished_for_seller(order_status):
        print_err(f"{robot_name} {order_id} is not completed, can not give rating")
        return False

    nostr_pubkey = nostr_pubkey_from_token(token)

    coord = roboauto_get_coordinator(coord_nick)
    if coord is False:
        return False

    coord_pubkey = coord.get("nostr_pubkey")
    coord_short_alias = coord.get("short_alias")
    if not coord_pubkey:
        print_err(
            f"{robot_name} {order_id} {coord_short_alias} " +
            "coordinator does not have nostr_pubkey"
        )
        return False

    coord_token_response = requests_api_review(
        token_base91, robot_url, robot_name, nostr_pubkey
    )
    if response_is_error(coord_token_response):
        print_err(f"{robot_name} {order_id} getting coordinator token")
        return False
    coord_token_response_text = coord_token_response.text
    coord_token_json = json_loads(coord_token_response_text)
    if coord_token_json is False:
        print_err(coord_token_response_text, end="", error=False)
        print_err(f"{robot_name} {order_id} coordinator token response is not json")
        return False
    coord_token = coord_token_json.get("token", False)
    if not coord_token:
        print_err(json_dumps(coord_token_json), error=False)
        print_err(f"{robot_name} {order_id} coord response did not provide token")
        return False

    if not nostr_create_publish_event(
        token, coord_pubkey, coord_token, coord_short_alias,
        order_id, rating_float
    ):
        print_err(f"{robot_name} {order_id} publishing rating on nostr")
        return False

    return True
