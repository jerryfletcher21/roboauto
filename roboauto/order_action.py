#!/usr/bin/env python3

"""order_action.py"""

# pylint: disable=C0116 missing-function-docstring

import os
import re

from roboauto.global_state import roboauto_options, roboauto_state
from roboauto.utils import \
    print_out, print_err, get_uint, json_loads, json_dumps, \
    input_ask, file_write, file_read, \
    invoice_get_correct_amount, is_float, file_is_executable
from roboauto.robot import \
    robot_get_current_fingerprint, robot_var_from_dic, \
    robot_input_from_argv, robot_change_dir
from roboauto.order_data import \
    order_is_waiting_seller_buyer, order_is_waiting_buyer, \
    order_is_waiting_seller, order_is_waiting_fiat_sent, \
    order_is_fiat_sent, order_is_public, order_is_paused, \
    order_is_sucessful, order_is_expired, get_order_string, \
    order_is_in_dispute, order_is_failed_routing, \
    order_is_sending_to_buyer
from roboauto.order import \
    order_requests_order_dic, peer_nick_from_response, bond_order, \
    amount_correct_from_response, premium_string_get, \
    order_string_status_print
from roboauto.requests_api import \
    requests_api_order_invoice, requests_api_order_pause, \
    requests_api_order_confirm, requests_api_order_undo_confirm, \
    requests_api_order_dispute, response_is_error, \
    requests_api_order_cancel, requests_api_order_rate, \
    requests_api_order_address, requests_api_order_submit_statement
from roboauto.gpg_key import gpg_sign_message
from roboauto.subprocess_commands import \
    subprocess_generate_invoice, \
    subprocess_pay_invoice_and_check
from roboauto.chat import robot_requests_chat


def order_take_argv(argv):
    if len(argv) < 1:
        print_err("insert options")
        return False

    fully = False
    use_node = True
    while len(argv) >= 1:
        if argv[0] == "--fully":
            argv = argv[1:]
            fully = True
        elif argv[0] == "--no-node":
            argv = argv[1:]
            use_node = False
        else:
            break

    if fully and not use_node:
        print_err("--fully and --no-node should not both be present")
        return False

    if not file_is_executable(roboauto_state["lightning_node_command"]) and fully is True:
        print_err("lightning node is not set --fully can not be used")
        return False

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    if len(argv) >= 1:
        order_id = argv[0]
        argv = argv[1:]
    else:
        order_id = input_ask("insert order id: ")
        if order_id is False:
            return False
    if get_uint(order_id) is False:
        return False

    if len(argv) >= 1:
        take_amount = argv[0]
        argv = argv[1:]
        if get_uint(take_amount) is False:
            return False
    else:
        take_amount = None

    order_dic = bond_order(
        robot_dic, order_id, taker=True,
        take_amount=take_amount,
        use_node=use_node
    )
    if order_dic is False:
        return False

    if use_node is False:
        return True

    robot_name = robot_dic["name"]

    print_out(f"{robot_name} {order_id} taken successfully")

    if fully is True:
        if isinstance(order_dic, dict):
            if order_dic["order_response_json"].get("is_seller", False) is True:
                if order_seller_bond_escrow(robot_dic, True) is False:
                    return False
            else:
                if order_buyer_update_invoice(robot_dic, None) is False:
                    return False

    if not robot_change_dir(robot_name, "pending"):
        return False

    return True


