#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0914 too-many-locals
# pylint: disable=R0915 too-many-statements
# pylint: disable=R1703 simplifiable-if-statement
# pylint: disable=R1705 no-else-return

import os
import time
import shutil

import filelock

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import \
    robot_get_lock_file, robot_list_dir, robot_load_from_name, \
    waiting_queue_get, robot_requests_robot, robot_change_dir
from roboauto.order_local import \
    robot_handle_taken, \
    order_is_public, order_is_paused, \
    order_is_waiting_maker_bond, order_is_waiting_taker_bond, \
    order_is_expired, order_get_order_dic, orders_get_directory, \
    order_save_order_file
from roboauto.order import \
    api_order_get_dic, bond_order, wait_order, make_order
from roboauto.book import \
    get_book_response_json, get_hour_offer, \
    get_current_timestamp, \
    get_current_hour_from_timestamp, get_current_minutes_from_timestamp
from roboauto.utils import \
    get_uint, file_json_write, \
    update_roboauto_options, \
    roboauto_get_coordinator_url, token_get_base91


def slowly_move_to_active(argv):
    roboauto_state["print_date"] = True

    if len(argv) >= 1:
        slowly_paused_interval_string = argv[0]
        argv = argv[:1]
        slowly_paused_interval = get_uint(slowly_paused_interval_string)
        if slowly_paused_interval is False:
            return False
    else:
        slowly_paused_interval = roboauto_options["slowly_paused_interval"]

    while len(os.listdir(roboauto_state["paused_home"])) > 0:
        robot_name = os.listdir(roboauto_state["paused_home"])[0]
        robot_dir = roboauto_state["paused_home"] + "/" + robot_name

        try:
            shutil.move(robot_dir, roboauto_state["active_home"])
            print_out("robot %s moved to active from pause" % robot_name)
        except OSError:
            print_err("moving %s to active" % robot_name)

        if len(os.listdir(roboauto_state["paused_home"])) < 1:
            break

        time.sleep(slowly_paused_interval)

    return True


def robot_check_expired(robot_dic, robot_this_hour):
    """check what happened to a robot that is no longer active
    return 1 if the robot is back online, 0 if not, false if something wrong"""

    robot_name = robot_dic["name"]
    token_base91 = token_get_base91(robot_dic["token"])
    robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])
    robot_dir = robot_dic["dir"]

    robot_response, robot_response_json = robot_requests_robot(
        token_base91, robot_url, robot_dic
    )
    if robot_response is False:
        return False

    order_id_number = robot_response_json.get("active_order_id", False)
    if order_id_number is False:
        order_id_number = robot_response_json.get("last_order_id", False)
        if order_id_number is False:
            print_err(robot_response, error=False, date=False)
            print_err("getting order_id for " + robot_name)
            return False

    order_id = str(order_id_number)

    order_dic = api_order_get_dic(robot_name, token_base91, robot_url, order_id)
    if order_dic is False:
        return False
    elif order_dic is None:
        print_out(robot_name + " last order not available")
        print_out(robot_name + " moving to paused")
        if not robot_change_dir(robot_name, "paused"):
            print_err("moving " + robot_name + " to paused")
            return False
        return 0

    order_info = order_dic["order_info"]

    if not order_save_order_file(robot_dir, order_id, order_dic):
        return False

    print_out(robot_name + " " + order_id + " " + order_info["status_string"])

    maximum_per_hour = roboauto_options["order_maximum"]

    status_id = order_info["status"]

    if order_is_public(status_id):
        print_err(robot_name + " " + order_id + " checked but was online")
        return 1
    elif order_is_paused(status_id):
        print_out(robot_name + " " + order_id + " " + order_info["order_description"])
        print_out(robot_name + " " + order_id + " moving to paused")
        if not robot_change_dir(robot_name, "paused"):
            print_err("moving " + robot_name + " to paused")
            return False
    elif order_is_waiting_taker_bond(status_id):
        print_out(robot_name + " " + order_id + " is in the process of being taken")
        return 1
    elif order_is_waiting_maker_bond(status_id):
        if robot_this_hour < maximum_per_hour:
            if not bond_order(robot_dic, order_id, False):
                return False
            return 1
        else:
            if not wait_order(robot_dic):
                return False
    elif order_is_expired(status_id):
        if robot_this_hour < maximum_per_hour:
            if not make_order(
                robot_dic, order_id,
                order_dic["order_data"], order_info["satoshis_now"]
            ):
                return False
            return 1
        else:
            if not wait_order(robot_dic):
                return False
    else:
        if not robot_handle_taken(
            robot_name, status_id, order_id, order_info["order_description"]
        ):
            return False

    return 0


def order_is_this_hour(order, current_hour, current_timestamp, coordinator=False):
    order_info = order.get("order_info", False)
    if order_info is False:
        return False
    if coordinator is not False:
        order_coordinator = order_info.get("coordinator", False)
        if order_coordinator is False:
            return False
        if coordinator[:3] != order_coordinator[:3]:
            return False
    order_response_json = order.get("order_response_json", False)
    if order_response_json is False:
        return False
    expires_at = order_response_json.get("expires_at", False)
    if expires_at is False:
        return False
    date_hour = get_hour_offer(
        expires_at, current_timestamp,
        roboauto_state["keep_online_hour_relative"]
    )
    if date_hour is False:
        return False
    if date_hour != current_hour:
        return False

    return True


