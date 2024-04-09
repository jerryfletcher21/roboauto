#!/usr/bin/env python3

"""keep_online.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=R1705 no-else-return

import time
import random

import filelock

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import \
    robot_get_lock_file, robot_list_dir, robot_load_from_name, \
    waiting_queue_get, robot_change_dir, robot_requests_get_order_id, \
    robot_get_dir_dic, robot_var_from_dic, robot_wait, robot_unwait
from roboauto.order_data import  \
    order_is_public, order_is_paused, order_is_finished, order_is_pending, \
    order_is_waiting_maker_bond, order_is_waiting_taker_bond, order_is_expired
from roboauto.order_local import \
    robot_handle_taken, order_get_order_dic
from roboauto.order import \
    order_requests_order_dic, bond_order, make_order
from roboauto.book import \
    get_book_response_json, get_hour_offer, \
    get_current_timestamp, \
    get_current_hour_from_timestamp, get_current_minutes_from_timestamp
from roboauto.utils import update_roboauto_options


def robot_check_expired(robot_dic, robot_this_hour):
    # pylint: disable=R0911 too-many-return-statements
    # pylint: disable=R0912 too-many-branches

    """check what happened to a robot that is no longer active
    return 1 if the robot is back online, 0 if not, false if something wrong"""

    robot_name = robot_dic["name"]

    order_id = robot_requests_get_order_id(robot_dic)
    if order_id is False:
        return False

    order_dic = order_requests_order_dic(robot_dic, order_id)
    if order_dic is None:
        print_out(robot_name + " moving to paused")
        if not robot_change_dir(robot_name, "paused"):
            print_err("moving " + robot_name + " to paused")
            return False
        return 0
    elif order_dic is False:
        return False

    order_info = order_dic["order_info"]

    print_out(robot_name + " " + order_id + " " + order_info["status_string"])

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
        if robot_this_hour < roboauto_options["order_maximum"]:
            if not bond_order(robot_dic, order_id):
                return False
            return 1
        else:
            if not robot_wait(robot_name):
                return False
    elif order_is_expired(status_id):
        if robot_this_hour < roboauto_options["order_maximum"]:
            if not make_order(
                robot_dic, order_id,
                order_dic["order_data"]
            ):
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
    # pylint: disable=R0911 too-many-return-statements

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
    current_timestamp, nicks_waiting, robot_set
):
    robot_this_hour = 0

    for robot_name in robot_set:
        if robot_name in nicks_waiting:
            continue

        order = order_get_order_dic(
            roboauto_state["active_home"] + "/" + robot_name, error_print=False
        )
        if order is False:
            continue

        if order_is_this_hour(
            order,
            current_timestamp
        ):
            robot_this_hour += 1

    return robot_this_hour


def robot_check_expired_handle(robot_dic, current_timestamp, robot_this_hour):
    robot_name = robot_dic["name"]
    robot_dir = roboauto_state["active_home"] + "/" + robot_name
    order = order_get_order_dic(robot_dir, error_print=False)
    if order is not False and order_is_this_hour(
        order, current_timestamp,
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
        return robot_this_hour
    order = order_get_order_dic(robot_dir, error_print=False)
    if order is not False and order_is_this_hour(
        order, current_timestamp,
        coordinator=False
    ):
        robot_this_hour += robot_online

    return robot_this_hour


def list_orders_single_book(
    coordinator, robot_list, nicks_waiting, robot_this_hour, current_timestamp
):
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
            return robot_this_hour

        if robot_name not in nicks:
            if robot_name not in nicks_waiting:
                try:
                    with filelock.SoftFileLock(
                        robot_get_lock_file(robot_name),
                        timeout=roboauto_state["filelock_timeout"]
                    ):
                        robot_check_expired_handle(
                            robot_dic, current_timestamp, robot_this_hour
                        )
                except filelock.Timeout:
                    # pylint: disable=C0209 consider-using-f-string
                    print_err("filelock timeout %d" % roboauto_state["filelock_timeout"])
                    continue
        elif robot_name in nicks_waiting:
            if robot_unwait(robot_name):
                order = order_get_order_dic(
                    roboauto_state["active_home"] + "/" + robot_name, error_print=False
                )
                if order is not False and order_is_this_hour(
                    order, current_timestamp,
                    coordinator=False
                ):
                    robot_this_hour += 1

    return robot_this_hour


def should_remove_from_waiting_queue(
    robot_this_hour, nicks_waiting, current_timestamp
):
    # let old orders expire
    current_minutes = get_current_minutes_from_timestamp(current_timestamp)
    min_minutes = 10
    if \
        current_minutes > min_minutes and \
        robot_this_hour < roboauto_options["order_maximum"] and \
        len(nicks_waiting) > 0:
        return True

    return False


def robot_handle_pending(robot_dic):
    # pylint: disable=R0911 too-many-return-statements

    robot_name, _, robot_dir, _, _, _, _ = robot_var_from_dic(robot_dic)

    old_order_dic = order_get_order_dic(robot_dir, error_print=False)
    if old_order_dic is not False:
        order_id = old_order_dic["order_info"]["order_id"]
    else:
        print_err("robot does not have orders saved, making request")
        order_id = robot_requests_get_order_id(robot_dic)
        if order_id is False:
            return False

    order_dic = order_requests_order_dic(robot_dic, order_id)
    if order_dic is None:
        print_out(robot_name + " moving to inactive")
        return robot_change_dir(robot_name, "inactive")
    elif order_dic is False:
        return False

    order_info = order_dic["order_info"]

    status_id = order_info["status"]

    # add order_is_finished_for_seller: sending satoshi to buyer and payment failed
    if not order_is_pending(status_id):
        status_string = order_info["status_string"]
        print_out(f"{robot_name} {order_id} {status_string}")

        if order_is_finished(status_id):
            print_out(f"{robot_name} {order_id} is completed, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
        elif order_is_public(status_id):
            # check rewards and claim them
            print_out(
                f"{robot_name} was pending and now is public, "
                "moving to active, check rewards"
            )
            return robot_change_dir(robot_name, "active")
        else:
            print_err(f"{robot_name} strange state, moving to inactive")
            return robot_change_dir(robot_name, "inactive")

    return True


def should_check_book(current_time, last_checked):
    if current_time >= last_checked + roboauto_options["book_interval"]:
        return True

    return False


def should_check_robot_pending(last_time, current_time, modulo_time):
    if modulo_time is None:
        return True

    if modulo_time > last_time % roboauto_options["pending_interval"]:
        correct_modulo_time = modulo_time
    else:
        correct_modulo_time = modulo_time + roboauto_options["pending_interval"]

    if \
        last_time % roboauto_options["pending_interval"] + \
        (current_time - last_time) > \
        correct_modulo_time:
        return True

    return False


def robot_active_set_update(old_robot_set, current_timestamp):
    """update robot active_set, may send added robot to the waiting list"""
    new_robot_set = robot_list_dir(robot_get_dir_dic()["active"], get_set=True)

    something_changed = False
    if new_robot_set != old_robot_set:
        robots_removed = old_robot_set - new_robot_set
        if len(robots_removed) > 0:
            for robot_removed in robots_removed:
                print_out(f"{robot_removed} removed from active directory")

        robots_added = new_robot_set - old_robot_set
        if len(robots_added) > 0:
            robot_this_hour = count_active_orders_this_hour(
                current_timestamp, waiting_queue_get(), old_robot_set
            )
            for robot_added in robots_added:
                print_out(f"{robot_added} added to active directory")
                robot_this_hour += 1
                if robot_this_hour > roboauto_options["order_maximum"]:
                    robot_wait(robot_added)

        something_changed = True

    return new_robot_set, something_changed


def robot_pending_dic_update(pending_dic):
    pending_set = robot_list_dir(robot_get_dir_dic()["pending"], get_set=True)

    for robot_name in set(pending_dic.keys()):
        if robot_name not in pending_set:
            pending_dic.pop(robot_name)
            print_out(f"{robot_name} removed from pending directory")

    for robot_name in pending_set:
        if robot_name not in pending_dic:
            pending_dic[robot_name] = None
            print_out(f"{robot_name} added to pending directory")

    return True


# active_set is the set of current active robots
# pending_dic is the set of current pending robots
# with an associated time % roboauto_options["pending_interval"]
# this way pending robots are not checked all together,
# but every one is checked at a different time
def keep_online_no_lock():
    # pylint: disable=R0912 too-many-branches
    # pylint: disable=R0914 too-many-locals
    # pylint: disable=R0915 too-many-statements

    roboauto_state["should_log"] = True

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

    active_set = set(active_list)
    pending_dic = {}
    for pending_robot in pending_list:
        # maybe randomize also here
        pending_dic[pending_robot] = None

    current_time = 0
    book_last_checked = 0

    while True:
        last_time = current_time
        current_time = time.time()
        if current_time < last_time:
            print_err("current time is less than last time")
            return False

        current_timestamp = get_current_timestamp()

        if \
            len(active_set) >= 1 and \
            should_check_book(current_time, book_last_checked):
            book_last_checked = current_time

            coordinator_robot_list = {}

            nicks_waiting = waiting_queue_get()

            for robot_name in active_set:
                robot_dic = robot_load_from_name(robot_name)
                if robot_dic is False:
                    print_err(f"skipping robot {robot_name}")
                    continue

                coordinator = robot_dic["coordinator"]
                if coordinator_robot_list.get(coordinator, False) is False:
                    coordinator_robot_list.update({coordinator: []})
                coordinator_robot_list[coordinator].append(robot_name)

            robot_this_hour = count_active_orders_this_hour(
                current_timestamp, nicks_waiting, active_set
            )

            for coordinator, robot_list in coordinator_robot_list.items():
                single_book_response = list_orders_single_book(
                    coordinator, robot_list, nicks_waiting,
                    robot_this_hour, current_timestamp
                )
                if single_book_response is not False:
                    robot_this_hour = single_book_response

            if should_remove_from_waiting_queue(
                robot_this_hour, nicks_waiting, current_timestamp
            ):
                robot_unwait()

        if len(pending_dic) >= 1:
            for robot_name, robot_time in pending_dic.items():
                if should_check_robot_pending(
                    last_time, current_time, robot_time
                ):
                    robot_dic = robot_load_from_name(robot_name)
                    if robot_dic is False:
                        print_err(f"skipping robot {robot_name}")
                        continue

                    robot_handle_pending(robot_dic)

                    if robot_time is None:
                        pending_dic[robot_name] = \
                            random.randint(1, roboauto_options["pending_interval"]) - 1

        active_set, something_changed_active = robot_active_set_update(
            active_set, current_timestamp
        )
        robot_pending_dic_update(pending_dic)
        if something_changed_active:
            # check next loop
            book_last_checked = 0

        # allow to adjust configs while roboauto is running
        if update_roboauto_options(True) is False:
            print_err("reading the config file")

        if len(active_set) < 1 and len(pending_dic) < 1:
            print_out("there are no active or pending robots", date=False)
            return True

        if roboauto_state["logger"] is not None:
            roboauto_state["logger"].flush()

        time.sleep(roboauto_state["sleep_interval"])

    return True


def keep_online(argv):
    if len(argv) >= 1 and argv[0] == "--quiet":
        roboauto_state["quiet"] = True
        argv = argv[1:]

    try:
        with filelock.SoftFileLock(
            robot_get_lock_file(roboauto_state["lock_home"] + "/" + "keep-online"),
            timeout=0
        ):
            return keep_online_no_lock()
    except filelock.Timeout:
        print_err("keep online is already running")

    return False
