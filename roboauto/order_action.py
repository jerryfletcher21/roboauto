#!/usr/bin/env python3

"""order_action.py"""

# pylint: disable=C0116 missing-function-docstring

import os

from roboauto.global_state import roboauto_options
from roboauto.utils import \
    print_out, print_err, get_uint, json_loads, json_dumps, \
    budget_ppm_from_argv, input_ask, file_write, file_read, \
    invoice_get_correct_amount
from roboauto.robot import \
    robot_get_current_fingerprint, robot_var_from_dic, \
    robot_input_from_argv, robot_change_dir
from roboauto.order_data import \
    order_is_waiting_seller_buyer, order_is_waiting_buyer, \
    order_is_waiting_seller, order_is_waiting_fiat_sent, \
    order_is_fiat_sent, order_is_public, order_is_paused, \
    order_is_sucessful, order_is_expired, get_order_string
from roboauto.order import \
    order_requests_order_dic, peer_nick_from_response, bond_order, \
    amount_correct_from_response, premium_string_get, \
    order_string_status_print
from roboauto.requests_api import \
    requests_api_order_invoice, requests_api_order_pause, \
    requests_api_order_confirm, requests_api_order_undo_confirm, \
    requests_api_order_dispute, response_is_error, \
    requests_api_order_cancel, requests_api_order_rate
from roboauto.gpg_key import gpg_sign_message
from roboauto.subprocess_commands import \
    subprocess_generate_invoice, \
    subprocess_pay_invoice_and_check


def order_take_argv(argv):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name = robot_dic["name"]

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

    if bond_order(robot_dic, order_id, taker=True, take_amount=take_amount) is False:
        return False

    print_out(f"{robot_name} {order_id} taken successfully")

    if not robot_change_dir(robot_name, "pending"):
        return False

    return True


def order_buyer_update_invoice(robot_dic, budget_ppm=None):
    robot_name, _, robot_dir, token, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or order_dic is None:
        return False

    # pylint: disable=R0801 duplicate-code
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
        print_err(f"{robot_name} {order_id} is not waiting for buyer")
        return False

    order_description = order_info["order_description"]

    peer_nick = peer_nick_from_response(order_response_json)

    order_string_status_print(robot_name, order_id, order_description, peer_nick)

    invoice_amount = order_response_json.get("invoice_amount", False)
    if invoice_amount is False:
        print_err("invoice amount is not present")
        return False

    if budget_ppm is None:
        budget_ppm = roboauto_options["routing_budget_ppm"]

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

    fingerprint = robot_get_current_fingerprint(robot_dir)
    if fingerprint is False:
        return False

    signed_invoice = gpg_sign_message(invoice, fingerprint, passphrase=token)
    if signed_invoice is False:
        print_err("signing invoice")
        return False

    order_invoice_response_all = requests_api_order_invoice(
        token_base91, order_id, robot_url, robot_name, signed_invoice, budget_ppm
    )
    if response_is_error(order_invoice_response_all):
        return False
    order_invoice_response = order_invoice_response_all.text
    order_invoice_response_json = json_loads(order_invoice_response)
    if order_invoice_response_json is False:
        print_err(order_invoice_response, end="", error=False, date=False)
        print_err(f"{robot_name} {order_id} sending invoice")
        return False

    bad_request = order_invoice_response_json.get("bad_request", False)
    if bad_request is not False:
        print_err(bad_request, date=False, error=False)
        return False

    new_status_id = order_invoice_response_json.get("status", False)
    if new_status_id is False:
        print_err(json_dumps(order_invoice_response_json), date=False, error=False)
        print_err("invoice not sent, no new status")
        return False

    if \
        not order_is_waiting_seller(new_status_id) and \
        not order_is_waiting_fiat_sent(new_status_id):
        print_err(json_dumps(order_invoice_response_json), date=False, error=False)
        print_err("invoice not send, current status: " + get_order_string(new_status_id))
        return False

    print_out(f"{robot_name} {order_id} invoice sent successfully")

    return True


def order_seller_bond_escrow(robot_dic):
    robot_name = robot_dic["name"]

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or order_dic is None:
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

    pay_label = \
        robot_name + "-" + str(peer_nick) + "-" + order_id + "-" + \
        order_user["type"] + "-" + order_user["currency"] + "-" + \
        amount_correct + "-" + premium_string_get(order_user["premium"])
    return subprocess_pay_invoice_and_check(
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
    )


def order_post_action_simple(
    robot_dic, order_post_function, is_wrong_status,
    string_error, string_or_bad_request,
    extra_arg=None
):
    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_dic = order_requests_order_dic(robot_dic, order_id=False)
    if order_dic is False or order_dic is None:
        return False

    order_info = order_dic["order_info"]
    order_response_json = order_dic["order_response_json"]

    status_id = order_info["status"]
    order_id = order_info["order_id"]

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


# should check that is buyer
def order_undo_confirm(robot_dic):
    return order_post_action_simple(
        robot_dic,
        requests_api_order_undo_confirm,
        lambda status_id : \
            not order_is_fiat_sent(status_id),
        "can not undo confirm payment",
        "confirmation undone"
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


def order_rate_coordinator(robot_dic, rating):
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
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    if extra_type == "budget_ppm":
        budget_ppm, argv = budget_ppm_from_argv(argv)
        if argv is False:
            return False

        extra_arg = budget_ppm
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

    if extra_type is None or extra_type is None:
        return order_post_function(robot_dic)
    else:
        return order_post_function(robot_dic, extra_arg)


def order_buyer_update_invoice_argv(argv):
    return robot_order_post_action_argv(
        argv, order_buyer_update_invoice, extra_type="budget_ppm"
    )


def order_rate_coordinator_argv(argv):
    return robot_order_post_action_argv(
        argv, order_rate_coordinator, extra_type="rating"
    )


def order_seller_bond_escrow_argv(argv):
    return robot_order_post_action_argv(argv, order_seller_bond_escrow)


def order_pause_toggle_argv(argv):
    return robot_order_post_action_argv(argv, order_pause_toggle)


def order_collaborative_cancel_argv(argv):
    return robot_order_post_action_argv(argv, order_collaborative_cancel)


def order_send_confirm_argv(argv):
    return robot_order_post_action_argv(argv, order_send_confirm)


def order_undo_confirm_argv(argv):
    return robot_order_post_action_argv(argv, order_undo_confirm)


def order_start_dispute_argv(argv):
    return robot_order_post_action_argv(argv, order_start_dispute)
