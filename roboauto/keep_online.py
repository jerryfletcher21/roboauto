#!/usr/bin/env python3

"""keep_online.py"""

# pylint: disable=C0116 missing-function-docstring

import time

import filelock

from roboauto.logger import print_out, print_err, logger_flush
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.robot import \
    robot_list_dir, robot_load_from_name, waiting_queue_get, \
    robot_change_dir, robot_get_dir_dic, robot_wait, \
    robot_unwait, robot_check_and_claim_reward, \
    robot_requests_get_order_id
from roboauto.chat import robot_requests_chat, robot_send_chat_message
from roboauto.order_data import  \
    order_is_public, order_is_paused, order_is_finished, \
    order_is_pending, order_is_waiting_maker_bond, get_order_string, \
    order_is_waiting_taker_bond, order_is_expired, \
    order_is_finished_for_seller, order_is_waiting_seller_buyer, \
    order_is_waiting_seller, order_is_waiting_buyer, \
    order_is_failed_routing, get_order_expiry_reason_string, \
    order_expired_is_not_taken, order_expired_is_maker_bond_not_locked
from roboauto.order_local import \
    robot_handle_taken, order_dic_from_robot_dir, \
    order_robot_get_last_order_id, order_save_order_file, \
    order_is_this_hour_and_online, robot_have_make_data, \
    robot_order_get_local_make_data
from roboauto.order import \
    order_requests_order_dic, bond_order, make_order, \
    peer_nick_from_response, order_read_initial_message_from_file, \
    order_remove_initial_message_file
from roboauto.order_action import \
    order_seller_bond_escrow, order_buyer_update_invoice
from roboauto.date_utils import \
    get_current_timestamp, get_current_minutes_from_timestamp, \
    timestamp_from_date_string, date_convert_time_zone_and_format_string
from roboauto.utils import \
    update_roboauto_options, lock_file_name_get, \
    shuffle_dic, file_is_executable, arg_key_value_number, \
    bad_request_is_cancelled, bad_request_is_wrong_robot


def robot_active_should_save_order_to_file(order_dic, old_order_dic):
    if old_order_dic is False or old_order_dic is None:
        return True

    # do not save when is waiting taken bond because it will change expires_at
    # and the robot will not appear to be online
    if \
        order_dic["order_info"]["status"] != old_order_dic["order_info"]["status"] and \
        not order_is_waiting_taker_bond(order_dic["order_info"]["status"]):
        return True

    return False


def robot_pending_should_save_order_to_file(order_dic, old_order_dic, robot_dic, order_id):
    robot_name = robot_dic["name"]
    robot_coordinator = robot_dic["coordinator"]

    return_status = False

    if old_order_dic is False or old_order_dic is None:
        return_status = True
        old_status_string = "?"
    else:
        old_status_string = get_order_string(old_order_dic["order_info"]["status"])

        if order_dic["order_info"]["status"] != old_order_dic["order_info"]["status"]:
            return_status = True

    status_id = order_dic["order_info"]["status"]
    if return_status is True:
        print_out(
            f"{robot_name} {robot_coordinator} {order_id} changed from "
            f"{old_status_string} to {get_order_string(status_id)}"
        )

    for attribute in (
        "pending_cancel", "asked_for_cancel",
        "statement_submitted", "chat_last_index"
    ):
        try:
            if old_order_dic is False or old_order_dic is None:
                old_attribute = None
                old_attribute_set = False
            else:
                old_attribute = old_order_dic["order_response_json"][attribute]
                old_attribute_set = True
        except KeyError:
            old_attribute = None
            old_attribute_set = False

        try:
            new_attribute = order_dic["order_response_json"][attribute]
            new_attribute_set = True
        except KeyError:
            new_attribute = None
            new_attribute_set = False

        if old_attribute_set == new_attribute_set and old_attribute == new_attribute:
            continue

        if attribute == "chat_last_index" and new_attribute_set is False:
            continue

        return_status = True
        if old_attribute not in (None, False, 0) or new_attribute not in (None, False, 0):
            print_out(
                f"{robot_name} {robot_coordinator} {order_id} changed {attribute} from "
                f"{str(old_attribute)} to {str(new_attribute)}"
            )
        if attribute == "chat_last_index":
            _, _, _ = robot_requests_chat(robot_dic)

    return return_status


