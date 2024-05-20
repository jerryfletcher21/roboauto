#!/usr/bin/env python3

"""keep_online.py"""

# pylint: disable=C0116 missing-function-docstring

import re
import time

import filelock

from roboauto.logger import print_out, print_err, logger_flush
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import \
    robot_list_dir, robot_load_from_name, waiting_queue_get, \
    robot_change_dir, robot_get_dir_dic, robot_wait, \
    robot_unwait, robot_check_and_claim_reward, \
    robot_requests_get_order_id
from roboauto.order_data import  \
    order_is_public, order_is_paused, order_is_finished, \
    order_is_pending, order_is_waiting_maker_bond, \
    order_is_waiting_taker_bond, order_is_expired, \
    order_is_finished_for_seller, order_is_waiting_seller_buyer, \
    order_is_waiting_seller, order_is_waiting_buyer, \
    order_is_failed_routing
from roboauto.order_local import \
    robot_handle_taken, order_dic_from_robot_dir, \
    order_robot_get_last_order_id, order_save_order_file
from roboauto.order import \
    order_requests_order_dic, bond_order, make_order
from roboauto.order_action import \
    order_seller_bond_escrow, order_buyer_update_invoice
from roboauto.book import get_hour_offer
from roboauto.date_utils import \
    get_current_timestamp, get_current_hour_from_timestamp, \
    get_current_minutes_from_timestamp, timestamp_from_date_string, \
    date_convert_time_zone_and_format_string
from roboauto.utils import \
    update_roboauto_options, lock_file_name_get, \
    get_uint, random_interval, \
    bad_request_is_cancelled, bad_request_is_wrong_robot


