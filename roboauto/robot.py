#!/usr/bin/env python3

"""robot.py"""

# pylint: disable=C0116 missing-function-docstring

import os
import re
import shutil

from roboauto.logger import print_out, print_err, print_war
from roboauto.requests_api import \
    requests_api_robot, response_is_error, requests_api_stealth, \
    requests_api_robot_generate, requests_api_reward
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.date_utils import date_get_current
from roboauto.utils import \
    file_read, file_write, json_loads, json_dumps, \
    file_json_read, file_json_write, \
    input_ask_robot, password_ask_token, input_ask, \
    generate_random_token_base62, \
    roboauto_first_coordinator, file_is_executable, \
    roboauto_get_coordinator_url, \
    roboauto_get_coordinator_from_argv, \
    token_get_base91, sha256_single, \
    dir_make_sure_exists, \
    string_from_multiline_format, string_to_multiline_format
from roboauto.gpg_key import gpg_generate_robot, gpg_import_key, gpg_sign_message
from roboauto.subprocess_commands import subprocess_generate_invoice


def robot_get_dir_dic():
    return {
        "active": roboauto_state["active_home"],
        "pending": roboauto_state["pending_home"],
        "paused": roboauto_state["paused_home"],
        "inactive": roboauto_state["inactive_home"]
    }


def robot_get_dic(robot_name, robot_state, robot_dir, token, coordinator):
    if robot_get_dir_dic()[robot_state] + "/" + robot_name != robot_dir:
        print_err(f"{robot_name} wrong state and directory")
        return False

    if not os.path.isdir(robot_dir):
        print_err(f"{robot_name} directory not present")
        return False

    if roboauto_get_coordinator_url(coordinator) is False:
        return False

    return {
        "name": robot_name,
        "state": robot_state,
        "dir": robot_dir,
        "token": token,
        "coordinator": coordinator
    }


def robot_var_from_dic(robot_dic):
    return \
        robot_dic["name"], \
        robot_dic["state"], \
        robot_dic["dir"], \
        robot_dic["token"], \
        robot_dic["coordinator"], \
        token_get_base91(robot_dic["token"]), \
        roboauto_get_coordinator_url(robot_dic["coordinator"])


def robot_load_from_name(robot_name, error_print=True):
    possible_state_base_dir = robot_get_dir_dic()
    found = False
    robot_dir = ""
    robot_state = None
    for possible_state, possible_base_dir in possible_state_base_dir.items():
        possible_dir = possible_base_dir + "/" + robot_name
        if os.path.isdir(possible_dir):
            if found is True:
                if error_print:
                    print_err(f"{robot_name} found in two directories")
                return False
            robot_state = possible_state
            robot_dir = possible_dir
            found = True
    if found is False:
        if error_print:
            print_err(f"{robot_name} not found")
        return False

    token_file = robot_dir + "/token"
    if not os.path.isfile(token_file):
        if error_print:
            print_err(f"{robot_name} does not have the token file")
        return False
    token = file_read(token_file, error_print=error_print)
    if token is False:
        if error_print:
            print_err(f"{robot_name} reading the token")
        return False

    coordinator_file = robot_dir + "/coordinator"
    if not os.path.isfile(coordinator_file):
        if error_print:
            print_err(f"{robot_name} does not have a coordinator, using default")
        coordinator = roboauto_first_coordinator()
    else:
        coordinator = file_read(coordinator_file, error_print=error_print)
        if coordinator is False:
            if error_print:
                print_war(f"{robot_name} reading coordinator, using default")
            coordinator = roboauto_first_coordinator()

    return robot_get_dic(robot_name, robot_state, robot_dir, token, coordinator)


def robot_save_to_disk_and_get_dic(robot_name, robot_state, robot_dir, token, coordinator):
    if os.makedirs(robot_dir) is not None:
        print_err("creating directory")
        return False

    if roboauto_options["federation"].get(coordinator, False) is False:
        print_err(f"coordinator {coordinator} does not exists")
        return False

    if file_write(robot_dir + "/token", token) is False:
        return False

    if file_write(robot_dir + "/coordinator", coordinator) is False:
        return False

    return robot_get_dic(robot_name, robot_state, robot_dir, token, coordinator)


