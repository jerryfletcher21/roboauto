#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0914 too-many-locals
# pylint: disable=R0915 too-many-statements
# pylint: disable=R1705 no-else-return

import os
import time
import shutil
import datetime

import filelock

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import \
    robot_set_dir, robot_get_token_base91, \
    robot_get_lock_file, robot_list_dir, robot_get_coordinator
from roboauto.order import \
    api_order_get_dic, \
    bond_order, wait_order, make_order, \
    robot_set_inactive, \
    order_is_public, order_is_paused, \
    order_is_waiting_maker_bond, order_is_waiting_taker_bond, \
    order_is_expired
from roboauto.requests_api import requests_api_robot, requests_api_book, response_is_error
from roboauto.book import get_offers_per_hour
from roboauto.utils import \
    get_uint, json_loads, dir_make_sure_exists, \
    file_json_write, file_json_read, \
    update_roboauto_options, \
    roboauto_get_coordinator_url


def slowly_move_to_active(argv):
    roboauto_state["print_date"] = True
    if len(argv) >= 1:
        slowly_paused_interval_string = argv[0]
        argv = argv[:1]
        slowly_paused_interval = get_uint(slowly_paused_interval_string)
        if slowly_paused_interval is False:
            return False
    else:
        slowly_paused_interval = roboauto_options["slowly_paused_interval_global"]

    while len(os.listdir(roboauto_state["paused_home"])) > 0:
        robot_dir = os.listdir(roboauto_state["paused_home"])[0]
        robot = robot_dir.split("/")[-1]

        try:
            shutil.move(robot_dir, roboauto_state["active_home"])
            print_out("robot %s moved to active from pause" % robot)
        except OSError:
            print_err("moving %s to active" % robot)

        if len(os.listdir(roboauto_state["paused_home"])) < 1:
            break

        time.sleep(slowly_paused_interval)

    return True


def robot_check_expired(robot, token_base91, robot_url, robot_this_hour=0):
    robot_response = requests_api_robot(token_base91, robot_url).text
    robot_response_json = json_loads(robot_response)
    if robot_response_json is False:
        print_err(robot_response, end="", error=False, date=False)
        print_err("getting robot response")
        return False

    order_id_number = robot_response_json.get("active_order_id", False)
    if order_id_number is False:
        order_id_number = robot_response_json.get("last_order_id", False)
        if order_id_number is False:
            print_err(robot_response, end="", error=False, date=False)
            print_err("getting order_id for " + robot)
            return False

    order_id = str(order_id_number)

    order_dic = api_order_get_dic(robot, token_base91, robot_url, order_id)
    if order_dic is False:
        return False
    elif order_dic is None:
        print_out(robot + " last order not available")
        print_out(robot + " moving to paused")
        if not robot_set_dir(roboauto_state["paused_home"], [robot]):
            print_err("moving " + robot + " to paused")
            return False
        return 0

    order_info = order_dic["order_info"]

    robot_dir = roboauto_state["active_home"] + "/" + robot
    orders_dir = robot_dir + "/orders"
    if not dir_make_sure_exists(orders_dir):
        return False
    order_file = orders_dir + "/" + order_id
    if not file_json_write(order_file, order_dic):
        print_err("saving order %s to file" % order_id)
        return False

    print_out(robot + " " + order_id + " " + order_info["status_string"])

    maximum_per_hour = roboauto_options["order_maximum"]
    # maximum_per_hour = \
    #     int(len(robot_list_dir(active_home)) / 24) + \
    #     roboauto_options["order_maximum"]

    status_id = order_info["status"]

    if order_is_public(status_id):
        print_err(robot + " " + order_id + " checked but was online")
        return False
    elif order_is_paused(status_id):
        print_out(robot + " " + order_id + " " + order_info["order_description"])
        print_out(robot + " " + order_id + " moving to paused")
        if not robot_set_dir(roboauto_state["paused_home"], [robot]):
            print_err("moving " + robot + " to paused")
            return False
    elif order_is_waiting_taker_bond(status_id):
        print_out(robot + " " + order_id + " is in the process of being taken")
    elif order_is_waiting_maker_bond(status_id):
        if robot_this_hour < maximum_per_hour:
            if bond_order(robot, token_base91, robot_url, order_id, False):
                return 1
            else:
                return False
        else:
            if wait_order(robot):
                return 0
            else:
                return False
    elif order_is_expired(status_id):
        if robot_this_hour < maximum_per_hour:
            if make_order(
                robot, token_base91, robot_url, order_id,
                order_dic["order_data"], order_info["satoshis_now"]
            ):
                return 1
            else:
                return False
        else:
            if wait_order(robot):
                return 0
            else:
                return False
    else:
        if robot_set_inactive(robot, order_id, order_info["order_description"]):
            return 0
        else:
            return False

    return 0


