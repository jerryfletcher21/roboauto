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
    robot_dir_search, robot_get_token_base91, \
    robot_get_coordinator, robot_input_ask, \
    token_get_base91
from roboauto.order import get_order_string, api_order_get_dic
from roboauto.requests_api import \
    requests_api_limits, \
    requests_api_info, requests_api_robot, \
    requests_api_chat
from roboauto.utils import \
    file_read, file_write, \
    file_json_read, file_json_write, \
    json_loads, json_dumps, \
    password_ask_token, \
    roboauto_get_coordinator_url, \
    roboauto_get_coordinator_from_argv, \
    dir_make_sure_exists


def list_limits(argv):
    _, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    limits_response = requests_api_limits(coordinator_url).text
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

    info_response = requests_api_info(coordinator_url).text
    info_response_json = json_loads(info_response)
    if not info_response_json:
        print_err(info_response, end="", error=False, date=False)
        print_err("info response is not json")
        return False

    print_out(json_dumps(info_response_json))

    return True


def robot_info(argv):
    robot = False
    robot_dir = False
    order_print = True
    token_base91 = False
    while len(argv) > 0:
        if argv[0] == "--no-order":
            order_print = False
        elif argv[0] == "--stdin":
            token_string = sys.stdin.readline().rstrip()
            token_base91 = token_get_base91(token_string)
        elif argv[0] == "--stdin-base91":
            token_base91 = sys.stdin.readline().rstrip()
        else:
            break
        argv = argv[1:]

    if token_base91 is False:
        robot, argv = robot_input_ask(argv)
        if robot is False:
            return False

        robot_dir = robot_dir_search(robot)
        if robot_dir is False:
            return False

        token_base91 = robot_get_token_base91(robot, robot_dir)
        if token_base91 is False:
            print_err("getting token base91 for " + robot)
            return False

        robot_url = roboauto_get_coordinator_url(
            robot_get_coordinator(robot, robot_dir)
        )
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

    robot_response = requests_api_robot(token_base91, robot_url).text
    robot_response_json = json_loads(robot_response)
    if robot_response_json is False:
        print_err(robot_response, end="", error=False, date=False)
        print_err("robot response is not json")
        return False

    print_out(json_dumps(robot_response_json))

    if robot is False:
        robot = robot_response_json.get("nickname", "unknown")

    order_id_number = robot_response_json.get("active_order_id", False)
    if order_id_number is False:
        order_id_number = robot_response_json.get("last_order_id", False)
        if order_id_number is False:
            print_err(robot + " does not have active orders")
            return True

    order_id = str(order_id_number)

    if order_print:
        order_dic = api_order_get_dic(robot, token_base91, robot_url, order_id)
        if order_dic is False:
            return False
        if order_dic is None:
            print_err("%s order not available" % robot)
            return False

        if robot_dir is not False:
            orders_dir = robot_dir + "/orders"
            if not dir_make_sure_exists(orders_dir):
                return False
            order_file = orders_dir + "/" + order_id
            if not file_json_write(order_file, order_dic):
                print_err("saving order %s to file" % order_id)
                return False

        order_response_json = order_dic["order_response_json"]

        print_out(json_dumps(order_response_json))

        order_status = order_response_json.get("status", False)
        if order_status is False:
            print_err(json_dumps(order_response_json), error=False, date=False)
            print_err("order getting order_status for " + robot)
            return False

        status = get_order_string(order_status)
        print_out(robot + " " + order_id + " " + status)

        chat_print = False
        if chat_print:
            chat_response = requests_api_chat(token_base91, order_id, robot_url).text
            chat_response_json = json_loads(chat_response)
            if not chat_response_json:
                print_err(chat_response, end="", error=False, date=False)
                print_err("chat response is not json")
                return False

            print_out(json_dumps(chat_response_json))

    return True