def robot_input_from_argv(argv, just_name=False, error_print=True) -> tuple:
    multi_false = False, False
    if len(argv) >= 1:
        robot_name = argv[0]
        argv = argv[1:]
    else:
        robot_name = input_ask_robot()
        if robot_name is False:
            return multi_false
    if robot_name == "":
        print_err("robot name not set")
        return multi_false

    if just_name:
        return robot_name, argv

    robot_dic = robot_load_from_name(robot_name, error_print=error_print)
    if robot_dic is False:
        return multi_false

    return robot_dic, argv


def robot_get_state_from_argv(argv, default_state="active"):
    multi_false = False, False

    robot_state = default_state

    if len(argv) >= 1:
        state_arg = argv[0]
        if state_arg in ("--active", "--pending", "--inactive", "--paused"):
            robot_state = state_arg[2:]
            argv = argv[1:]
        elif re.match('^-', state_arg) is not None:
            print_err(f"option {state_arg} not recognized")
            return multi_false

    return robot_state, argv


def robot_import(argv):
    coordinator, _, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator is False:
        return False

    robot_state, argv = robot_get_state_from_argv(argv)
    if robot_state is False:
        return False

    robot_name, argv = robot_input_from_argv(argv, just_name=True)
    if robot_name is False:
        return False

    robot_dir = robot_get_dir_dic()[robot_state] + "/" + robot_name

    if os.path.exists(robot_dir):
        if not os.path.isdir(robot_dir):
            print_err(f"{robot_dir} exists and is not a directory")
        else:
            print_err(f"robot {robot_name} already exists")
        return False

    if len(argv) >= 1:
        token = argv[0]
        argv = argv[1:]
    else:
        token = password_ask_token()
        if token is False:
            return False
    if token == "":
        print_err("robot token not set")
        return False

    if robot_save_to_disk_and_get_dic(
        robot_name, robot_state, robot_dir, token, coordinator
    ) is False:
        return False

    return True


def robot_print_token(argv):
    use_base91 = False
    if len(argv) >= 1:
        if argv[0] == "--base91":
            use_base91 = True
            argv = argv[1:]

    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    token = robot_dic["token"]

    if use_base91:
        print_out(token_get_base91(token))
    else:
        print_out(token)

    return True


def robot_print_coordinator(argv):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    coordinator = robot_dic["coordinator"]

    coordinator_url = roboauto_get_coordinator_url(coordinator)
    if coordinator_url is False:
        return False

    print_out(coordinator)
    print_out(coordinator_url)

    return True


def robot_list_dir(robot_dir, get_set=False):
    full_path_list = os.listdir(robot_dir)

    if get_set:
        return {full_path.split("/")[-1] for full_path in full_path_list}

    return sorted([full_path.split("/")[-1] for full_path in full_path_list])


def robot_change_dir(robot_name, destination_state, error_is_already=True):
    if destination_state not in robot_get_dir_dic():
        print_err(f"{destination_state} is not an available destination directory")
        return False

    destination_dir = robot_get_dir_dic()[destination_state]

    if robot_name != "--all":
        robot_dic = robot_load_from_name(robot_name)
        if robot_dic is False:
            return False
        robot_state = robot_dic["state"]
        robot_dir = robot_dic["dir"]
        if robot_state == destination_state:
            if error_is_already:
                print_err(f"{robot_name} is already {destination_state}")
                return False
        else:
            try:
                shutil.move(robot_dir, destination_dir)
            except OSError:
                print_err(f"moving {robot_name} to {destination_state}")
                return False
    else:
        if destination_dir == roboauto_state["active_home"]:
            print_err("you can not set all robots active for privacy concerns")
            return False
        for active_robot in os.listdir(roboauto_state["active_home"]):
            robot_dir = roboauto_state["active_home"] + "/" + active_robot
            try:
                shutil.move(robot_dir, destination_dir)
            except OSError:
                print_err(f"moving {robot_name} to {destination_state}")
                return False

    return True


def robot_change_dir_from_argv(destination_dir, argv):
    if len(argv) > 0 and argv[0] == "--all":
        robot_name = argv[0]
        argv = argv[1:]
    else:
        robot_name, argv = robot_input_from_argv(argv, just_name=True)
        if robot_name is False:
            return False

    return robot_change_dir(robot_name, destination_dir)


