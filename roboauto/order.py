#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
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
import subprocess
import signal

import filelock

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.order_local import \
    get_order_string, get_type_string, get_currency_string, \
    order_is_public, order_is_paused, order_is_waiting_maker_bond, \
    order_is_expired, order_data_from_order_user, \
    get_order_data, order_get_order_dic, order_save_order_file
from roboauto.robot import \
    robot_get_lock_file, robot_input_from_argv, \
    waiting_queue_get, robot_requests_robot, robot_change_dir
from roboauto.requests_api import \
    requests_api_order, requests_api_cancel, \
    requests_api_make, response_is_error
from roboauto.utils import \
    json_dumps, file_is_executable, subprocess_run_command, \
    json_loads, file_json_write, \
    input_ask, roboauto_get_coordinator_url, \
    roboauto_get_coordinator_from_url, token_get_base91


def order_user_get(with_default):
    empty_order = {
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

    if with_default:
        empty_order["public_duration"] = roboauto_options["default_duration"]
        empty_order["escrow_duration"] = roboauto_options["default_escrow"]
        empty_order["bond_size"] = roboauto_options["default_bond_size"]

    return empty_order


def api_order_get_dic(robot_name, token_base91, robot_url, order_id):
    """get the order_dic making a request to the coordinator
    the order_dic is composed by 4 dictionaries:
    order_data:  can be derived from order_user, and is the data
                 used when creating orders
    order_urser: data user readable, everything that can be modivied
                 by the user
    order_info:  everything not in order_data and order_user
    order_response_json: the json response from the coordinator"""

    order_response_all = requests_api_order(token_base91, order_id, robot_url)
    # error 500 when the old order is purged from the server
    # maybe create last order from local if available
    if order_response_all.status_code in (400, 500):
        return None
    if response_is_error(order_response_all):
        return False
    order_response = order_response_all.text
    order_response_json = json_loads(order_response)
    if order_response_json is False:
        print_err(order_response, end="", error=False, date=False)
        print_err("getting order info for " + robot_name + " " + order_id)
        return False

    coordinator = roboauto_get_coordinator_from_url(robot_url)

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
        "order_data": get_order_data(
            type_id, currency_id,
            amount, has_range, min_amount, max_amount,
            payment_method, premium,
            public_duration, escrow_duration, bond_size
        ),
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
            "coordinator":          coordinator,
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


def api_order_get_dic_handle(robot_name, token_base91, robot_url, order_id):
    """api_order_get_dic can return None or False, this function is
    used when it does not matter whether None or False is returned"""
    order_dic = api_order_get_dic(robot_name, token_base91, robot_url, order_id)
    if order_dic is False:
        return False
    if order_dic is None:
        print_err("%s order %s not available" % (robot_name, str(order_id)))
        return False

    return order_dic


def robot_cancel_order(robot_dic):
    robot_name = robot_dic["name"]
    token_base91 = token_get_base91(robot_dic["token"])
    robot_dir = robot_dic["dir"]
    robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])

    if robot_dic["state"] != "active":
        print_err("robot %s is not in the active directory" % robot_name)
        return False

    try:
        with filelock.SoftFileLock(
            robot_get_lock_file(robot_name), timeout=roboauto_state["filelock_timeout"]
        ):
            robot_response, robot_response_json = robot_requests_robot(
                token_base91, robot_url, robot_dic
            )
            if robot_response is False:
                return False

            order_id_num = robot_response_json.get("active_order_id", False)
            if order_id_num is False:
                print_err(robot_response, error=False, date=False)
                print_err("getting active order_id for " + robot_name)
                return False

            order_id = str(order_id_num)

            order_dic = api_order_get_dic(robot_name, token_base91, robot_url, order_id)
            if order_dic is False:
                print_err("order data is false %s %s" % (robot_name, order_id))
                return False
            elif order_dic is None:
                print_err("%s last order not available" % robot_name)
                return False

            if not order_save_order_file(robot_dir, order_id, order_dic):
                return False

            status_id = order_dic["order_info"]["status"]

            if \
                not order_is_public(status_id) and \
                not order_is_paused(status_id) and \
                not order_is_waiting_maker_bond(status_id):
                print_err("robot order %s %s is not public or paused" % (robot_name, order_id))
                return False

            print_out("robot %s cancel order %s" % (robot_name, order_id))

            order_post_response_all = requests_api_cancel(token_base91, order_id, robot_url)
            if response_is_error(order_post_response_all):
                return False
            order_post_response = order_post_response_all.text
            order_post_response_json = json_loads(order_post_response)
            if order_post_response_json is False:
                print_err(order_post_response, end="", error=False, date=False)
                print_err("cancelling order %s %s" % (robot_name, token_base91))
                return False

            bad_requets = order_post_response_json.get("bad_request", False)
            if bad_requets is False:
                print_err(order_post_response, end="", error=False, date=False)
                print_err("getting cancel response %s %s" % (robot_name, order_id))
                return False

            print_out(bad_requets)
    except filelock.Timeout:
        print_err("filelock timeout %d" % roboauto_state["filelock_timeout"])
        return False

    return True


