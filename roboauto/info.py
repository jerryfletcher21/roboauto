#!/usr/bin/env python3

"""info.py"""

# pylint: disable=C0116 missing-function-docstring

import sys
import os
import re

from roboauto.logger import print_out, print_err
from roboauto.robot import \
    robot_input_from_argv, robot_requests_robot, \
    robot_var_from_dic, robot_requests_get_order_id
from roboauto.order_local import \
    order_get_order_dic, order_dic_from_robot_dic, \
    order_dic_print
from roboauto.order import order_requests_order_dic
from roboauto.chat import \
    robot_requests_chat, chat_print_encrypted_messages, chat_print_single_message
from roboauto.requests_api import \
    response_is_error, requests_api_info, \
    requests_api_historical, requests_api_limits, \
    requests_api_price, requests_api_ticks
from roboauto.utils import \
    file_json_read, json_loads, json_dumps, \
    roboauto_get_coordinator_url, roboauto_get_coordinator_from_argv, \
    token_get_base91


def requests_simple_handle(
    requests_function, coordinator_url, coordinator, description_string
):
    response_all = requests_function(coordinator_url, coordinator)
    if response_is_error(response_all):
        return False
    response = response_all.text
    response_json = json_loads(response)
    if response_json is False:
        print_err(response, end="", error=False, date=False)
        print_err(f"{description_string} response is not json")
        return False

    return response_json


def list_historical(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    historical_response_json = requests_simple_handle(
        requests_api_historical, coordinator_url, coordinator, "historical"
    )
    if historical_response_json is False:
        return False

    print_out(json_dumps(historical_response_json))

    return True


def list_limits(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    limits_response_json = requests_simple_handle(
        requests_api_limits, coordinator_url, coordinator, "limits"
    )
    if limits_response_json is False:
        return False

    print_out(json_dumps(limits_response_json))

    return True


def list_price(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    price_response_json = requests_simple_handle(
        requests_api_price, coordinator_url, coordinator, "price"
    )
    if price_response_json is False:
        return False

    print_out(json_dumps(price_response_json))

    return True


def list_ticks(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    if len(argv) < 1:
        print_err("insert start date")
        return False
    start_date = argv[0]
    argv = argv[1:]

    if len(argv) < 1:
        print_err("insert end date")
        return False
    end_date = argv[0]
    argv = argv[1:]

    ticks_response_all = requests_api_ticks(
        coordinator_url, coordinator, start_date, end_date
    )
    if response_is_error(ticks_response_all):
        return False
    ticks_response = ticks_response_all.text
    ticks_response_json = json_loads(ticks_response)
    if ticks_response_json is False:
        print_err(ticks_response, end="", error=False, date=False)
        print_err("ticks response is not json")
        return False

    print_out(json_dumps(ticks_response_json))

    return True


def robosats_info(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    info_response_json = requests_simple_handle(
        requests_api_info, coordinator_url, coordinator, "info"
    )
    if info_response_json is False:
        return False

    print_out(json_dumps(info_response_json))

    return True


def robot_info_argv(argv):
    """print info about a robot"""

    robot_dic = None

    token_base91 = False

    while len(argv) > 0:
        if argv[0] == "--stdin":
            token_base91 = token_get_base91(sys.stdin.readline().rstrip())
        elif argv[0] == "--stdin-base91":
            token_base91 = sys.stdin.readline().rstrip()
        else:
            break
        argv = argv[1:]

    if token_base91 is False:
        robot_dic, argv = robot_input_from_argv(argv)
        if robot_dic is False:
            return False

        token_base91 = token_get_base91(robot_dic["token"])
        robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])
    else:
        if len(argv) < 1:
            print_err("insert coordinator name or link")
            return False

        if re.match('^--', argv[0]) is None:
            robot_url = argv[0]
            argv = argv[1:]
        else:
            _, robot_url, argv = roboauto_get_coordinator_from_argv(argv)
            if robot_url is False:
                return False

    # pylint: disable=R0801 duplicate-code
    robot_response, robot_response_json = robot_requests_robot(
        token_base91, robot_url, robot_dic
    )
    if robot_response is False:
        return False

    print_out(json_dumps(robot_response_json))

    return True


def order_info_argv(argv):
    full_mode = True
    local_mode = False
    while len(argv) > 0:
        first_argv = argv[0]
        if first_argv == "--local":
            local_mode = True
            argv = argv[1:]
        elif first_argv == "--simple":
            full_mode = False
            argv = argv[1:]
        elif re.match('^-', first_argv) is not None:
            print_err(f"{first_argv} not recognied")
            return False
        else:
            break

    # pylint: disable=R0801 duplicate-code
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, robot_dir, _, coordinator, _, _ = robot_var_from_dic(robot_dic)

    if local_mode is False:
        order_dic = order_get_order_dic(robot_dir, error_print=False)
        if order_dic is not False:
            order_info = order_dic.get("order_info", False)
            if order_info is False:
                return False

            order_id = order_info.get("order_id", False)
            if order_id is False:
                return False
        else:
            print_out("robot does not have orders saved, searching it")

            order_id = robot_requests_get_order_id(robot_dic, error_print=False)
            if order_id is False:
                print_err(f"{robot_name} does not have active or last orders")
                return False

        order_dic = order_requests_order_dic(robot_dic, order_id)
        if order_dic is False or order_dic is None:
            return False
    else:
        if len(argv) >= 1:
            order_id = argv[0]
            argv = argv[1:]
        else:
            order_id = False

        order_dic = order_dic_from_robot_dic(robot_dic, order_id)
        if order_dic is None:
            print_err(json_dumps({"error": "no order dir"}))
            return False
        if order_dic is False:
            return False

    order_dic_print(
        order_dic, robot_name, coordinator, one_line=False, full_mode=full_mode
    )

    return True


def robot_chat(argv):
    from_local = False
    if len(argv) > 0 and argv[0] == "--local":
        from_local = True
        argv = argv[1:]

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_dir = robot_dic["dir"]
    token = robot_dic["token"]

    if from_local is False:
        chat_response, chat_response_json = robot_requests_chat(robot_dic)
        if chat_response is False:
            return False

        if not chat_print_encrypted_messages(chat_response_json, robot_dir, token):
            return False
    else:
        decrypted_messages_file = robot_dir + "/messages-decrypted"
        chat_response_file = robot_dir + "/chat-response"

        if os.path.isfile(decrypted_messages_file):
            decrypted_messages = file_json_read(decrypted_messages_file)
            if decrypted_messages is False:
                return False

            first_message = True
            for message_dic in decrypted_messages:
                if first_message:
                    first_message = False
                else:
                    print_out("\n", end="")

                if chat_print_single_message(message_dic) is False:
                    return False
        elif os.path.isfile(chat_response_file):
            chat_response_json = file_json_read(chat_response_file)
            if chat_response_json is False:
                return False

            if not chat_print_encrypted_messages(chat_response_json, robot_dir, token):
                return False
        else:
            print_err("there are no local messages")
            return False

    return True
