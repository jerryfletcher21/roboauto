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
from roboauto.order_local import order_get_order_dic
from roboauto.order import order_requests_order_dic
from roboauto.chat import \
    robot_requests_chat, chat_print_encrypted_messages, chat_print_single_message
from roboauto.requests_api import \
    requests_api_limits, requests_api_info, response_is_error
from roboauto.utils import \
    file_json_read, json_loads, json_dumps, \
    roboauto_get_coordinator_url, roboauto_get_coordinator_from_argv, \
    token_get_base91


def list_limits(argv):
    _, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    limits_response_all = requests_api_limits(coordinator_url)
    if response_is_error(limits_response_all):
        return False
    limits_response = limits_response_all.text
    limits_response_json = json_loads(limits_response)
    if limits_response_json is False:
        print_err(limits_response, end="", error=False, date=False)
        print_err("limits response is not json")
        return False

    print_out(json_dumps(limits_response_json))

    return True


def robosats_info(argv):
    _, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    info_response_all = requests_api_info(coordinator_url)
    if response_is_error(info_response_all):
        return False
    info_response = info_response_all.text
    info_response_json = json_loads(info_response)
    if info_response_json is False:
        print_err(info_response, end="", error=False, date=False)
        print_err("info response is not json")
        return False

    print_out(json_dumps(info_response_json))

    return True


def robot_info_argv(argv):
    # pylint: disable=R0911 too-many-return-statements
    # pylint: disable=R0912 too-many-branches
    # pylint: disable=R0915 too-many-statements

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

    robot_response, robot_response_json = robot_requests_robot(
        token_base91, robot_url, robot_dic
    )
    if robot_response is False:
        return False

    print_out(json_dumps(robot_response_json))

    return True


def order_info_argv(argv):
    # pylint: disable=R0911 too-many-return-statements

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, robot_dir, _, _, _, _ = robot_var_from_dic(robot_dic)

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

    print_out(json_dumps(order_dic))

    return True


def robot_chat(argv):
    # pylint: disable=R0911 too-many-return-statements
    # pylint: disable=R0912 too-many-branches

    from_local = False
    if len(argv) > 0 and argv[0] == "--local":
        from_local = True
        argv = argv[1:]

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_dir = robot_dic["dir"]
    token = robot_dic["token"]
    token_base91 = token_get_base91(token)
    robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])

    if from_local is False:
        chat_response, chat_response_json = robot_requests_chat(
            robot_dir, token_base91, robot_url
        )
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
