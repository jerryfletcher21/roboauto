#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0914 too-many-locals
# pylint: disable=R0915 too-many-statements
# pylint: disable=W0611 unused-import


import sys

from roboauto.logger import print_out, print_err
from roboauto.robot import robot_dir_search, robot_get_token_base91, robot_get_coordinator
from roboauto.order import get_order_string
from roboauto.requests_api import \
    requests_api_limits, \
    requests_api_info, requests_api_robot, \
    requests_api_order, requests_api_chat
from roboauto.utils import \
    file_read, file_write, \
    file_json_read, \
    json_loads, json_dumps, \
    input_ask_robot, password_ask_token, \
    roboauto_get_coordinator_url


def list_limits():
    limits_response = requests_api_limits().text
    limits_response_json = json_loads(limits_response)
    if not limits_response_json:
        print_err(limits_response, end="", error=False, date=False)
        print_err("limits response is not json")
        return False

    print_out(json_dumps(limits_response_json))

    return True


def robosats_info():
    info_response = requests_api_info().text
    info_response_json = json_loads(info_response)
    if not info_response_json:
        print_err(info_response, end="", error=False, date=False)
        print_err("info response is not json")
        return False

    print_out(json_dumps(info_response_json))

    return True


def robot_info(argv):
    order_print = True
    token_base91 = False
    while len(argv) > 0:
        if argv[0] == "--no-order":
            order_print = False
        elif argv[0] == "--stdin":
            token_base91 = sys.stdin.readline().rstrip()
        else:
            break
        argv = argv[1:]

    if token_base91 is False:
        if len(argv) >= 1:
            robot = argv[0]
            argv = argv[1:]
        else:
            robot = input_ask_robot()
            if robot is False:
                return False
        if robot == "":
            print_err("robot name not set")
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

    robot_response = requests_api_robot(token_base91, robot_url).text
    robot_response_json = json_loads(robot_response)
    if robot_response_json is False:
        print_err(robot_response, end="", error=False, date=False)
        print_err("robot response is not json")
        return False

    print_out(json_dumps(robot_response_json))

    order_id_number = robot_response_json.get("active_order_id", False)
    if order_id_number is False:
        order_id_number = robot_response_json.get("last_order_id", False)
        if order_id_number is False:
            print_err(robot + " does not have active orders")
            return True

    order_id = str(order_id_number)

    if order_print:
        order_response = requests_api_order(token_base91, order_id, robot_url).text
        order_response_json = json_loads(order_response)
        if not order_response_json:
            print_err(order_response, end="", error=False, date=False)
            print_err("order response is not json")
            return False

        print_out(json_dumps(order_response_json))

        order_status = order_response_json.get("status", False)
        if order_status is False:
            print_err(order_response, end="", error=False, date=False)
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