def order_buyer_update_data(
    robot_dic, data_string, data_var, extra_value
):
    robot_name, _, robot_dir, token, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or isinstance(order_dic, str):
        return False

    order_user = order_dic["order_user"]
    order_info = order_dic["order_info"]
    order_response_json = order_dic["order_response_json"]

    order_id = order_info["order_id"]
    status_id = order_info["status"]

    is_buyer = order_response_json.get("is_buyer", False)
    if is_buyer is False:
        print_err(f"{robot_name} {order_id} is not buyer")
        return False

    if \
        not order_is_waiting_seller_buyer(status_id) and \
        not order_is_waiting_buyer(status_id):
        if data_string == "invoice":
            if not order_is_failed_routing(status_id):
                print_err(
                    f"{robot_name} {order_id} is not "
                    "waiting for buyer or failed routing"
                )
                return False
        else:
            print_err(f"{robot_name} {order_id} is not waiting for buyer")
            return False

    order_description = order_info["order_description"]

    peer_nick = peer_nick_from_response(order_response_json)

    order_string_status_print(robot_name, order_id, order_description, peer_nick)

    if data_string == "invoice":
        invoice = data_var
        budget_ppm = extra_value

        if invoice is None or invoice is False:
            if not order_is_failed_routing(status_id):
                invoice_amount = order_response_json.get("invoice_amount", False)
                if invoice_amount is False:
                    print_err("invoice amount is not present")
                    return False
            else:
                invoice_amount = order_response_json.get("trade_satoshis", False)
                if invoice_amount is False:
                    print_err("trade satoshis is not present")
                    return False

            correct_invoice_amount = invoice_get_correct_amount(invoice_amount, budget_ppm)

            amount_correct = amount_correct_from_response(order_response_json)
            if amount_correct is False:
                amount_correct = order_info["amount_string"]

            invoice = subprocess_generate_invoice(
                str(correct_invoice_amount),
                robot_name + "-" + str(peer_nick) + "-" + order_id + "-" +
                order_user["type"] + "-" + order_user["currency"] + "-" +
                amount_correct + "-" + premium_string_get(order_user["premium"])
            )
            if invoice is False:
                return False

        message = invoice
        requests_api_order_function = requests_api_order_invoice
    elif data_string == "address":
        address = data_var
        message = address
        requests_api_order_function = requests_api_order_address
    else:
        print_err(f"wrong order buyer update data {data_string}")
        return False

    fingerprint = robot_get_current_fingerprint(robot_dir)
    if fingerprint is False:
        return False

    signed_message = gpg_sign_message(message, fingerprint, passphrase=token)
    if signed_message is False:
        print_err(f"signing {data_string}")
        return False

    order_data_response_all = requests_api_order_function(
        token_base91, order_id, robot_url, robot_name, signed_message, extra_value
    )
    if response_is_error(order_data_response_all):
        return False
    order_data_response = order_data_response_all.text
    order_data_response_json = json_loads(order_data_response)
    if order_data_response_json is False:
        print_err(order_data_response, end="", error=False, date=False)
        print_err(f"{robot_name} {order_id} sending {data_string}")
        return False

    bad_request = order_data_response_json.get("bad_request", False)
    if bad_request is not False:
        print_err(bad_request, date=False, error=False)
        return False

    new_status_id = order_data_response_json.get("status", False)
    if new_status_id is False:
        print_err(json_dumps(order_data_response_json), date=False, error=False)
        print_err(f"{data_string} not sent, no new status")
        return False

    if \
        not order_is_waiting_seller(new_status_id) and \
        not order_is_waiting_fiat_sent(new_status_id) and \
        not order_is_sending_to_buyer(new_status_id):
        print_err(json_dumps(order_data_response_json), date=False, error=False)
        print_err(
            f"{data_string} not send, current status: " +
            str(get_order_string(new_status_id))
        )
        return False

    print_out(f"{robot_name} {order_id} {data_string} sent successfully")

    return True


def order_buyer_update_invoice(robot_dic, extra_arg):
    budget_ppm, invoice = extra_arg
    if budget_ppm is None or budget_ppm is False:
        budget_ppm = roboauto_options["routing_budget_ppm"]

    return order_buyer_update_data(
        robot_dic, "invoice", invoice, budget_ppm
    )


def order_buyer_update_address(robot_dic, extra_arg):
    address, sat_per_vb = extra_arg

    return order_buyer_update_data(
        robot_dic, "address", address, sat_per_vb
    )


