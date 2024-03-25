#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0914 too-many-locals
# pylint: disable=R0915 too-many-statements
# pylint: disable=W0611 unused-import

import sys
import re

from roboauto.logger import print_out, print_err
from roboauto.robot import \
    robot_input_from_argv, robot_requests_robot
from roboauto.order_local import get_order_string, order_save_order_file
from roboauto.order import api_order_get_dic_handle
from roboauto.requests_api import \
    requests_api_limits, requests_api_info, \
    requests_api_chat, response_is_error
from roboauto.utils import \
    file_read, file_write, \
    file_json_read, file_json_write, \
    json_loads, json_dumps, \
    password_ask_token, \
    roboauto_get_coordinator_url, \
    roboauto_get_coordinator_from_argv, \
    dir_make_sure_exists, \
    token_get_base91, token_get_double_sha256


def list_limits(argv):
    _, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    limits_response_all = requests_api_limits(coordinator_url)
    if response_is_error(limits_response_all):
        return False
    limits_response = limits_response_all.text
    limits_response_json = json_loads(limits_response)
    if not limits_response_json:
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
    if not info_response_json:
        print_err(info_response, end="", error=False, date=False)
        print_err("info response is not json")
        return False

    print_out(json_dumps(info_response_json))

    return True


def robot_info(argv):
    """print info about a robot and his order if --no-order is not specified"""
    robot_name = False
    robot_dir = False

    robot_print = True
    order_print = True
    chat_print = False

    token_base91 = False

    while len(argv) > 0:
        if argv[0] == "--no-order":
            order_print = False
        elif argv[0] == "--chat":
            robot_print = False
            order_print = False
            chat_print = True
        elif argv[0] == "--stdin":
            token_string = sys.stdin.readline().rstrip()
            token_base91 = token_get_base91(token_string)
        elif argv[0] == "--stdin-base91":
            token_base91 = sys.stdin.readline().rstrip()
        else:
            break
        argv = argv[1:]

    if token_base91 is False:
        robot_dic, argv = robot_input_from_argv(argv)
        if robot_dic is False:
            return False

        robot_name = robot_dic["name"]
        token_base91 = token_get_base91(robot_dic["token"])
        robot_dir = robot_dic["dir"]
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

    robot_response, robot_response_json = robot_requests_robot(token_base91, robot_url)
    if robot_response is False:
        return False

    if robot_print:
        print_out(json_dumps(robot_response_json))

    if order_print or chat_print:
        if robot_name is False:
            robot_name = robot_response_json.get("nickname", "unknown")

        order_id_number = robot_response_json.get("active_order_id", False)
        if order_id_number is False:
            order_id_number = robot_response_json.get("last_order_id", False)
            if order_id_number is False:
                print_err(robot_name + " does not have active orders")
                return True

        order_id = str(order_id_number)

        order_dic = api_order_get_dic_handle(robot_name, token_base91, robot_url, order_id)
        if order_dic is False:
            return False

        if robot_dir is not False:
            if not order_save_order_file(robot_dir, order_id, order_dic):
                return False

        order_response_json = order_dic["order_response_json"]

        if order_print:
            print_out(json_dumps(order_response_json))

        if chat_print:
            chat_response_all = requests_api_chat(token_base91, order_id, robot_url)
            if response_is_error(chat_response_all):
                return False
            chat_response = chat_response_all.text
            chat_response_json = json_loads(chat_response)
            if not chat_response_json:
                print_err(chat_response, end="", error=False, date=False)
                print_err("chat response is not json")
                return False

            print_out(json_dumps(chat_response_json))

    return True