def bond_order(robot_dic, order_id, bond_amount):
    """bond an order, if bond amount is not False, also check invoice
    will run the pay_command as a subprocess"""

    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]
    token_base91 = token_get_base91(robot_dic["token"])
    robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])

    order_dic = api_order_get_dic_handle(robot_name, token_base91, robot_url, order_id)
    if order_dic is False:
        return False

    if not order_save_order_file(robot_dir, order_id, order_dic):
        return False

    order_user = order_dic["order_user"]
    order_info = order_dic["order_info"]

    if not order_is_waiting_maker_bond(order_info["status"]):
        print_err(robot_name + " " + order_id + " is not expired")
        return False

    print_out(robot_name + " " + order_id + " " + order_info["order_description"])

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
        print_out("%s %s invoice will not be checked" % (robot_name, order_id))

    if not file_is_executable(roboauto_state["pay_command"]):
        print_err(roboauto_state["pay_command"] + " is not an executable script")
        return False

    pay_subprocess_command = [
        roboauto_state["pay_command"], order_info["invoice"], robot_name, order_id,
        order_user["type"], order_user["currency"],
        order_info["amount_string"]
    ]
    try:
        with subprocess.Popen(pay_subprocess_command, start_new_session=True) as pay_subprocess:
            while True:
                print_out("checking if order is bonded...")

                order_dic = api_order_get_dic_handle(
                    robot_name, token_base91, robot_url, order_id
                )
                if order_dic is False:
                    return False

                if not order_save_order_file(robot_dir, order_id, order_dic):
                    return False

                order_response_json = order_dic["order_response_json"]

                order_status = order_response_json.get("status", False)
                if order_status is False:
                    print_err(json_dumps(order_response_json), error=False, date=False)
                    print_err("getting order_status of " + robot_name + " " + order_id)
                    return False

                if not order_is_waiting_maker_bond(order_status):
                    if not order_is_expired(order_status):
                        print_out("bonded successfully, order is public for " + robot_name)
                        return_status = True
                    else:
                        print_err("bond expired, will retry next loop for " + robot_name)
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


def make_order(
    robot_dic, order_id, make_data, satoshis_now, should_bond=True
):
    """make the request to the coordinator to create an order,
    and if should_bond is true, also bond it"""

    robot_name = robot_dic["name"]
    token_base91 = token_get_base91(robot_dic["token"])
    robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])

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

    make_response_all = requests_api_make(
        token_base91, order_id, robot_url, make_data=json_dumps(make_data)
    )
    if response_is_error(make_response_all):
        return False
    make_response = make_response_all.text
    make_response_json = json_loads(make_response)
    if make_response_json is False:
        print_err(make_data, error=False, date=False)
        print_err("getting response make order for " + robot_name)
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
            print_err("getting id of new order for " + robot_name)
        return False

    order_id = str(order_id_number)

    if not should_bond:
        print_out(f"order {order_id} will not be bonded")
        return True

    return bond_order(robot_dic, order_id, bond_amount)


def order_user_from_argv(argv, with_default=False):
    """get order_user's fields from argv"""
    order_user = order_user_get(with_default)

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
    should_bond = True
    if len(argv) >= 1:
        if argv[0] == "--no-bond":
            should_bond = False
            argv = argv[1:]
        elif re.match('^-', argv[0]) is not None:
            print_err("option %s not recognized" % argv[0])
            return False
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

    if make_order(
        robot_dic,
        False, order_data, False,
        should_bond=should_bond
    ) is False:
        return False

    print_out(f"{robot_name} order created successfully")

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
    should_bond = True
    if len(argv) >= 1:
        if argv[0] == "--no-cancel":
            should_cancel = False
            argv = argv[1:]
        elif argv[0] == "--no-bond":
            should_bond = False
            argv = argv[1:]
        elif re.match('^-', argv[0]) is not None:
            print_err("option %s not recognized" % argv[0])
            return False
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

    if len(argv) > 0:
        order_user_changed = True
    else:
        order_user_changed = False

    order_user = order_user_from_argv(argv)
    if order_user is False:
        return False

    if should_cancel:
        if not robot_cancel_order(robot_dic):
            return False

    order_dic = order_get_order_dic(robot_dir)
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
        robot_dic,
        order_id, order_data, satoshis_now,
        should_bond=should_bond
    ):
        return False

    if should_cancel is False:
        if not robot_change_dir(robot_name, "active"):
            return False

    return True


def wait_order(robot_dic):
    """move robot to waiting queue"""
    nicks_waiting = waiting_queue_get()
    if nicks_waiting is False:
        return False

    robot_name = robot_dic["name"]

    nicks_waiting.append(robot_name)
    print_out(robot_name + " added to waiting queue")
    if file_json_write(roboauto_state["waiting_queue_file"], nicks_waiting) is False:
        print_err("writing waiting queue")
        return False

    return False