def order_seller_bond_escrow(robot_dic, extra_arg):
    robot_name = robot_dic["name"]

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or isinstance(order_dic, str):
        return False

    # pylint: disable=R0801 duplicate-code
    order_user = order_dic["order_user"]
    order_info = order_dic["order_info"]
    order_response_json = order_dic["order_response_json"]

    order_id = order_info["order_id"]
    status_id = order_info["status"]

    is_seller = order_response_json.get("is_seller", False)
    if is_seller is False:
        print_err(f"{robot_name} {order_id} is not seller")
        return False

    if \
        not order_is_waiting_seller_buyer(status_id) and \
        not order_is_waiting_seller(status_id):
        print_err(f"{robot_name} {order_id} is not waiting for seller")
        return False

    order_description = order_info["order_description"]

    peer_nick = peer_nick_from_response(order_response_json)

    order_string_status_print(robot_name, order_id, order_description, peer_nick)

    amount_correct = amount_correct_from_response(order_response_json)
    if amount_correct is False:
        amount_correct = order_info["amount_string"]

    escrow_satoshis = order_response_json.get("escrow_satoshis", False)
    if escrow_satoshis is False:
        print_err(
            f"{robot_name} {order_id} escrow_satoshis not present, invoice can not be checked"
        )
        return False

    escrow_invoice = order_response_json.get("escrow_invoice", False)
    if escrow_invoice is False:
        print_err(
            f"{robot_name} {order_id} escrow_invoice not present, invoice can not be checked"
        )
        return False

    use_node = extra_arg
    if not use_node:
        print_out(escrow_invoice)
        return True

    if not file_is_executable(roboauto_state["lightning_node_command"]):
        print_err("lightning node not set, to use without node pass --no-node")
        return False

    pay_label = \
        robot_name + "-" + str(peer_nick) + "-" + order_id + "-" + \
        order_user["type"] + "-" + order_user["currency"] + "-" + \
        amount_correct + "-" + premium_string_get(order_user["premium"])
    if subprocess_pay_invoice_and_check(
        robot_dic, order_id,
        escrow_invoice, str(escrow_satoshis), pay_label,
        lambda order_status : \
            not order_is_waiting_seller_buyer(order_status) and \
            not order_is_waiting_seller(order_status),
        "checking if escrow is paid...",
        "escrow paid successfully",
        "escrow not paid in time",
        order_requests_order_dic, order_is_expired,
        maximum_retries=100
    ) is False:
        return False

    return True


def order_post_action_simple(
    robot_dic, order_post_function, is_wrong_status,
    string_error, string_or_bad_request,
    extra_arg=None,
    should_be_buyer=False, should_be_seller=False
):
    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or isinstance(order_dic, str):
        return False

    order_info = order_dic["order_info"]
    order_response_json = order_dic["order_response_json"]

    status_id = order_info["status"]
    order_id = order_info["order_id"]

    if should_be_buyer and order_response_json.get("is_seller", False):
        print_err(f"{robot_name} {order_id} is not buyer")
        return False

    if should_be_seller and order_response_json.get("is_buyer", False):
        print_err(f"{robot_name} {order_id} is not seller")
        return False

    if is_wrong_status(status_id):
        print_err(f"{robot_name} {order_id} " + string_error)
        return False

    order_description = order_info["order_description"]

    peer_nick = peer_nick_from_response(order_response_json)

    order_string_status_print(robot_name, order_id, order_description, peer_nick)

    if extra_arg is False or extra_arg is None:
        order_post_response_all = order_post_function(
            token_base91, order_id, robot_url, robot_name
        )
    else:
        order_post_response_all = order_post_function(
            token_base91, order_id, robot_url, extra_arg
        )
    if response_is_error(order_post_response_all):
        return False
    order_post_response = order_post_response_all.text
    order_post_response_json = json_loads(order_post_response)
    if order_post_response_json is False:
        print_err(order_post_response, error=False, date=False)
        print_err(f"{robot_name} {order_id} response is not json")
        return False

    # strange reseponse for order post cancel
    # bad_request is set when success
    # see https://github.com/RoboSats/robosats/issues/1245
    bad_request = order_post_response_json.get("bad_request", False)
    if string_or_bad_request is False:
        if bad_request is False:
            print_err(order_post_response, error=False, date=False)
            print_err(f"{robot_name} {order_id} problems in the response")
            return False

        print_out(bad_request, date=False)
    else:
        if bad_request is not False:
            print_err(bad_request, error=False, date=False)
            print_err(f"{robot_name} {order_id} problems in the response")
            return False

        print_out(f"{robot_name} {order_id} " + string_or_bad_request)

    return True


