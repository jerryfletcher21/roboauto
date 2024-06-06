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
    get_uint, shuffle_dic, file_is_executable, \
    bad_request_is_cancelled, bad_request_is_wrong_robot


def robot_handle_active(robot_dic, all_dic):
    """handle an active robot"""

    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]
    robot_coordinator = robot_dic["coordinator"]

    order_id = order_robot_get_last_order_id(robot_dic, error_print=False)
    if order_id is False or order_id is None:
        print_out(f"{robot_name} active does not have orders saved, making request")
        order_id = robot_requests_get_order_id(robot_dic, error_print_not_found_level=2)
        if order_id is False or order_id is None:
            return False

    old_order_dic = order_dic_from_robot_dir(robot_dir, order_id, error_print=False)

    # save to file just when status id is different from previous
    order_dic = order_requests_order_dic(
        robot_dic, order_id, save_to_file=False,
        until_true=False, error_print_not_found_level=2,
        timeout=roboauto_options["orders_timeout"]
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
            print_out(f"{robot_name} {order_id} active is cancelled, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
    elif isinstance(order_dic, str):
        return False

    order_info = order_dic["order_info"]

    status_id = order_info["status"]

    # do not save when is waiting taken bond because it will change expires_at
    # and the robot will not appear to be online
    if \
        old_order_dic is False or old_order_dic is None or (
            status_id != old_order_dic["order_info"]["status"] and
            not order_is_waiting_taker_bond(status_id)
        ):
        if not order_save_order_file(robot_dir, order_id, order_dic):
            return False

    nicks_waiting = waiting_queue_get()
    if robot_name in nicks_waiting:
        if order_is_public(status_id):
            if robot_unwait(nicks_waiting, robot_name) is False:
                return False
            print_out(f"{robot_name} removed from waiting queue because it is active")
        if \
            not order_is_waiting_maker_bond(status_id) and \
            not order_is_public(status_id) and \
            not order_is_paused(status_id) and \
            not order_is_waiting_taker_bond(status_id) and \
            not order_is_waiting_maker_bond(status_id) and \
            not order_is_expired(status_id):
            if robot_unwait(nicks_waiting, robot_name) is False:
                return False
            print_out(f"{robot_name} removed from waiting queue because it is taken")
            if not robot_handle_taken(
                robot_name, status_id, order_id, order_info["order_description"]
            ):
                return False
    else:
        if order_is_public(status_id):
            return True

        status_string = order_info["status_string"]
        print_out(f"{robot_name} {robot_coordinator} {order_id} {status_string}")

        if order_is_paused(status_id):
            print_out(robot_name + " " + order_id + " " + order_info["order_description"])
            print_out(robot_name + " " + order_id + " moving to paused")
            if not robot_change_dir(robot_name, "paused"):
                print_err("moving " + robot_name + " to paused")
                return False
        elif order_is_waiting_taker_bond(status_id):
            print_out(robot_name + " " + order_id + " is in the process of being taken")
        elif order_is_waiting_maker_bond(status_id):
            if count_active_orders_this_hour(all_dic) < roboauto_options["order_maximum"]:
                if bond_order(robot_dic, order_id) is False:
                    return False
            else:
                if not robot_wait(robot_name):
                    return False
        elif order_is_expired(status_id):
            if count_active_orders_this_hour(all_dic) < roboauto_options["order_maximum"]:
                # will return None when maxium robot orders is reached,
                # it is ok to return True since the robot is checked correctly
                if make_order(
                    robot_dic, order_id,
                    order_dic["order_data"],
                    check_change=True
                ) is False:
                    return False
            else:
                if not robot_wait(robot_name):
                    return False
        else:
            if not robot_handle_taken(
                robot_name, status_id, order_id, order_info["order_description"]
            ):
                return False

    return True


def order_is_this_hour_and_online(order, coordinator=False):
    current_timestamp = get_current_timestamp()

    order_info = order.get("order_info", False)
    if order_info is False:
        return False

    if not isinstance(coordinator, bool):
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

    status_id = order_info.get("status", False)
    if status_id is False:
        return False

    if \
        not order_is_public(status_id) and \
        not order_is_paused(status_id) and \
        not order_is_waiting_taker_bond(status_id):
        return False

    return True


def count_active_orders_this_hour(all_dic):
    robot_this_hour = 0

    for robot_name, robot_state in all_dic.items():
        if robot_state != "active":
            continue

        order_dic = order_dic_from_robot_dir(
            roboauto_state["active_home"] + "/" + robot_name,
            order_id=None, error_print=False
        )
        if order_dic is False or order_dic is None:
            continue

        if order_is_this_hour_and_online(order_dic):
            robot_this_hour += 1

    return robot_this_hour


def should_remove_from_waiting_queue(all_dic):
    current_timestamp = get_current_timestamp()

    # let old orders expire
    current_minutes = get_current_minutes_from_timestamp(current_timestamp)
    min_minutes = roboauto_state["waiting_queue_remove_after"]
    if \
        current_minutes > min_minutes and \
        count_active_orders_this_hour(all_dic) < roboauto_options["order_maximum"] and \
        len(waiting_queue_get()) > 0:
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
    robot_coordinator = robot_dic["coordinator"]

    order_id = order_robot_get_last_order_id(robot_dic, error_print=False)
    if order_id is False or order_id is None:
        print_out(f"{robot_name} pending does not have orders saved, making request")
        order_id = robot_requests_get_order_id(robot_dic, error_print_not_found_level=2)
        if order_id is False or order_id is None:
            return False

    old_order_dic = order_dic_from_robot_dir(robot_dir, order_id, error_print=False)

    # save to file just when status id is different from previous
    order_dic = order_requests_order_dic(
        robot_dic, order_id, save_to_file=False,
        until_true=False, error_print_not_found_level=2,
        timeout=roboauto_options["orders_timeout"]
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
        old_order_dic is False or old_order_dic is None or \
        status_id != old_order_dic["order_info"]["status"]:
        if not order_save_order_file(robot_dir, order_id, order_dic):
            return False

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
                    return order_seller_bond_escrow(robot_dic, True)
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
        print_out(f"{robot_name} {robot_coordinator} {order_id} {status_string}")

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


def robot_dic_update(all_dic):
    """return number of added and failed robots"""

    active_set = robot_list_dir(robot_get_dir_dic()["active"], get_set=True)
    pending_set = robot_list_dir(robot_get_dir_dic()["pending"], get_set=True)

    added_robots = 0
    failed_robots = 0

    for robot_name, robot_state in list(all_dic.items()):
        if robot_state == "active":
            if robot_name not in active_set:
                nicks_waiting = waiting_queue_get()
                if robot_name in nicks_waiting:
                    if robot_unwait(nicks_waiting, robot_name) is not False:
                        print_out(\
                            f"{robot_name} removed from waiting queue " +
                            "because it is no longer active"
                        )
                if robot_name in pending_set:
                    print_out(f"{robot_name} moved from active to pending")
                    all_dic[robot_name] = "pending"
                else:
                    all_dic.pop(robot_name)
                    print_out(f"{robot_name} removed from active directory")
        elif robot_state == "pending":
            if robot_name not in pending_set:
                if robot_name in active_set:
                    print_out(f"{robot_name} moved from pending to active")
                    all_dic[robot_name] = "active"
                else:
                    all_dic.pop(robot_name)
                    print_out(f"{robot_name} removed from pending directory")

    for robot_active in active_set:
        if robot_active not in all_dic:
            print_out(f"{robot_active} added to active directory")

            if count_active_orders_this_hour(all_dic) >= roboauto_options["order_maximum"]:
                robot_wait(robot_active)

            all_dic[robot_active] = "active"

            added_robots += 1

            robot_dic = robot_load_from_name(robot_active)
            if robot_dic is False:
                print_err(f"{robot_active} getting active robot")
                failed_robots += 1
                continue

            if robot_handle_active(robot_dic, all_dic) is False:
                failed_robots += 1

    for robot_pending in pending_set:
        if robot_pending not in all_dic:
            print_out(f"{robot_pending} added to pending directory")

            all_dic[robot_pending] = "pending"

            added_robots += 1

            robot_dic = robot_load_from_name(robot_pending)
            if robot_dic is False:
                print_err(f"{robot_pending} getting pending robot")
                failed_robots +=1
                continue

            if robot_handle_pending(robot_dic) is False:
                failed_robots += 1

    return added_robots, failed_robots


# active_dic is the set of current active robots
# with an associated time % roboauto_options["active_interval"]
# pending_dic is the set of current pending robots
# with an associated time % roboauto_options["pending_interval"]
# this way robots are not checked all together,
# but every one is checked at a different time
def keep_online_no_lock(should_sleep, initial_info):
    active_list = robot_list_dir(roboauto_state["active_home"])
    pending_list = robot_list_dir(roboauto_state["pending_home"])

    if len(active_list) < 1 and len(pending_list) < 1:
        print_out("there are no active or pending robots", date=False)
        return True

    if initial_info:
        if len(active_list) >= 1:
            print_out(f"current {len(active_list)} active robots are:", date=False)
            for robot_name in active_list:
                print_out(robot_name, date=False)
        else:
            print_out("there are currently no active robots", date=False)
        print_out("\n", end="", date=False)

        if len(pending_list) >= 1:
            print_out(f"current {len(pending_list)} pending robots are:", date=False)
            for robot_name in pending_list:
                print_out(robot_name, date=False)
        else:
            print_out("there are currently no pending robots", date=False)
        print_out("\n", end="", date=False)

    ordered_all_dic = {}

    for active_robot in active_list:
        ordered_all_dic[active_robot] = "active"

    for pending_robot in pending_list:
        ordered_all_dic[pending_robot] = "pending"

    all_dic = shuffle_dic(ordered_all_dic)

    robot_check_current = 0

    logger_flush()

    while True:
        all_starting_time = time.time()

        total_robots = len(all_dic)
        if robot_check_current >= total_robots:
            robot_check_current = 0

        if len(all_dic) < 1:
            print_out("there are no active or pending robots", date=False)
            return True

        # every loop make a robot requests to check for rewards
        robot_name = list(all_dic.keys())[robot_check_current]
        robot_dic = robot_load_from_name(robot_name)
        if robot_dic is False:
            print_err(f"{robot_name} skipping request robot")
        else:
            _ = robot_check_and_claim_reward(robot_dic, error_print_not_found_level=2)

        robot_check_current += 1

        failed_numbers = 0

        for robot_name, robot_state in list(all_dic.items()):
            if robot_name not in all_dic:
                total_robots -= 1
                continue

            starting_time = time.time()

            robot_dic = robot_load_from_name(robot_name)
            if robot_dic is False:
                print_err(f"{robot_name} skipping {robot_state} robot")
                failed_numbers += 1
                continue

            if robot_state == "active":
                if robot_handle_active(robot_dic, all_dic) is False:
                    failed_numbers += 1
            elif robot_state == "pending":
                if robot_handle_pending(robot_dic) is False:
                    failed_numbers += 1

            added_robots, additional_failed_robots = robot_dic_update(all_dic)
            total_robots += added_robots
            failed_numbers += additional_failed_robots

            # allow to adjust configs while roboauto is running
            if update_roboauto_options(True) is False:
                print_err("reading the config file")

            if len(all_dic) < 1:
                print_out("there are no active or pending robots", date=False)
                return True

            logger_flush()

            elapsed_time = time.time() - starting_time

            # robosats/api/logics.py user_activity_status
            # 2 minutes Active
            # 10 minutes Seen recently

            if should_sleep is True:
                half_max_time = (120 / len(all_dic)) / 2
                if elapsed_time < half_max_time:
                    time.sleep(half_max_time)

        if should_remove_from_waiting_queue(all_dic):
            robot_unwaited = robot_unwait(waiting_queue_get())
            if robot_unwaited is not False:
                print_out(f"{robot_unwaited} removed from waiting queue")

        all_elapsed_time = int(time.time() - all_starting_time)
        print_out(
            f"{total_robots} robots checked in {all_elapsed_time} seconds " +
            f"{failed_numbers} failed",
            level=1
        )


def keep_online(argv):
    should_sleep = True
    initial_info = True
    while len(argv) >= 1:
        current_arg = argv[0]
        argv = argv[1:]

        if current_arg == "--no-sleep":
            should_sleep = False
        elif current_arg == "--no-initial-info":
            initial_info = False
        elif re.match('^--verbosity', current_arg) is not None:
            key_value = current_arg[2:].split("=", 1)
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
        else:
            print_err(f"option {current_arg} not recognied", date=False, error=False)
            return False

    if not file_is_executable(roboauto_state["lightning_node_command"]):
        print_err("lightning node not set, it is required for keep-online")
        return False

    try:
        with filelock.FileLock(
            lock_file_name_get("keep-online"),
            timeout=0
        ):
            return keep_online_no_lock(should_sleep, initial_info)
    except filelock.Timeout:
        print_err("keep online is already running", date=False, error=False)

    return False
