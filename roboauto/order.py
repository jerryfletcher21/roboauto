#!/usr/bin/env python3

"""order.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

import os

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_options, roboauto_state
from roboauto.order_data import \
    get_order_string, get_type_string, get_currency_string, \
    order_is_public, order_is_paused, order_is_waiting_maker_bond, \
    order_is_waiting_taker_bond, order_is_expired
from roboauto.order_local import \
    get_order_data, order_dic_from_robot_dir, \
    order_save_order_file, get_order_user, order_id_list_from_robot_dir, \
    order_is_this_hour_and_online, robot_set_make_response, \
    robot_order_set_local_make_data, robot_order_remove_local_make_data
from roboauto.robot import \
    robot_change_dir, robot_var_from_dic, robot_requests_get_order_id, \
    robot_generate, robot_list_dir
from roboauto.requests_api import \
    requests_api_order, requests_api_order_cancel, \
    requests_api_make, response_is_error, requests_api_order_take
from roboauto.utils import \
    json_dumps, string_is_false_none_null, file_is_executable, \
    json_loads, roboauto_get_coordinator_from_url, file_json_write, \
    file_json_read, file_remove, bad_request_is_cancelled
from roboauto.subprocess_commands import subprocess_pay_invoice_and_check


def order_user_empty_get():
    empty_order = get_order_user(
        False, False, False, False, False,
        False, False, False, False
    )

    return empty_order


def amount_correct_format(amount, is_fiat):
    if amount is False or amount is None or string_is_false_none_null(amount):
        return "null"

    if is_fiat is True:
        amount_format = "%.2f"
    else:
        amount_format = "%.8f"

    return amount_format % float(amount)


def peer_nick_from_response(order_response_json):
    if order_response_json.get("is_maker", True) is True:
        peer_nick = order_response_json.get("taker_nick", None)
    else:
        peer_nick = order_response_json.get("maker_nick", None)

    if string_is_false_none_null(peer_nick):
        return None

    return peer_nick


def order_requests_order_dic(
    robot_dic, order_id, order_function=None, take_amount=None,
    save_to_file=True, until_true=True, error_print_not_found_level=0, timeout=None
):
    """get the order_dic making a request to the coordinator
    order_function can be set to requests_api_order_take
    when taking an order
    will return False, or the string of bad_requests so it
    should be checked that the return value is not a string

    the order_dic is composed by 4 dictionaries:
    order_data:  can be derived from order_user, and is the data
                 used when creating orders
    order_urser: data user readable, everything that can be modivied
                 by the user
    order_info:  everything not in order_data and order_user
    order_response_json: the json response from the coordinator"""

    robot_name, _, robot_dir, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    if order_id is False or order_id is None:
        order_id = robot_requests_get_order_id(robot_dic)
        if order_id is False or order_id is None:
            return False

    requests_options = {
        "until_true": until_true,
        "error_print": error_print_not_found_level
    }
    if timeout is not None and timeout is not False:
        requests_options.update({
            "timeout": timeout
        })
    if order_function is None:
        order_response_all = requests_api_order(
            token_base91, order_id, robot_url, robot_name,
            options=requests_options
        )
    else:
        order_response_all = order_function(
            token_base91, order_id, robot_url, robot_name, take_amount=take_amount,
            options=requests_options
        )

    if response_is_error(order_response_all):
        print_err(f"{robot_name} {order_id} not found", level=error_print_not_found_level)
        return False
    order_response = order_response_all.text
    order_response_json = json_loads(order_response)
    if order_response_json is False:
        print_err(order_response, end="", error=False, date=False)
        print_err("getting order info for " + robot_name + " " + order_id)
        return False

    bad_request = order_response_json.get("bad_request", False)
    if bad_request is not False:
        print_err(bad_request, error=False, date=False)
        if not isinstance(bad_request, str):
            print_err("bad_request is not a string")
            print_err(f"{robot_name} {order_id} not available")
            return False
        else:
            if not bad_request_is_cancelled(bad_request):
                print_err(f"{robot_name} {order_id} not available")
            return bad_request

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
    public_duration = order_response_json.get(
        "public_duration", roboauto_options["default_duration"]
    )
    escrow_duration = order_response_json.get(
        "escrow_duration", roboauto_options["default_escrow"]
    )
    bond_size = order_response_json.get(
        "bond_size", str(roboauto_options["default_bond_size"])
    )
    is_taken = order_response_json.get("taker", None) is not None and \
        not order_is_waiting_taker_bond(status_id)

    peer_nick = peer_nick_from_response(order_response_json)

    status_string = get_order_string(status_id)

    type_string = str(get_type_string(type_id))

    currency_string = str(get_currency_string(currency_id)).lower()
    is_fiat = currency_string != "btc"

    amount_single = None
    if is_taken or not has_range:
        amount_single = amount_correct_format(amount, is_fiat)
        if not amount_single:
            print_err(order_response, end="", error=False, date=False)
            print_err("format amount: " + amount)
            return False
    if not has_range:
        min_amount_user = amount
        max_amount_user = amount
        amount_string = amount_single
    else:
        min_amount_user = min_amount
        max_amount_user = max_amount
        min_amount_string = amount_correct_format(min_amount, is_fiat)
        max_amount_string = amount_correct_format(max_amount, is_fiat)
        if not min_amount_string or not max_amount_string:
            print_err(order_response, end="", error=False, date=False)
            print_err("format amount: " + min_amount + " " + max_amount)
            return False
        if is_taken:
            amount_string = amount_single
        else:
            amount_string = min_amount_string + "-" + max_amount_string

    order_description = \
        type_string + " " + currency_string + " " + str(amount_string) + " " + \
        premium + " " + payment_method + " " + status_string

    order_dic = {
        "order_data": get_order_data(
            type_id, currency_id,
            amount, has_range, min_amount, max_amount,
            payment_method, premium,
            public_duration, escrow_duration, bond_size
        ),
        "order_user": get_order_user(
            type_string, currency_string, min_amount_user, max_amount_user,
            payment_method, premium, str(public_duration), str(escrow_duration),
            bond_size
        ),
        "order_info": {
            "coordinator":          coordinator,
            "order_id":             order_id,
            "status":               status_id,
            "status_string":        status_string,
            "amount_string":        amount_string,
            "order_description":    order_description,
            "is_taken":             is_taken,
            "peer_nick":            peer_nick,
            "amount_single":        amount_single
        },
        "order_response_json":      order_response_json
    }

    if save_to_file is True:
        if not order_save_order_file(robot_dir, order_id, order_dic):
            return False

    return order_dic


# As a maker if you cancel an order after you have locked your maker bond,
# you are returned your bond.
def robot_cancel_order(robot_dic):
    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    if robot_dic["state"] != "active":
        print_err("robot %s is not in the active directory" % robot_name)
        return False

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or isinstance(order_dic, str):
        return False

    order_info = order_dic["order_info"]

    order_id = order_info["order_id"]
    status_id = order_info["status"]

    if \
        not order_is_public(status_id) and \
        not order_is_paused(status_id) and \
        not order_is_waiting_maker_bond(status_id):
        print_err("robot order %s %s is not public or paused" % (robot_name, order_id))
        return False

    print_out("robot %s cancel order %s" % (robot_name, order_id))

    order_cancel_response_all = requests_api_order_cancel(
        token_base91, order_id, robot_url, robot_name, status_id
    )
    if response_is_error(order_cancel_response_all):
        return False
    order_cancel_response = order_cancel_response_all.text
    order_cancel_response_json = json_loads(order_cancel_response)
    if order_cancel_response_json is False:
        print_err(order_cancel_response, end="", error=False, date=False)
        print_err("cancelling order %s %s" % (robot_name, token_base91))
        return False

    bad_request = order_cancel_response_json.get("bad_request", False)
    if bad_request is False:
        print_err(order_cancel_response, end="", error=False, date=False)
        print_err("getting cancel response %s %s" % (robot_name, order_id))
        return False

    print_out(bad_request, date=False)

    return True


def amount_correct_from_response(order_response_json):
    amount_correct = order_response_json.get("amount", False)
    if amount_correct is False or amount_correct is None:
        return False

    is_fiat = str(get_currency_string(
        order_response_json.get("currency", "fiat")
    )).lower() != "btc"

    return amount_correct_format(amount_correct, is_fiat)


def premium_string_get(premium):
    if premium[0] == "-":
        return "below-" + premium[1:]
    else:
        return "above-" + premium


def order_string_status_print(robot_name, order_id, order_description, peer_nick):
    if peer_nick is False or peer_nick is None:
        print_out(f"{robot_name} {order_id} {order_description}")
    else:
        print_out(f"{robot_name} {peer_nick} {order_id} {order_description}")


def bond_order(robot_dic, order_id, taker=False, take_amount=None, use_node=True):
    """bond an order, after checking the invoice with lightning-node check
    will run lightning-node check and lightning-node pay as subprocesses
    if use_node is True it will simply print out the invoice"""

    robot_name = robot_dic["name"]

    if taker is False:
        order_function = None
    else:
        order_function = requests_api_order_take

    order_dic = order_requests_order_dic(
        robot_dic, order_id, order_function=order_function, take_amount=take_amount
    )
    if order_dic is False or isinstance(order_dic, str):
        return False

    # pylint: disable=R0801 duplicate-code
    order_user = order_dic["order_user"]
    order_info = order_dic["order_info"]
    order_response_json = order_dic["order_response_json"]

    order_description = order_info["order_description"]
    if taker is False:
        checking_function = order_is_waiting_maker_bond
        failure_function = order_is_expired
        if not checking_function(order_info["status"]):
            print_err(f"{robot_name} {order_id} is not waiting maker bond")
            return False
        string_paid = "bonded successfully, order is public"
        string_not_paid = "bond expired, order is not public"

        order_string_status_print(robot_name, order_id, order_description, None)

        name_pay_label = robot_name
    else:
        checking_function = order_is_waiting_taker_bond
        failure_function = order_is_public
        if not checking_function(order_info["status"]):
            print_err(f"order {order_id} is not waiting taker bond")
            return False
        string_paid = "bonded successfully, order is taken"
        string_not_paid = "bond expired, order is not taken"

        peer_nick = peer_nick_from_response(order_response_json)

        order_string_status_print(robot_name, order_id, order_description, peer_nick)

        name_pay_label = robot_name + "-" + str(peer_nick)

    bond_satoshis = order_response_json.get("bond_satoshis", False)
    if bond_satoshis is False:
        print_err(
            f"{robot_name} {order_id} bond_satoshis not present, invoice can not be checked"
        )
        return False

    bond_invoice = order_response_json.get("bond_invoice", False)
    if bond_invoice is False:
        print_err(
            f"{robot_name} {order_id} bond_invoice not present, invoice can not be checked"
        )
        return False

    if not use_node:
        print_out(bond_invoice)
        return True

    if not file_is_executable(roboauto_state["lightning_node_command"]):
        print_err("lightning node not set, to use without node pass --no-node")
        return False

    pay_label = \
        "bond-" + name_pay_label + "-" + order_id + "-" + \
        order_user["type"] + "-" + order_user["currency"] + "-" + \
        order_info["amount_string"] + "-" + premium_string_get(order_user["premium"])
    return subprocess_pay_invoice_and_check(
        robot_dic, order_id,
        bond_invoice, str(bond_satoshis), pay_label,
        lambda order_status : not checking_function(order_status),
        "checking if order is bonded...",
        string_paid, string_not_paid,
        order_requests_order_dic, failure_function
    )


def make_order(
    robot_dic, make_data, should_bond=True, check_change=False, use_node=True
):
    """make the request to the coordinator to create an order.
    if should_bond is true, also bond it, if it is false do not create
    the order if there are more than maximum order this hour, save
    make data to file instead
    if check_change is true, change the order from data saved on disk
    return False if an error None if the requests was not made"""

    robot_name, robot_state, robot_dir, _, coordinator, token_base91, robot_url = \
        robot_var_from_dic(robot_dic)

    change_order_file = robot_dir + "/change-next-order"

    if check_change is True:
        if os.path.isfile(change_order_file):
            change_order = file_json_read(change_order_file)
            if change_order is not False:
                for key, value in change_order.items():
                    if value is not False:
                        old_value = make_data[key]
                        make_data[key] = value
                        print_out(
                            f"{robot_name} {key} "
                            f"changed from {old_value} to {value}"
                        )

    if roboauto_options["robot_maximum_orders"] > 0:
        max_orders = roboauto_options["robot_maximum_orders"]
        order_ids = order_id_list_from_robot_dir(robot_dir, error_print=False)
        if \
            order_ids is not False and order_ids is not None and \
            len(order_ids) >= max_orders:
            print_out(
                f"{robot_name} {coordinator} maximum orders {max_orders} reached"
            )
            if roboauto_options["create_new_after_maximum_orders"] is True:
                new_robot_dic = robot_generate(coordinator, robot_state)
                if new_robot_dic is False:
                    return False
                new_robot_name = new_robot_dic["name"]
                new_robot_dir = new_robot_dic["dir"]

                print_out(f"{new_robot_name} created with order data of {robot_name}")

                initial_message = order_read_initial_message_from_file(robot_dir)
                if initial_message is False:
                    print_err(
                        f"{robot_name} reading initial message, " +
                        f"not copied to {new_robot_name}"
                    )
                elif initial_message is not None:
                    if order_write_initial_message_to_file(new_robot_dir, initial_message):
                        print_out(f"{robot_name} copied initial message to {new_robot_name}")
                    else:
                        print_err(f"{robot_name} copying initial message to {new_robot_name}")

                if robot_order_set_local_make_data(new_robot_dir, make_data) is False:
                    return False

                print_out(f"{robot_name} moving to inactive")
                if not robot_change_dir(robot_name, "inactive"):
                    print_err(f"{robot_name} moving to inactive")
                    return False

                return make_order(
                    new_robot_dic, make_data,
                    should_bond=should_bond,
                    check_change=check_change,
                    use_node=use_node
                )
            else:
                print_out(f"{robot_name} moving to inactive")
                if not robot_change_dir(robot_name, "inactive"):
                    print_err(f"{robot_name} moving to inactive")
                    return False

                return None

    if should_bond is False:
        robot_this_hour = 0

        active_list = robot_list_dir(roboauto_state["active_home"])
        for robot_active in active_list:
            # pylint: disable=R0801 duplicate-code
            order_dic = order_dic_from_robot_dir(
                roboauto_state["active_home"] + "/" + robot_active,
                order_id=None, error_print=False
            )
            if order_dic is False or order_dic is None:
                continue

            if order_is_this_hour_and_online(order_dic):
                robot_this_hour += 1

        order_maximum = roboauto_options["order_maximum"]
        if robot_this_hour >= order_maximum:
            print_out(
                f"{robot_name} there are already {order_maximum} orders this hour, " +
                "saving make data to file without creating order"
            )
            return robot_order_set_local_make_data(robot_dir, make_data)

    if not make_data["bond_size"]:
        print_err("bond size percentage not defined")
        return False

    make_response_all = requests_api_make(
        token_base91, robot_url, robot_name, make_data=json_dumps(make_data)
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
            print_err(bad_request, error=False, date=False)
            if "Your order maximum amount is too big" in bad_request:
                print_out(f"{robot_name} maximum amount too big, moving to paused")
                if not robot_change_dir(robot_name, "paused", error_is_already=False):
                    return False
            elif "Current limit is 0 orders" in bad_request:
                print_out(f"{robot_name} {coordinator} paused orders, moving to paused")
                if not robot_change_dir(robot_name, "paused", error_is_already=False):
                    return False
            else:
                print_err("making order")
        else:
            print_err(make_response, end="", error=False, date=False)
            print_err(make_data, error=False, date=False)
            print_err("getting id of new order for " + robot_name)
        return False

    if not robot_set_make_response(robot_dir, make_response_json):
        return False
    if not robot_order_remove_local_make_data(robot_dir):
        return False

    order_id = str(order_id_number)

    if check_change is True:
        if os.path.isfile(change_order_file):
            file_remove(change_order_file)

    if not should_bond:
        print_out(f"{robot_name} order {order_id} will not be bonded")
        return True

    return bond_order(robot_dic, order_id, use_node=use_node)


def order_initial_message_file_get(robot_dir):
    return robot_dir + "/initial-message"


def order_read_initial_message_from_file(robot_dir):
    initial_message_file = order_initial_message_file_get(robot_dir)

    if not os.path.isfile(initial_message_file):
        return None

    initial_message = file_json_read(initial_message_file)
    return initial_message


def order_write_initial_message_to_file(robot_dir, initial_message):
    initial_message_file = order_initial_message_file_get(robot_dir)

    if not file_json_write(initial_message_file, initial_message):
        return False

    return True


def order_remove_initial_message_file(robot_dir):
    initial_message_file = order_initial_message_file_get(robot_dir)

    if not file_remove(initial_message_file):
        return False

    return True