def order_pause_toggle(robot_dic):
    return order_post_action_simple(
        robot_dic,
        requests_api_order_pause,
        lambda status_id : \
            not order_is_public(status_id) and \
            not order_is_paused(status_id),
        "is not public or paused",
        "toggled pause"
    )


def order_collaborative_cancel(robot_dic):
    return order_post_action_simple(
        robot_dic,
        requests_api_order_cancel,
        lambda status_id : \
            not order_is_waiting_buyer(status_id) and \
            not order_is_waiting_fiat_sent(status_id),
        "can not send collaborative cancel",
        False
    )


def order_send_confirm(robot_dic):
    return order_post_action_simple(
        robot_dic,
        requests_api_order_confirm,
        lambda status_id : \
            not order_is_waiting_fiat_sent(status_id) and \
            not order_is_fiat_sent(status_id),
        "can not confirm payment",
        "confirmation sent"
    )


def order_undo_confirm(robot_dic):
    return order_post_action_simple(
        robot_dic,
        requests_api_order_undo_confirm,
        lambda status_id : \
            not order_is_fiat_sent(status_id),
        "can not undo confirm payment",
        "confirmation undone",
        should_be_buyer=True
    )


def order_start_dispute(robot_dic):
    return order_post_action_simple(
        robot_dic,
        requests_api_order_dispute,
        lambda status_id : \
            not order_is_waiting_fiat_sent(status_id) and \
            not order_is_fiat_sent(status_id),
        "can not start dispute",
        "dispute started"
    )


def order_submit_statement(robot_dic, extra_arg):
    statement = extra_arg

    return order_post_action_simple(
        robot_dic,
        requests_api_order_submit_statement,
        lambda status_id : \
            not order_is_in_dispute(status_id),
        "can not send dispute statement",
        "dispute statement submitted",
        extra_arg=statement
    )


def order_rate_coordinator(robot_dic, extra_arg):
    rating = extra_arg

    if order_post_action_simple(
        robot_dic,
        requests_api_order_rate,
        lambda status_id : \
            not order_is_sucessful(status_id),
        "is not sucessful",
        f"robosats rated {rating} stars",
        extra_arg=rating
    ) is False:
        return False

    if not file_write(robot_dic["dir"] + "/rating-coordinator", rating):
        return False

    return True