def robot_handle_single_active(robot_dic, robot_this_hour):
    """return 1 if the robot after the function is online,
    0 if not, false if something went wrong"""

    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]

    order_id = order_robot_get_last_order_id(robot_dic, error_print=False)
    if order_id is False or order_id is None:
        print_err(f"{robot_name} active does not have orders saved, making request")
        order_id = robot_requests_get_order_id(robot_dic)
        if order_id is False or order_id is None:
            return False

    # order_id may be false
    # save to file just when order is not public below
    order_dic = order_requests_order_dic(
        robot_dic, order_id, save_to_file=False,
        until_true=False, timeout=roboauto_options["orders_timeout"]
    )
    if order_dic is False:
        return False
    elif bad_request_is_wrong_robot(order_dic):
        print_out(f"{robot_name} {order_id} wrong robot, moving to paused")
        return robot_change_dir(robot_name, "paused")
    elif bad_request_is_cancelled(order_dic):
        earned_rewards = robot_check_and_claim_reward(robot_dic)
        if earned_rewards is False:
            return False
        elif earned_rewards > 0:
            return 0
        else:
            print_out(f"{robot_name} {order_id} active is cancelled, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
    elif isinstance(order_dic, str):
        return False

    order_info = order_dic["order_info"]

    status_id = order_info["status"]

    if order_is_public(status_id):
        return 1

    status_string = order_info["status_string"]
    print_out(f"{robot_name} {order_id} {status_string}")

    if not order_save_order_file(robot_dir, order_id, order_dic):
        return False

    if order_is_paused(status_id):
        print_out(robot_name + " " + order_id + " " + order_info["order_description"])
        print_out(robot_name + " " + order_id + " moving to paused")
        if not robot_change_dir(robot_name, "paused"):
            print_err("moving " + robot_name + " to paused")
            return False
    elif order_is_waiting_taker_bond(status_id):
        print_out(robot_name + " " + order_id + " is in the process of being taken")
        return 1
    elif order_is_waiting_maker_bond(status_id):
        if robot_this_hour < roboauto_options["order_maximum"]:
            if bond_order(robot_dic, order_id) is False:
                return False
            return 1
        else:
            if not robot_wait(robot_name):
                return False
    elif order_is_expired(status_id):
        if robot_this_hour < roboauto_options["order_maximum"]:
            if make_order(
                robot_dic, order_id,
                order_dic["order_data"],
                check_change=True
            ) is False:
                return False
            return 1
        else:
            if not robot_wait(robot_name):
                return False
    else:
        if not robot_handle_taken(
            robot_name, status_id, order_id, order_info["order_description"]
        ):
            return False

    return 0


def order_is_this_hour(order, current_timestamp, coordinator=False):
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
    if date_hour != get_current_hour_from_timestamp(current_timestamp):
        return False

    return True


def count_active_orders_this_hour(
    current_timestamp, nicks_waiting, robot_list_dic
):
    robot_this_hour = 0

    for robot_name in robot_list_dic:
        if robot_name in nicks_waiting:
            continue

        order_dic = order_dic_from_robot_dir(
            roboauto_state["active_home"] + "/" + robot_name,
            order_id=None, error_print=False
        )
        if order_dic is False or order_dic is None:
            continue

        if order_is_this_hour(
            order_dic,
            current_timestamp
        ):
            robot_this_hour += 1

    return robot_this_hour


def robot_handle_active(robot_dic, current_timestamp, robot_this_hour):
    robot_name = robot_dic["name"]
    robot_dir = roboauto_state["active_home"] + "/" + robot_name

    order_dic = order_dic_from_robot_dir(robot_dir, order_id=None, error_print=False)
    if order_dic is not False and order_dic is not None and order_is_this_hour(
        order_dic, current_timestamp,
        coordinator=False
    ):
        robot_this_hour -= 1
        if robot_this_hour < 0:
            print_err("negative robot this hour")
            robot_this_hour = 0

    robot_online = robot_handle_single_active(
        robot_dic, robot_this_hour
    )
    if robot_online is False or robot_online == 0:
        return robot_this_hour

    order_dic = order_dic_from_robot_dir(robot_dir, order_id=None, error_print=False)
    if order_dic is not False and order_dic is not None and order_is_this_hour(
        order_dic, current_timestamp,
        coordinator=False
    ):
        robot_this_hour += robot_online

    return robot_this_hour


def should_remove_from_waiting_queue(
    robot_this_hour, nicks_waiting, current_timestamp
):
    # let old orders expire
    current_minutes = get_current_minutes_from_timestamp(current_timestamp)
    min_minutes = roboauto_state["waiting_queue_remove_after"]
    if \
        current_minutes > min_minutes and \
        robot_this_hour < roboauto_options["order_maximum"] and \
        len(nicks_waiting) > 0:
        return True

    return False


def pending_robot_should_act(expires_timestamp, escrow_duration):
    remaining_seconds = expires_timestamp - get_current_timestamp()
    if remaining_seconds < 0:
        return False

    seconds_pending_order = roboauto_options["seconds_pending_order"]
    if seconds_pending_order > 0:
        if remaining_seconds < seconds_pending_order:
            return True
    elif seconds_pending_order < 0:
        if remaining_seconds < escrow_duration + seconds_pending_order:
            return True

    return False


def robot_handle_pending(robot_dic):
    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]

    order_id = order_robot_get_last_order_id(robot_dic, error_print=False)
    if order_id is False or order_id is None:
        print_err(f"{robot_name} pending does not have orders saved, making request")
        order_id = robot_requests_get_order_id(robot_dic)
        if order_id is False or order_id is None:
            return False

    # order_id can be false
    # save to file just when order is not pending below
    order_dic = order_requests_order_dic(
        robot_dic, order_id, save_to_file=False,
        until_true=False, timeout=roboauto_options["orders_timeout"]
    )
    if order_dic is False:
        return False
    elif bad_request_is_wrong_robot(order_dic):
        print_out(f"{robot_name} {order_id} wrong robot, moving to paused")
        return robot_change_dir(robot_name, "paused")
    elif bad_request_is_cancelled(order_dic):
        earned_rewards = robot_check_and_claim_reward(robot_dic)
        if earned_rewards is False:
            return False
        elif earned_rewards > 0:
            return True
        else:
            print_out(f"{robot_name} {order_id} pending is cancelled, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
    elif isinstance(order_dic, str):
        return False

    order_response_json = order_dic["order_response_json"]
    order_info = order_dic["order_info"]

    status_id = order_info["status"]

    is_seller = order_response_json.get("is_seller", False)

    if \
        order_is_pending(status_id) and \
        not (is_seller and order_is_finished_for_seller(status_id)):
        if not is_seller and order_is_failed_routing(status_id):
            print_out(
                f"{robot_name} {order_id} old invoice failed, sending a new one"
            )
            return order_buyer_update_invoice(robot_dic, None)

        expires_at = order_response_json.get("expires_at", False)
        if expires_at is False:
            print_err("no expires_at")
            return False

        escrow_duration = order_response_json.get("escrow_duration", False)
        if escrow_duration is False:
            print_err("no escrow_duration")
            return False

        if pending_robot_should_act(
            timestamp_from_date_string(expires_at),
            int(escrow_duration)
        ):
            date_short_expire = date_convert_time_zone_and_format_string(
                expires_at, output_format="%H:%M:%S"
            )
            if is_seller:
                if \
                    order_is_waiting_seller_buyer(status_id) or \
                    order_is_waiting_seller(status_id):
                    print_out(
                        f"{robot_name} {order_id} "
                        f"expires at {date_short_expire}, paying escrow"
                    )
                    return order_seller_bond_escrow(robot_dic)
            else:
                if \
                    order_is_waiting_seller_buyer(status_id) or \
                    order_is_waiting_buyer(status_id):
                    print_out(
                        f"{robot_name} {order_id} "
                        f"expires at {date_short_expire}, sending invoice"
                    )
                    return order_buyer_update_invoice(robot_dic, None)
    else:
        status_string = order_info["status_string"]
        print_out(f"{robot_name} {order_id} {status_string}")

        if not order_save_order_file(robot_dir, order_id, order_dic):
            return False

        earned_rewards = robot_check_and_claim_reward(robot_dic)
        if earned_rewards is False:
            return False
        elif earned_rewards > 0:
            # while there are rewards to be claimed it is not moving from pending
            return True

        if \
            order_is_finished(status_id) or \
            (is_seller and order_is_finished_for_seller(status_id)):
            print_out(f"{robot_name} {order_id} is completed, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
        elif order_is_public(status_id):
            print_out(
                f"{robot_name} {order_id} was pending and now is public, moving to active"
            )
            return robot_change_dir(robot_name, "active")
        else:
            print_err(f"{robot_name} strange state, moving to paused")
            return robot_change_dir(robot_name, "paused")

    return True


def should_check_robot_by_time(last_time, current_time, modulo_time, max_time):
    if modulo_time > last_time % max_time:
        correct_modulo_time = modulo_time
    else:
        correct_modulo_time = modulo_time + max_time

    if \
        last_time % max_time + \
        (current_time - last_time) > \
        correct_modulo_time:
        return True

    return False


def robot_active_dic_update(active_dic, robot_this_hour):
    active_set = robot_list_dir(robot_get_dir_dic()["active"], get_set=True)

    robots_removed = [
        robot_name for robot_name in active_dic if robot_name not in active_set
    ]
    for robot_name in robots_removed:
        active_dic.pop(robot_name)
        print_out(f"{robot_name} removed from active directory")

    robots_added = [
        robot_name for robot_name in active_set if robot_name not in active_dic
    ]
    for robot_name in robots_added:
        active_dic[robot_name] = random_interval(
            roboauto_options["active_interval"]
        )
        print_out(f"{robot_name} added to active directory")
        if robot_this_hour >= roboauto_options["order_maximum"]:
            robot_wait(robot_name)
        else:
            robot_this_hour += 1

    return robot_this_hour


def robot_pending_dic_update(pending_dic):
    pending_set = robot_list_dir(robot_get_dir_dic()["pending"], get_set=True)

    robots_removed = [
        robot_name for robot_name in pending_dic if robot_name not in pending_set
    ]
    for robot_name in robots_removed:
        pending_dic.pop(robot_name)
        print_out(f"{robot_name} removed from pending directory")

    robots_added = [
        robot_name for robot_name in pending_set if robot_name not in pending_dic
    ]
    for robot_name in robots_added:
        pending_dic[robot_name] = random_interval(
            roboauto_options["pending_interval"]
        )
        print_out(f"{robot_name} added to pending directory")

    return True


# active_dic is the set of current active robots
# with an associated time % roboauto_options["active_interval"]
# pending_dic is the set of current pending robots
# with an associated time % roboauto_options["pending_interval"]
# this way robots are not checked all together,
# but every one is checked at a different time
def keep_online_no_lock():
    active_list = robot_list_dir(roboauto_state["active_home"])
    pending_list = robot_list_dir(roboauto_state["pending_home"])

    if len(active_list) < 1 and len(pending_list) < 1:
        print_out("there are no active or pending robots", date=False)
        return True

    if len(active_list) >= 1:
        print_out("current active robots are:", date=False)
        for robot_name in active_list:
            print_out(robot_name, date=False)
    else:
        print_out("there are currently no active robots", date=False)
    print_out("\n", end="", date=False)

    if len(pending_list) >= 1:
        print_out("current pending robots are:", date=False)
        for robot_name in pending_list:
            print_out(robot_name, date=False)
    else:
        print_out("there are currently no pending robots", date=False)
    print_out("\n", end="", date=False)

    active_dic = {}
    for active_robot in active_list:
        active_dic[active_robot] = random_interval(
            roboauto_options["active_interval"]
        )

    pending_dic = {}
    for pending_robot in pending_list:
        pending_dic[pending_robot] = random_interval(
            roboauto_options["pending_interval"]
        )

    current_time = 0

    logger_flush()

    while True:
        last_time = current_time
        current_time = time.time()
        if current_time < last_time:
            print_err("current time is less than last time")
            return False

        current_timestamp = get_current_timestamp()

        robot_this_hour = 0

        if len(active_dic) > 0:
            nicks_waiting = waiting_queue_get()

            robot_this_hour = count_active_orders_this_hour(
                current_timestamp, nicks_waiting, active_dic
            )

            for robot_name, robot_time in active_dic.items():
                if robot_name not in nicks_waiting and should_check_robot_by_time(
                    last_time, current_time, robot_time,
                    roboauto_options["active_interval"]
                ):
                    robot_dic = robot_load_from_name(robot_name)
                    if robot_dic is False:
                        print_err(f"{robot_name} skipping active robot")
                        continue

                    robot_this_hour = robot_handle_active(
                        robot_dic, current_timestamp, robot_this_hour
                    )

            if should_remove_from_waiting_queue(
                robot_this_hour, nicks_waiting, current_timestamp
            ):
                if robot_unwait():
                    robot_this_hour += 1

        if len(pending_dic) > 0:
            for robot_name, robot_time in pending_dic.items():
                if should_check_robot_by_time(
                    last_time, current_time, robot_time,
                    roboauto_options["pending_interval"]
                ):
                    robot_dic = robot_load_from_name(robot_name)
                    if robot_dic is False:
                        print_err(f"{robot_name} skipping pending robot")
                        continue

                    robot_handle_pending(robot_dic)

        robot_this_hour = robot_active_dic_update(active_dic, robot_this_hour)
        robot_pending_dic_update(pending_dic)

        # allow to adjust configs while roboauto is running
        if update_roboauto_options(True) is False:
            print_err("reading the config file")

        if len(active_dic) < 1 and len(pending_dic) < 1:
            print_out("there are no active or pending robots", date=False)
            return True

        logger_flush()

        time.sleep(roboauto_state["sleep_interval"])

    return True


def keep_online(argv):
    if len(argv) >= 1:
        first_arg = argv[0]
        argv = argv[1:]

        if re.match('^--verbosity', first_arg) is None:
            print_err(f"option {first_arg} not recognied", date=False, error=False)
            return False

        key_value = first_arg.split("=", 1)
        if len(key_value) != 2:
            print_err("verbosity is not --verbosity=number", date=False, error=False)
            return False
        verbosity_string, verbosity_number_string = key_value

        if verbosity_string != "verbosity":
            print_err(f"key {verbosity_string} not recognied", date=False, error=False)
            return False

        verbosity_number = get_uint(verbosity_number_string)
        if verbosity_number is False:
            return False

        roboauto_state["log_level"] = verbosity_number

    try:
        with filelock.FileLock(
            lock_file_name_get("keep-online"),
            timeout=0
        ):
            return keep_online_no_lock()
    except filelock.Timeout:
        print_err("keep online is already running", date=False, error=False)

    return False