def robot_requests_robot(
    token_base91, robot_url, robot_dic, error_print_not_found_level=0
):
    """run requests_api_robot, robot_dic can also be None"""

    multi_false = False, False

    if robot_dic is not None:
        robot_name = robot_dic["name"]
        user = robot_dic["name"]
    else:
        robot_name = "robot"
        # base91 have strange characters can not be used
        user = sha256_single(token_base91)

    requests_options = {
        "error_print": error_print_not_found_level
    }
    robot_response_all = requests_api_robot(
        token_base91, robot_url, user,
        options=requests_options
    )
    if response_is_error(robot_response_all):
        print_err(f"{robot_name} not found", level=error_print_not_found_level)
        return multi_false
    robot_response = robot_response_all.text
    robot_response_json = json_loads(robot_response)
    if robot_response_json is False:
        print_err(robot_response, end="", error=False, date=False)
        print_err(f"{robot_name} getting robot response")
        return multi_false

    if "bad_request" in robot_response_json:
        print_err(json_dumps(robot_response_json), error=False, date=False)
        return multi_false

    nickname = robot_response_json.get("nickname", "robot")

    earned_rewards = robot_response_json.get("earned_rewards", 0)
    if earned_rewards is not False and earned_rewards is not None and earned_rewards > 0:
        print_out(f"{nickname} have {earned_rewards} earned rewards")

    if robot_dic is not None:
        robot_dir = robot_dic["dir"]

        if robot_name != nickname:
            print_err(f"{nickname} is not the same as {robot_name}")
            return multi_false

        robot_response_file = robot_dir + "/robot-response"
        if not file_json_write(robot_response_file, robot_response_json):
            return multi_false

        if robot_save_gpg_public_private(robot_dic, robot_response_json) is False:
            return multi_false

    return robot_response, robot_response_json


def robot_requests_get_order_id(
    robot_dic, error_print=True, error_print_not_found_level=0
):
    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    robot_response, robot_response_json = robot_requests_robot(
        token_base91, robot_url, robot_dic,
        error_print_not_found_level=error_print_not_found_level
    )
    if robot_response is False or robot_response_json is False:
        return False

    order_id_number = robot_response_json.get("active_order_id", False)
    if order_id_number is False:
        order_id_number = robot_response_json.get("last_order_id", False)
        if order_id_number is False:
            if error_print:
                print_err(robot_response, error=False, date=False)
                print_err("getting order_id for " + robot_name)
            return False

    order_id = str(order_id_number)

    return order_id


def robot_save_gpg_keys(robot_dir, public_key, private_key, fingerprint, set_default=False):
    gpg_list_dir = robot_dir + "/gpg"
    if dir_make_sure_exists(gpg_list_dir) is False:
        return False

    gpg_dir = gpg_list_dir + "/" + fingerprint
    if not os.path.exists(gpg_dir):
        if dir_make_sure_exists(gpg_dir) is False:
            return False
        if not file_write(gpg_dir + "/public", public_key):
            return False
        if not file_write(gpg_dir + "/private", private_key):
            return False

    if set_default:
        if not file_write(robot_dir + "/current-fingerprint", fingerprint):
            return False

    return True


def robot_get_current_fingerprint(robot_dir, error_print=True):
    fingerprint_dir = robot_dir + "/current-fingerprint"
    if not os.path.isfile(fingerprint_dir):
        if error_print:
            print_err("robot does not have a current fingerprint")
        return False

    return file_read(fingerprint_dir)


def robot_save_peer_gpg_public_key(robot_dir, peer_key, fingerprint, set_default=False):
    gpg_list_dir = robot_dir + "/gpg-peer"
    if dir_make_sure_exists(gpg_list_dir) is False:
        return False

    gpg_dir = gpg_list_dir + "/" + fingerprint
    if not os.path.exists(gpg_dir):
        if dir_make_sure_exists(gpg_dir) is False:
            return False
        if not file_write(gpg_dir + "/public", peer_key):
            return False

    if set_default:
        if not file_write(robot_dir + "/peer-fingerprint", fingerprint):
            return False

    return True


def robot_get_peer_fingerprint(robot_dir, error_print=True):
    fingerprint_dir = robot_dir + "/peer-fingerprint"
    if not os.path.isfile(fingerprint_dir):
        if error_print:
            print_err("robot does not have a peer fingerprint")
        return False

    return file_read(fingerprint_dir)