def robot_order_post_action_argv(argv, order_post_function, extra_type=None):
    # pylint: disable=R0801 duplicate-code
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    extra_arg = ()

    if extra_type == "update_invoice":
        budget_ppm = None
        if len(argv) >= 1 and re.match('^--budget-ppm', argv[0]) is not None:
            argv = argv[1:]
            key_value = argv[0][2:].split("=", 1)
            if len(key_value) != 2:
                print_err("budget-ppm is not --budget-ppm=number")
                return False
            budget_ppm_string, budget_ppm_number_string = key_value

            if budget_ppm_string != "budget-ppm":
                print_err(f"key {budget_ppm_string} not recognied")
                return False

            budget_ppm = get_uint(budget_ppm_number_string)
            if budget_ppm is False:
                return False

        invoice = None
        if len(argv) >= 1:
            invoice = argv[0]
            argv = argv[1:]
        if not file_is_executable(roboauto_state["lightning_node_command"]) and invoice is None:
            invoice = input_ask("insert invoice: ")
            if invoice is False:
                return False
        if invoice == "":
            print_err("invoice not set")

        extra_arg = (budget_ppm, invoice)
    if extra_type == "escrow_pay":
        use_node = True
        if len(argv) >= 1 and argv[0] == "--no-node":
            use_node = False
            argv = argv[1:]

        extra_arg = use_node
    elif extra_type == "update_address":
        if len(argv) < 1:
            print_err("insert address")
            return False
        address = argv[0]
        argv = argv[1:]

        if len(argv) < 1:
            print_err("insert sat per vb")
            return False
        sat_per_vb = argv[0]
        argv = argv[1:]

        if not is_float(sat_per_vb, additional_check="positive"):
            print_err("sat per vb should be a positive float")
            return False

        extra_arg = (address, sat_per_vb)
    elif extra_type == "statement":
        # see frontend/src/components/TradeBox/index.tsx
        # maybe support also sending chat messages, not working in the main web client
        if len(argv) < 1:
            print_err("insert dispute statement")
            return False
        statement_arg = argv[0]
        argv = argv[1:]

        if statement_arg != "--file":
            statement = statement_arg
        else:
            if len(argv) < 1:
                print_err("insert dispute statement file")
                return False
            statement_file = argv[0]
            argv = argv[1:]

            if not os.path.isfile(statement_file):
                print_err(f"{statement_file} is not a file")
                return False
            statement = file_read(statement_file)
            if statement is False:
                return False

        statement_min_len = 100
        statement_max_len = 5000
        if len(statement) <= statement_min_len:
            print_err(f"dispute statement should be at least {statement_min_len} characters long")
            return False
        elif len(statement) >= statement_max_len:
            print_err(f"dispute statement should be at most {statement_max_len} characters long")
            return False

        extra_arg = statement
    elif extra_type == "rating":
        robot_name = robot_dic["name"]
        rating_coordinator_file = robot_dic["dir"] + "/rating-coordinator"
        if os.path.isfile(rating_coordinator_file):
            rating = file_read(rating_coordinator_file)
            if rating is False:
                return False
            print_err(f"{robot_name} already rated {rating}")
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

        extra_arg = rating
    elif extra_type == "save_chat":
        save_chat = True
        if len(argv) >= 1 and argv[0] == "--no-save-chat":
            argv = argv[1:]
            save_chat = False

        if save_chat is True:
            chat_response, chat_response_json = robot_requests_chat(robot_dic)
            if chat_response is False or chat_response_json is False:
                return False
            robot_name = robot_dic["name"]
            print_out(f"{robot_name} chat saved on disk")

    if extra_arg == ():
        return order_post_function(robot_dic)
    else:
        return order_post_function(robot_dic, extra_arg)


def order_buyer_update_invoice_argv(argv):
    return robot_order_post_action_argv(
        argv, order_buyer_update_invoice, extra_type="update_invoice"
    )


def order_buyer_update_address_argv(argv):
    return robot_order_post_action_argv(
        argv, order_buyer_update_address, extra_type="update_address"
    )


def order_submit_statement_argv(argv):
    return robot_order_post_action_argv(
        argv, order_submit_statement, extra_type="statement"
    )


def order_rate_coordinator_argv(argv):
    return robot_order_post_action_argv(
        argv, order_rate_coordinator, extra_type="rating"
    )


def order_collaborative_cancel_argv(argv):
    return robot_order_post_action_argv(
        argv, order_collaborative_cancel, extra_type="save_chat"
    )


def order_send_confirm_argv(argv):
    return robot_order_post_action_argv(
        argv, order_send_confirm, extra_type="save_chat"
    )


def order_start_dispute_argv(argv):
    return robot_order_post_action_argv(
        argv, order_start_dispute, extra_type="save_chat"
    )


def order_seller_bond_escrow_argv(argv):
    return robot_order_post_action_argv(
        argv, order_seller_bond_escrow, extra_type="escrow_pay"
    )


def order_pause_toggle_argv(argv):
    return robot_order_post_action_argv(argv, order_pause_toggle)


def order_undo_confirm_argv(argv):
    return robot_order_post_action_argv(argv, order_undo_confirm)