def robot_handle_active_expired(robot_dic, all_dic, make_data, expiry_reason=None):
    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]

    if expiry_reason is not None and expiry_reason is not False:
        if \
            not order_expired_is_not_taken(expiry_reason) and \
            not order_expired_is_maker_bond_not_locked(expiry_reason):
            expiry_string = get_order_expiry_reason_string(expiry_reason)
            print_out(f"{robot_name} was active and now is {expiry_string}")

            earned_rewards = robot_check_and_claim_reward(robot_dic)
            if earned_rewards is False:
                return False
            elif earned_rewards > 0:
                # while there are rewards to be claimed it is not moving from active
                return True
            print_out(f"{robot_name} unusual expiry, moving to paused")
            return robot_change_dir(robot_name, "paused")

    if count_active_orders_this_hour(all_dic) < roboauto_options["order_maximum"]:
        if make_data is None or make_data is False:
            make_data = robot_order_get_local_make_data(robot_dir)
            if make_data is None or make_data is False:
                print_out(
                    f"{robot_name} does not have orders and make data, " +
                    "moving to paused"
                )
                return robot_change_dir(robot_name, "paused")
            print_out(f"{robot_name} creating order from make data")

        # will return None when maxium robot orders is reached,
        # it is ok to return True since the robot is checked correctly
        if make_order(
            robot_dic,
            make_data,
            check_change=True
        ) is False:
            return False
    else:
        if not robot_wait(robot_name):
            return False

    return True


