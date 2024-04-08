#!/usr/bin/env python3

"""order_action.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=R1705 no-else-return

import filelock

from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.utils import \
    print_out, print_err, get_uint, subprocess_run_command, \
    json_loads
from roboauto.robot import \
    robot_get_current_fingerprint, robot_var_from_dic, \
    robot_input_from_argv, robot_get_lock_file
from roboauto.order_data import \
    order_is_waiting_seller_buyer, order_is_waiting_buyer, \
    order_is_waiting_seller, order_is_waiting_fiat_sent, \
    order_is_fiat_sent, order_is_public, order_is_paused
from roboauto.order import \
    robot_requests_get_order_dic, peer_nick_from_response, \
    amount_correct_from_response, subprocess_pay_invoice_and_check
from roboauto.requests_api import \
    requests_api_order_invoice, requests_api_order_pause, \
    requests_api_order_confirm, requests_api_order_undo_confirm, \
    requests_api_order_dispute, response_is_error, requests_api_order_cancel
from roboauto.gpg_key import gpg_sign_message


def order_buyer_update_invoice(robot_dic, budget_ppm=None):
    # pylint: disable=R0911 too-many-return-statements
    # pylint: disable=R0914 too-many-locals

    robot_name, _, robot_dir, token, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_dic = robot_requests_get_order_dic(robot_dic)
    if order_dic is False:
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
        print_err(f"{robot_name} {order_id} is not waiting for buyer")
        return False

    order_description = order_info["order_description"]
    print_out(f"{robot_name} {order_id} {order_description}")

    invoice_amount = order_response_json.get("invoice_amount", False)
    if invoice_amount is False:
        print_err("invoice amount is not present")
        return False

    if budget_ppm is None:
        budget_ppm = roboauto_options["routing_budget_ppm"]

    correct_invoice_amount = \
        int(invoice_amount * (1 - budget_ppm / 1000000))

    peer_nick = peer_nick_from_response(order_response_json)

    amount_correct = amount_correct_from_response(order_response_json)
    if amount_correct is False:
        amount_correct = order_info["amount_string"]

    invoice_generate_output = subprocess_run_command([
        roboauto_state["lightning_node_command"], "invoice",
        str(correct_invoice_amount),
        robot_name + "-" + peer_nick + "-" + order_id + "-" +
        order_user["type"] + "-" + order_user["currency"] + "-" +
        amount_correct
    ])
    if invoice_generate_output is False:
        print_err("generating the invoice")
        return False

    invoice = invoice_generate_output.decode()

    fingerprint = robot_get_current_fingerprint(robot_dir)
    if fingerprint is False:
        return False

    signed_invoice = gpg_sign_message(invoice, fingerprint, passphrase=token)
    if signed_invoice is False:
        print_err("signing invoice")
        return False

    order_invoice_response_all = requests_api_order_invoice(
        token_base91, order_id, robot_url, signed_invoice, budget_ppm
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

    print_out(f"{robot_name} {order_id} invoice sent successfully")

    return True


def order_seller_bond_escrow(robot_dic):
    robot_name = robot_dic["name"]

    order_dic = robot_requests_get_order_dic(robot_dic)
    if order_dic is False:
        return False

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
    print_out(f"{robot_name} {order_id} {order_description}")

    escrow_invoice = order_response_json.get("escrow_invoice", False)
    if escrow_invoice is False:
        print_err("escrow invoice not present in order response")
        return False

    peer_nick = peer_nick_from_response(order_response_json)

    amount_correct = amount_correct_from_response(order_response_json)
    if amount_correct is False:
        amount_correct = order_info["amount_string"]

    pay_command = [
        roboauto_state["lightning_node_command"], "pay",
        escrow_invoice,
        robot_name + "-" + peer_nick + "-" + order_id + "-" +
        order_user["type"] + "-" + order_user["currency"] + "-" +
        amount_correct
    ]
    return subprocess_pay_invoice_and_check(
        robot_dic, order_id,
        pay_command,
        lambda order_status : \
            not order_is_waiting_seller_buyer(order_status) and \
            not order_is_waiting_seller(order_status),
        "checking if escrow is paid...",
        "escrow paid successfully",
        "escrow not paid in time",
        maximum_retries=100
    )


def order_post_action_simple(
    robot_dic, order_post_function, is_wrong_status, string_error, string_or_bad_request
):
    # pylint: disable=R0911 too-many-return-statements
    # pylint: disable=R0914 too-many-locals

    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_dic = robot_requests_get_order_dic(robot_dic)
    if order_dic is False:
        return False

    order_info = order_dic["order_info"]

    status_id = order_info["status"]
    order_id = order_info["order_id"]

    if is_wrong_status(status_id):
        print_err(f"{robot_name} {order_id} " + string_error)
        return False

    order_description = order_info["order_description"]
    print_out(f"{robot_name} {order_id} {order_description}")

    order_post_response_all = order_post_function(
        token_base91, order_id, robot_url
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

        print_out(bad_request)
    else:
        if bad_request is not False:
            print_err(bad_request)
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


def robot_order_post_action_argv(argv, order_post_function, extra_args=None):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    if extra_args == "budget_ppm":
        budget_ppm = None
        if len(argv) >= 1:
            budget_ppm = get_uint(argv[0])
            if budget_ppm is False:
                return False
            argv = argv[1:]

    try:
        with filelock.SoftFileLock(
            robot_get_lock_file(robot_dic["name"]), timeout=roboauto_state["filelock_timeout"]
        ):
            if extra_args is None:
                return order_post_function(robot_dic)
            elif extra_args == "budget_ppm":
                return order_post_function(robot_dic, budget_ppm=budget_ppm)
            else:
                return False
    except filelock.Timeout:
        # pylint: disable=C0209 consider-using-f-string
        print_err("filelock timeout %d" % roboauto_state["filelock_timeout"])
        return False


def order_buyer_update_invoice_argv(argv):
    return robot_order_post_action_argv(
        argv, order_buyer_update_invoice, extra_args="budget_ppm"
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