def single_book_count_active_orders_this_hour(
    current_hour, current_timestamp, coordinator, nicks_waiting
):
    additional_robots = 0

    orders_active = orders_get_directory(roboauto_state["active_home"])
    for order in orders_active:
        order_response_json = order.get("order_response_json", False)
        if order_response_json is not False:
            robot_name = order_response_json.get("maker_nick", False)
            if robot_name is not False:
                if robot_name in nicks_waiting:
                    continue
        if order_is_this_hour(
            order, current_hour,
            current_timestamp,
            coordinator=coordinator
        ):
            additional_robots += 1

    return additional_robots


def list_orders_single_book(
    coordinator, robot_list, nicks_waiting, robot_this_hour, current_timestamp
):
    current_hour = get_current_hour_from_timestamp(current_timestamp)

    book_response_json = get_book_response_json(coordinator, until_true=False)
    if book_response_json is False:
        return robot_this_hour

    nicks = []
    for offer in book_response_json:
        robot_name = offer["maker_nick"]
        nicks.append(robot_name)

    for robot_name in robot_list:
        robot_dic = robot_load_from_name(robot_name)
        if robot_dic is False:
            return False

        if robot_name not in nicks:
            if robot_name not in nicks_waiting:
                try:
                    with filelock.SoftFileLock(robot_get_lock_file(robot_name)):
                        robot_dir = roboauto_state["active_home"] + "/" + robot_name
                        order = order_get_order_dic(robot_dir, error_print=False)
                        if order is not False and order_is_this_hour(
                            order, current_hour, current_timestamp,
                            coordinator=False
                        ):
                            robot_this_hour -= 1
                            if robot_this_hour < 0:
                                print_err("negative robot this hour")
                                robot_this_hour = 0
                        robot_online = robot_check_expired(
                            robot_dic, robot_this_hour
                        )
                        if robot_online is False or robot_online == 0:
                            continue
                        order = order_get_order_dic(robot_dir, error_print=False)
                        if order is not False and order_is_this_hour(
                            order, current_hour, current_timestamp,
                            coordinator=False
                        ):
                            robot_this_hour += robot_online
                except filelock.Timeout:
                    print_err("filelock timeout %d" % roboauto_state["filelock_timeout"])
                    continue
        elif robot_name in nicks_waiting:
            print_err(robot_name + " is waiting and also active")

    return robot_this_hour


def should_remove_from_waiting_queue(
    robot_this_hour, maximum_per_hour, nicks_waiting, current_timestamp
):
    # let old orders expire
    current_minutes = get_current_minutes_from_timestamp(current_timestamp)
    min_minutes = 10
    if \
        current_minutes > min_minutes and \
        robot_this_hour < maximum_per_hour and \
        len(nicks_waiting) > 0:
        return True

    return False


def keep_online():
    roboauto_state["print_date"] = True

    robot_list = robot_list_dir(roboauto_state["active_home"])
    if len(robot_list) < 1:
        print_out("there are no active robots", date=False)
        return True

    print_out("current active robots are:", date=False)
    for robot_name in robot_list:
        print_out(robot_name, date=False)
    print_out("\n", end="", date=False)

    while True:
        # allow to adjust configs while roboauto is running
        if update_roboauto_options(True) is False:
            print_err("reading the config file")

        maximum_per_hour = roboauto_options["order_maximum"]
        maximum_possible_orders = 24 * maximum_per_hour
        if len(robot_list) < 1:
            print_out("there are no active robots")
            return True
        elif len(robot_list) > maximum_possible_orders:
            print_out(
                "there are %d active robot but a maximum of %s can be active" %
                (len(robot_list), maximum_possible_orders)
            )

        current_timestamp = get_current_timestamp()
        current_hour = get_current_hour_from_timestamp(current_timestamp)

        coordinator_robot_list = {}

        robot_this_hour = 0

        nicks_waiting = waiting_queue_get()
        if nicks_waiting is False:
            return False

        for robot_name in robot_list:
            robot_dic = robot_load_from_name(robot_name)
            if robot_dic is False:
                print_err(f"skipping robot {robot_name}")
                continue

            coordinator = robot_dic["coordinator"]
            if coordinator_robot_list.get(coordinator, False) is False:
                coordinator_robot_list.update({coordinator: []})
            coordinator_robot_list[coordinator].append(robot_name)

        for coordinator, _ in coordinator_robot_list.items():
            robot_this_hour += single_book_count_active_orders_this_hour(
                current_hour, current_timestamp, coordinator, nicks_waiting
            )

        for coordinator, coord_robot_list in coordinator_robot_list.items():
            single_book_response = list_orders_single_book(
                coordinator, coord_robot_list, nicks_waiting, robot_this_hour, current_timestamp
            )
            if single_book_response is not False:
                robot_this_hour = single_book_response

        if should_remove_from_waiting_queue(
            robot_this_hour, maximum_per_hour, nicks_waiting, current_timestamp
        ):
            robot_activate = nicks_waiting.pop(0)
            print_out(robot_activate + " removed from waiting queue")
            if file_json_write(roboauto_state["waiting_queue_file"], nicks_waiting) is False:
                print_err("writing waiting queue")
                return False

        sleeping_periods = int(
            roboauto_options["book_interval"] / roboauto_state["sleep_interval"]
        )
        for _ in range(sleeping_periods):
            old_robot_set = set(robot_list)
            robot_list = robot_list_dir(roboauto_state["active_home"])
            new_robot_set = set(robot_list)
            if new_robot_set != old_robot_set:
                robots_removed = old_robot_set - new_robot_set
                for robot_removed in robots_removed:
                    print_out(f"{robot_removed} removed from active directory")
                robots_added = new_robot_set - old_robot_set
                for robot_added in robots_added:
                    print_out(f"{robot_added} added to active directory")
                break

            time.sleep(roboauto_state["sleep_interval"])

    return True