def robot_handle_active(robot_dic, all_dic):
    """handle an active robot"""

    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]
    robot_coordinator = robot_dic["coordinator"]

    # handle robot with make data
    if robot_have_make_data(robot_dir):
        return robot_handle_active_expired(robot_dic, all_dic, None)

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
        print_out(f"{robot_name} {order_id} active is cancelled, moving to inactive")
        return robot_change_dir(robot_name, "inactive")
    elif isinstance(order_dic, str):
        return False

    order_info = order_dic["order_info"]

    status_id = order_info["status"]

    if robot_active_should_save_order_to_file(order_dic, old_order_dic):
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
            not order_is_expired(status_id):
            if robot_unwait(nicks_waiting, robot_name) is False:
                return False
            print_out(f"{robot_name} removed from waiting queue because it is taken")
            if not robot_handle_taken(
                robot_name, status_id, order_id, order_info["order_description"]
            ):
                return False
    elif order_is_waiting_taker_bond(status_id):
        status_string = order_info["status_string"]

        print_out(
            f"{robot_name} {robot_coordinator} {order_id} {status_string}",
            level=roboauto_options["log_level_waiting_for_taker_bond"]
        )

        print_out(
            robot_name + " " + order_id + " is in the process of being taken",
            level=roboauto_options["log_level_waiting_for_taker_bond"]
        )
    else:
        if order_is_public(status_id):
            return True

        order_response_json = order_dic["order_response_json"]

        is_seller = order_response_json.get("is_seller", False)

        status_string = order_info["status_string"]
        print_out(f"{robot_name} {robot_coordinator} {order_id} {status_string}")

        if order_is_paused(status_id):
            print_out(robot_name + " " + order_id + " " + order_info["order_description"])
            print_out(robot_name + " " + order_id + " moving to paused")
            if not robot_change_dir(robot_name, "paused"):
                print_err("moving " + robot_name + " to paused")
                return False
        elif order_is_waiting_maker_bond(status_id):
            if count_active_orders_this_hour(all_dic) < roboauto_options["order_maximum"]:
                if bond_order(robot_dic, order_id) is False:
                    return False
            else:
                if not robot_wait(robot_name):
                    return False
        elif order_is_expired(status_id):
            return robot_handle_active_expired(
                robot_dic, all_dic, order_dic["order_data"],
                expiry_reason=order_response_json.get("expiry_reason", None)
            )
        elif \
            order_is_finished(status_id) or \
            (is_seller and order_is_finished_for_seller(status_id)):
            earned_rewards = robot_check_and_claim_reward(robot_dic)
            if earned_rewards is False:
                return False
            elif earned_rewards > 0:
                # while there are rewards to be claimed it is not moving from active
                return True
            print_out(f"{robot_name} {order_id} active is completed, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
        else:
            if not robot_handle_taken(
                robot_name, status_id, order_id, order_info["order_description"]
            ):
                return False

    return True


def count_active_orders_this_hour(all_dic):
    robot_this_hour = 0

    for robot_name, robot_info in all_dic.items():
        robot_state = robot_info["state"]
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


def pending_robot_should_act(expires_timestamp, duration, reference):
    remaining_seconds = expires_timestamp - get_current_timestamp()
    if remaining_seconds < 0:
        return False

    if reference > 0:
        if remaining_seconds < reference:
            return True
    elif reference < 0:
        if remaining_seconds < duration + reference:
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
        print_out(f"{robot_name} {order_id} pending is cancelled, moving to inactive")
        return robot_change_dir(robot_name, "inactive")
    elif isinstance(order_dic, str):
        return False

    order_response_json = order_dic["order_response_json"]
    order_info = order_dic["order_info"]

    status_id = order_info["status"]

    is_seller = order_response_json.get("is_seller", False)

    if robot_pending_should_save_order_to_file(order_dic, old_order_dic, robot_dic, order_id):
        if not order_save_order_file(robot_dir, order_id, order_dic):
            return False

    if \
        order_is_pending(status_id) and \
        not (is_seller and order_is_finished_for_seller(status_id)):
        if not is_seller and order_is_failed_routing(status_id):
            if "trade_satoshis" in order_response_json:
                print_out(
                    f"{robot_name} {order_id} old invoice failed, sending a new one"
                )
                return order_buyer_update_invoice(robot_dic, (None, None))
            else:
                order_description = order_info["order_description"]
                peer_nick = peer_nick_from_response(order_response_json)
                print_out(f"{robot_name} {peer_nick} {order_id} {order_description}")
                if "failure_reason" in order_response_json:
                    failure_reason = order_response_json["failure_reason"]
                    print_out(f"{robot_name} {peer_nick} {order_id} {failure_reason}")
                return True

        expires_at = order_response_json.get("expires_at", False)
        if expires_at is False:
            print_err("no expires_at")
            return False

        expires_timestamp = timestamp_from_date_string(expires_at)

        if \
            order_is_waiting_seller_buyer(status_id) or \
            order_is_waiting_seller(status_id) or \
            order_is_waiting_buyer(status_id):
            escrow_duration = order_response_json.get("escrow_duration", False)
            if escrow_duration is False:
                print_err("no escrow_duration")
                return False

            if pending_robot_should_act(
                expires_timestamp,
                int(escrow_duration),
                roboauto_options["seconds_pending_order"]
            ):
                date_short_expire = date_convert_time_zone_and_format_string(expires_at)
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
                        return order_buyer_update_invoice(robot_dic, (None, None))
        else:
            initial_message = order_read_initial_message_from_file(robot_dir)
            if initial_message is None:
                return True
            elif initial_message is False:
                print_err(f"{robot_name} {order_id} reading initial message")
                order_remove_initial_message_file(robot_dir)
                return False

            total_secs_exp = order_response_json.get("total_secs_exp", False)
            if total_secs_exp is False:
                print_err("no total_secs_exp")
                return False

            timing = initial_message.get("timing", False)
            if timing is False:
                print_err(f"{robot_name} {order_id} initial message does not have timing")
                order_remove_initial_message_file(robot_dir)
                return False
            message = initial_message.get("message", False)
            if message is False:
                print_err(f"{robot_name} {order_id} initial message does not have message")
                order_remove_initial_message_file(robot_dir)
                return False

            if pending_robot_should_act(expires_timestamp, int(total_secs_exp), timing):
                date_short_expire = date_convert_time_zone_and_format_string(expires_at)
                print_out(
                    f"{robot_name} {order_id} "
                    f"expires at {date_short_expire}, sending initial message"
                )
                if robot_send_chat_message(robot_dic, message) is False:
                    print_err(f"{robot_name} {order_id} sending message")
                    order_remove_initial_message_file(robot_dir)
                    return False

                if order_remove_initial_message_file(robot_dir) is False:
                    return False
    else:
        status_string = order_info["status_string"]
        print_out(f"{robot_name} {robot_coordinator} {order_id} {status_string}")

        earned_rewards = robot_check_and_claim_reward(robot_dic)
        if earned_rewards is False:
            return False
        elif earned_rewards > 0:
            # while there are rewards to be claimed it is not moving from pending
            return True

        expiry_reason = order_response_json.get("expiry_reason", -1)

        if \
            order_is_finished(status_id) or \
            (is_seller and order_is_finished_for_seller(status_id)):
            print_out(f"{robot_name} {order_id} is completed, moving to inactive")
            return robot_change_dir(robot_name, "inactive")
        elif order_is_public(status_id) or order_is_waiting_taker_bond(status_id):
            print_out(
                f"{robot_name} {order_id} was pending and now is " +
                f"{get_order_string(status_id)}, moving to active"
            )
            return robot_change_dir(robot_name, "active")
        elif order_is_expired(status_id):
            if order_expired_is_not_taken(expiry_reason):
                print_out(
                    f"{robot_name} {order_id} was pending and now is expired not taken, " +
                    "moving to active"
                )
                return robot_change_dir(robot_name, "active")
            else:
                expiry_string = get_order_expiry_reason_string(expiry_reason)
                print_out(
                    f"{robot_name} {order_id} was pending and now is {expiry_string}, " +
                    "moving to paused"
                )
                return robot_change_dir(robot_name, "paused")
        else:
            print_err(f"{robot_name} strange state, moving to paused")
            return robot_change_dir(robot_name, "paused")

    return True


def robot_check_last_checked(robot_dic, seconds_not_checked):
    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]
    robot_coordinator = robot_dic["coordinator"]

    order_dic = order_dic_from_robot_dir(
        robot_dir, error_print=False
    )
    if order_dic is False or order_dic is None:
        return False

    order_data = order_dic.get("order_data", False)
    if order_data is False:
        return False
    escrow_duration = order_data.get("escrow_duration", False)
    if not isinstance(escrow_duration, int):
        return False

    if seconds_not_checked > int(escrow_duration / 2):
        minutes_not_chcked = int(seconds_not_checked / 60)
        minutes_escrow = int (escrow_duration / 60)
        print_out(
            f"{robot_name} {robot_coordinator} was not successfully checked " +
            f"for {minutes_not_chcked} minutes, " +
            f"escrow duration {minutes_escrow} minutes"
        )

    return True