def robot_save_gpg_public_private(robot_dic, robot_response_json):
    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]
    token = robot_dic["token"]

    public_key = string_from_multiline_format(
        robot_response_json.get("public_key", False)
    )
    if public_key is False:
        print_err(f"{robot_name} getting public key")
        return False

    private_key = string_from_multiline_format(
        robot_response_json.get("encrypted_private_key", False)
    )
    if private_key is False:
        print_err(f"{robot_name} getting private key")
        return False

    fingerprint = gpg_import_key(private_key, token)
    if fingerprint is False:
        return False

    if not robot_save_gpg_keys(
        robot_dir, public_key, private_key, fingerprint, set_default=False
    ):
        return False

    return True


def robot_generate(coordinator, robot_state):
    coordinator_url = roboauto_get_coordinator_url(coordinator)
    if coordinator_url is False:
        return False

    token = generate_random_token_base62()
    token_base91 = token_get_base91(token)

    fingerprint, public_key, private_key = gpg_generate_robot(token)
    if fingerprint is False:
        return False

    generate_response_all = requests_api_robot_generate(
        token_base91,
        string_to_multiline_format(public_key),
        string_to_multiline_format(private_key),
        coordinator_url, coordinator
    )
    if response_is_error(generate_response_all):
        return False
    generate_response = generate_response_all.text
    generate_response_json = json_loads(generate_response)
    if generate_response_json is False:
        print_err(generate_response, end="", error=False, date=False)
        print_err("generate response is not json")
        return False

    robot_name = generate_response_json.get("nickname", False)
    if robot_name is False:
        print_err(generate_response_json, error=False, date=False)
        print_err("getting robot name")
        return False

    robot_dir = robot_get_dir_dic()[robot_state] + "/" + robot_name

    if os.path.exists(robot_dir):
        if not os.path.isdir(robot_dir):
            print_err(f"{robot_dir} exists and is not a directory")
        else:
            print_err("robot {robot_name} already exists")
        return False

    robot_dic = robot_save_to_disk_and_get_dic(
        robot_name, robot_state, robot_dir, token, coordinator
    )
    if robot_dic is False:
        return False

    if not robot_save_gpg_keys(
        robot_dir, public_key, private_key, fingerprint, set_default=True
    ):
        return False

    # could make sure that when False is returned the robot directory
    # is not created

    return robot_dic