def list_orders_single_book(coordinator, coordinator_url, robot_list):
    book_response_pre = requests_api_book(coordinator_url, until_true=False)
    if response_is_error(book_response_pre):
        print_err("connecting to coordinator %s" % coordinator)
        return False

    book_response = book_response_pre.text
    book_response_json = json_loads(book_response)
    if book_response_json is False:
        print_err(book_response, error=False, date=False)
        print_err("getting book")
        return False

    nicks = []
    for offer in book_response_json:
        nicks.append(offer["maker_nick"])

    if os.path.isfile(roboauto_state["waiting_queue_file"]):
        nicks_waiting = file_json_read(roboauto_state["waiting_queue_file"])
        if nicks_waiting is False:
            print_err("reading waiting queue")
            return False
    else:
        nicks_waiting = []

    offers_per_hour_relative = False
    if offers_per_hour_relative is True:
        hour_position = -1
    else:
        hour_position = int(datetime.datetime.now().strftime("%H"))
    robot_this_hour = len(get_offers_per_hour(
        offers_per_hour_relative
    )[hour_position])
    maximum_per_hour = roboauto_options["order_maximum"]
    # maximum_per_hour = \
    #     int(len(robot_list_dir(active_home)) / 24) + \
    #     roboauto_options["order_maximum"]

    for robot in robot_list:
        robot_dir = roboauto_state["active_home"] + "/" + robot
        token_base91 = robot_get_token_base91(robot, robot_dir)
        if token_base91 is False:
            print_err("getting token base91 for " + robot)
            continue
        robot_url = roboauto_get_coordinator_url(
            robot_get_coordinator(robot, robot_dir)
        )

        if robot not in nicks:
            if robot not in nicks_waiting:
                try:
                    with filelock.SoftFileLock(robot_get_lock_file(robot)):
                        expired_response = robot_check_expired(
                            robot, token_base91, robot_url, robot_this_hour=robot_this_hour
                        )
                        if expired_response is not False:
                            robot_this_hour += expired_response
                except filelock.Timeout:
                    print_err("filelock timeout %d" % roboauto_state["filelock_timeout"])
                    continue
        elif robot in nicks_waiting:
            print_err(robot + " is waiting and also active")
            continue

    if robot_this_hour < maximum_per_hour and len(nicks_waiting) > 0:
        robot_activate = nicks_waiting.pop(0)
        print_out(robot_activate + " removed from waiting queue")
        if file_json_write(roboauto_state["waiting_queue_file"], nicks_waiting) is False:
            print_err("writing waiting queue")
            return False

    return True


def keep_online():
    roboauto_state["print_date"] = True
    robot_list = robot_list_dir(roboauto_state["active_home"])
    if len(robot_list) < 1:
        print_out("there are no active robots", date=False)
        return True

    print_out("current active robots are:", date=False)
    for robot in robot_list:
        print_out(robot, date=False)
    print_out("\n", end="", date=False)

    while True:
        # allow to adjust configs while roboauto is running
        if update_roboauto_options(True) is False:
            print_err("reading the config file")

        robot_list = robot_list_dir(roboauto_state["active_home"])
        robot_list_len = len(robot_list)
        maximum_possible_orders = 24 * roboauto_options["order_maximum"]
        if robot_list_len < 1:
            print_out("there are no active robots")
            return True
        elif robot_list_len > maximum_possible_orders:
            print_out(
                "there are %d active robot but a maximum of %s can be active" %
                (robot_list_len, maximum_possible_orders)
            )

        coordinator_robot_list = {}

        for robot in robot_list:
            robot_dir = roboauto_state["active_home"] + "/" + robot
            coordinator = robot_get_coordinator(robot, robot_dir)
            if coordinator_robot_list.get(coordinator, False) is False:
                coordinator_robot_list.update({coordinator: []})
            coordinator_robot_list[coordinator].append(robot)

        for coordinator, robot_list in coordinator_robot_list.items():
            list_orders_single_book(
                coordinator, roboauto_get_coordinator_url(coordinator),
                robot_list
            )

        time.sleep(roboauto_options["book_interval"])

    return True