def robot_dic_update(all_dic):
    """return number of added and failed robots"""

    active_set = robot_list_dir(robot_get_dir_dic()["active"], get_set=True)
    pending_set = robot_list_dir(robot_get_dir_dic()["pending"], get_set=True)

    added_robots = 0
    failed_robots = 0

    for robot_name, robot_info in list(all_dic.items()):
        robot_state = robot_info["state"]
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
                    all_dic[robot_name]["state"] = "pending"
                else:
                    all_dic.pop(robot_name)
                    print_out(f"{robot_name} removed from active directory")
        elif robot_state == "pending":
            if robot_name not in pending_set:
                if robot_name in active_set:
                    print_out(f"{robot_name} moved from pending to active")
                    all_dic[robot_name]["state"] = "active"
                else:
                    all_dic.pop(robot_name)
                    print_out(f"{robot_name} removed from pending directory")

    for robot_active in active_set:
        if robot_active not in all_dic:
            print_out(f"{robot_active} added to active directory")

            if count_active_orders_this_hour(all_dic) >= roboauto_options["order_maximum"]:
                robot_wait(robot_active)

            all_dic[robot_active] = {
                "state": "active",
                "last_checked": int(time.time())
            }

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

            all_dic[robot_pending] = {
                "state": "pending",
                "last_checked": int(time.time())
            }

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

    all_starting_time = time.time()

    for active_robot in active_list:
        ordered_all_dic[active_robot] = {
            "state": "active",
            "last_checked": int(all_starting_time)
        }

    for pending_robot in pending_list:
        ordered_all_dic[pending_robot] = {
            "state": "pending",
            "last_checked": int(all_starting_time)
        }

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

        for robot_name, robot_info in list(all_dic.items()):
            if robot_name not in all_dic:
                total_robots -= 1
                continue
            robot_state = robot_info["state"]

            starting_time = time.time()

            robot_dic = robot_load_from_name(robot_name)
            if robot_dic is False:
                print_err(f"{robot_name} skipping {robot_state} robot")
                failed_numbers += 1
                continue

            if robot_state == "active":
                if robot_handle_active(robot_dic, all_dic) is False:
                    failed_numbers += 1
                    robot_check_last_checked(
                        robot_dic, int(starting_time) - robot_info["last_checked"]
                    )
                else:
                    all_dic[robot_name]["last_checked"] = int(starting_time)
            elif robot_state == "pending":
                if robot_handle_pending(robot_dic) is False:
                    failed_numbers += 1
                    robot_check_last_checked(
                        robot_dic, int(starting_time) - robot_info["last_checked"]
                    )
                else:
                    all_dic[robot_name]["last_checked"] = int(starting_time)

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
        if failed_numbers < total_robots / 2:
            print_out(
                f"{total_robots} robots checked in {all_elapsed_time} seconds " +
                f"{failed_numbers} failed",
                level=1
            )
        else:
            print_out(
                f"{total_robots} robots checked in {all_elapsed_time} seconds " +
                f"{failed_numbers} failed, connection may be instable",
                level=0
            )
        logger_flush()


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
        else:
            arg_verbosity = arg_key_value_number("verbosity", current_arg)
            if arg_verbosity is False:
                return False
            elif arg_verbosity is not None:
                roboauto_state["log_level"] = arg_verbosity
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