def robot_generate_argv(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    robot_state, argv = robot_get_state_from_argv(argv, default_state="paused")
    if robot_state is False:
        return False

    robot_dic = robot_generate(coordinator, robot_state)
    if robot_dic is False:
        return False

    print_out(robot_dic["name"])

    return True


def waiting_queue_get():
    if os.path.isfile(roboauto_state["waiting_queue_file"]):
        nicks_waiting = file_json_read(roboauto_state["waiting_queue_file"])
        if nicks_waiting is False:
            print_err("reading waiting queue")
            return []
    else:
        nicks_waiting = []

    return nicks_waiting


def waiting_queue_print():
    nicks_waiting = waiting_queue_get()

    for nick in nicks_waiting:
        print_out(f"{nick}")

    return True


def robot_wait(robot_name):
    """move robot to waiting queue"""
    nicks_waiting = waiting_queue_get()

    if robot_name in nicks_waiting:
        return True

    nicks_waiting.append(robot_name)
    print_out(robot_name + " added to waiting queue")
    if file_json_write(roboauto_state["waiting_queue_file"], nicks_waiting) is False:
        print_err("writing waiting queue")
        return False

    return False


def robot_unwait(nicks_waiting, robot_name=None):
    """remove robot or first in the list from the waiting queue"""

    if robot_name is not None:
        try:
            nicks_waiting.remove(robot_name)
        except ValueError:
            print_err(f"{robot_name} is not in the waiting queue")
            return False
    else:
        robot_name = nicks_waiting.pop(0)

    if file_json_write(
        roboauto_state["waiting_queue_file"], nicks_waiting
    ) is False:
        print_err("writing waiting queue")
        return False

    return robot_name


def robot_claim_reward(robot_dic, reward_amount, invoice=None):
    robot_name, _, robot_dir, token, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    if invoice is None or invoice is False:
        date_current = date_get_current(
            roboauto_options["date_format"].replace(" ", "-").replace("/", "-").replace(":", "-")
        )

        invoice = subprocess_generate_invoice(
            str(reward_amount),
            "reward-" + robot_name + "-" + date_current
        )
        if invoice is False:
            return False

    fingerprint = robot_get_current_fingerprint(robot_dir)
    if fingerprint is False:
        return False

    signed_invoice = gpg_sign_message(invoice, fingerprint, passphrase=token)
    if signed_invoice is False:
        print_err("signing reward invoice")
        return False

    reward_response_all = requests_api_reward(
        token_base91, robot_url, robot_name, signed_invoice
    )
    if response_is_error(reward_response_all):
        return False
    reward_response = reward_response_all.text
    reward_response_json = json_loads(reward_response)
    if reward_response_json is False:
        print_err(reward_response, end="", error=False, date=False)
        print_err("getting reward response")
        return False

    bad_request = reward_response_json.get("bad_request", False)
    if bad_request is not False:
        print_err(bad_request, date=False, error=False)
        print_err("reward not claimed")
        return False

    successful_withdrawal = reward_response_json.get("successful_withdrawal", False)
    if successful_withdrawal is False:
        bad_invoice = reward_response_json.get("bad_invoice", False)
        if bad_invoice is not False:
            print_err(bad_invoice, error=False, date=False)
        print_err("withdrawing not successful")
        return False

    print_out(f"{robot_name} invoice reward sent successfully")

    return True


def robot_check_and_claim_reward(robot_dic, error_print_not_found_level=0, invoice=None):
    """will return False if something went wrong,
    earned_rewards (which could already be claimed) if there were rewards
    we could make a second robot request to check if the invoice
    sent by robot_claim_reward is already paid, but it is possible that is
    not yet paid, better to wait.
    Since this function is run in keep-online, it will be checked
    again next loop"""

    _, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    robot_response, robot_response_json = robot_requests_robot(
        token_base91, robot_url, robot_dic,
        error_print_not_found_level=error_print_not_found_level
    )
    if robot_response is False or robot_response_json is False:
        return False

    earned_rewards = robot_response_json.get("earned_rewards", 0)
    if earned_rewards is not False and earned_rewards is not None and earned_rewards > 0:
        if not robot_claim_reward(robot_dic, earned_rewards, invoice=invoice):
            return False

    return earned_rewards


def robot_claim_reward_argv(argv):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    invoice = None
    if len(argv) >= 1:
        invoice = argv[0]
        argv = argv[1:]
    if not file_is_executable(roboauto_state["lightning_node_command"]) and invoice is None:
        invoice = input_ask("insert invoice: ")
        if invoice is False:
            return False
    if invoice == "":
        print_err("invoice not set")

    earned_rewards = robot_check_and_claim_reward(robot_dic, invoice=invoice)
    if earned_rewards is False:
        return False
    elif earned_rewards == 0:
        print_err(f"{robot_name} does not have claimable rewards")
        return False

    robot_response, robot_response_json = robot_requests_robot(
        token_base91, robot_url, robot_dic
    )
    if robot_response is False or robot_response_json is False:
        return False

    earned_rewards = robot_response_json.get("earned_rewards", 0)
    if earned_rewards is not False and earned_rewards is not None and earned_rewards > 0:
        print_err("coordinator does not have yet paid the reward invoice")
        return False

    return True


def robot_update_stealth_invoice_option_argv(argv):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    robot_name, _, _, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    if len(argv) < 1:
        print_err("insert stealth invoice option")
        return False
    wants_stealth_input = argv[0]
    argv = argv[1:]

    if wants_stealth_input.lower() == "true":
        wants_stealth_bool = True
    elif wants_stealth_input.lower() == "false":
        wants_stealth_bool = False
    else:
        print_err("stealth invoice option should be true/false")
        return False

    stealth_response_all = requests_api_stealth(
        token_base91, robot_url, robot_name, wants_stealth_bool
    )
    if response_is_error(stealth_response_all):
        return False
    stealth_response = stealth_response_all.text
    stealth_response_json = json_loads(stealth_response)
    if stealth_response_json is False:
        print_err(stealth_response, end="", error=False, date=False)
        print_err("getting stealth response")
        return False

    bad_request = stealth_response_json.get("bad_request", False)
    if bad_request is not False:
        print_err(bad_request, date=False, error=False)
        print_err("changing stealth option")
        return False

    wants_stealth = stealth_response_json.get("wantsStealth", False)
    if wants_stealth is not wants_stealth_bool:
        print_err("stealth option not changed")
        return False

    print_out(f"{robot_name} stealth option changed to {wants_stealth}")

    return True
