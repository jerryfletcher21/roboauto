#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0914 too-many-locals

import os
import re
import shutil

from roboauto.logger import print_out, print_err, print_war
from roboauto.requests_api import \
    requests_api_robot, response_is_error, requests_api_robot_generate
from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.utils import \
    file_read, file_write, \
    file_json_read, \
    json_loads, \
    input_ask_robot, password_ask_token, \
    generate_random_token_base62, \
    roboauto_first_coordinator, \
    roboauto_get_coordinator_url, \
    roboauto_get_coordinator_from_argv, \
    token_get_base91, \
    dir_make_sure_exists
from roboauto.gpg_key import gpg_generate_robot


def robot_get_dir_dic():
    return {
        "active": roboauto_state["active_home"],
        "pending": roboauto_state["pending_home"],
        "paused": roboauto_state["paused_home"],
        "inactive": roboauto_state["inactive_home"]
    }


def robot_get_dic(robot_name, robot_state, robot_dir, token, coordinator):
    return {
        "name": robot_name,
        "state": robot_state,
        "dir": robot_dir,
        "token": token,
        "coordinator": coordinator
    }


def robot_load_from_name(robot_name, error_print=True):
    possible_state_base_dir = robot_get_dir_dic()
    found = False
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


def robot_save_to_disk(robot):
    robot_dir = robot["dir"]
    if os.makedirs(robot_dir) is not None:
        print_err("creating directory")
        return False

    coordinator = robot["coordinator"]
    if roboauto_options["federation"].get(coordinator, False) is False:
        print_err(f"coordinator {coordinator} does not exists")
        return False

    if file_write(robot_dir + "/token", robot["token"]) is False:
        return False

    if file_write(robot_dir + "/coordinator", coordinator) is False:
        return False

    return True


def robot_input_from_argv(argv, just_name=False, error_print=True):
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

    robot = robot_load_from_name(robot_name, error_print=error_print)
    if robot is False:
        return multi_false

    return robot, argv


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


def robot_get_lock_file(robot):
    return roboauto_state["lock_home"] + "/" + robot


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

    return robot_save_to_disk(robot_get_dic(
        robot_name, robot_state, robot_dir, token, coordinator
    ))


def robot_remove(argv):
    robot, argv = robot_input_from_argv(argv)
    if robot is False:
        return False

    robot_name = robot["name"]
    robot_state = robot["state"]
    robot_dir = robot["dir"]

    if not os.path.exists(robot_dir):
        print_err(f"{robot_name} does not exists")
        return False

    try:
        shutil.rmtree(robot_dir)
    except OSError:
        return False

    print_out(f"{robot_name} removed from {robot_state} directory")

    return True


def robot_print_token(argv):
    use_base91 = False
    if len(argv) >= 1:
        if argv[0] == "--base91":
            use_base91 = True
            argv = argv[1:]

    robot, argv = robot_input_from_argv(argv)
    if robot is False:
        return False

    token = robot["token"]

    if use_base91:
        print_out(token_get_base91(token))
    else:
        print_out(token)

    return True


def robot_print_coordinator(argv):
    robot, argv = robot_input_from_argv(argv)
    if robot is False:
        return False

    coordinator = robot["coordinator"]

    print_out(coordinator)
    print_out(roboauto_get_coordinator_url(coordinator))

    return True


def robot_list_dir(robot_dir):
    full_path_list = os.listdir(robot_dir)
    name_list = [full_path.split("/")[-1] for full_path in full_path_list]

    return sorted(name_list)


def robot_print_dir(robot_dir):
    for robot in robot_list_dir(robot_dir):
        print_out(robot)

    return True


def robot_change_dir(robot_name, destination_state):
    if destination_state not in robot_get_dir_dic():
        print_err(f"{destination_state} is not an available destination directory")
        return False

    destination_dir = robot_get_dir_dic()[destination_state]

    if robot_name != "--all":
        robot = robot_load_from_name(robot_name)
        if robot is False:
            return False
        robot_dir = robot["dir"]
        try:
            shutil.move(robot_dir, destination_dir)
        except OSError:
            print_err("moving {robot_dir} to {destination_dir}")
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
                print_err(f"moving {robot_dir} to {destination_dir}")
                return False

    return True


def robot_change_dir_from_argv(destination_dir, argv):
    if argv[0] == "--all":
        robot_name = argv[0]
        argv = argv[1:]
    else:
        robot_name, argv = robot_input_from_argv(argv, just_name=True)
        if robot_name is False:
            return False

    return robot_change_dir(robot_name, destination_dir)


def robot_requests_robot(token_base91, robot_url):
    multi_false = False, False

    robot_response_all = requests_api_robot(token_base91, robot_url)
    if response_is_error(robot_response_all):
        return multi_false
    robot_response = robot_response_all.text
    robot_response_json = json_loads(robot_response)
    if robot_response_json is False:
        print_err(robot_response, end="", error=False, date=False)
        print_err("getting robot response")
        return multi_false

    return robot_response, robot_response_json


def robot_generate(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    robot_state, argv = robot_get_state_from_argv(argv, default_state="paused")
    if robot_state is False:
        return False

    token = generate_random_token_base62()
    token_base91 = token_get_base91(token)

    fingerprint, public_key, private_key = gpg_generate_robot(token)
    if fingerprint is False:
        return False

    generate_response_all = requests_api_robot_generate(
        token_base91, public_key, private_key,
        coordinator_url,
        until_true=True
    )
    if response_is_error(generate_response_all):
        return False
    generate_response = generate_response_all.text
    generate_response_json = json_loads(generate_response)
    if not generate_response_json:
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

    print_out(robot_name)

    if not robot_save_to_disk(robot_get_dic(
        robot_name, robot_state, robot_dir, token, coordinator
    )):
        return False

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

    if not file_write(robot_dir + "/current-fingerprint", fingerprint):
        return False

    return True


def waiting_queue_get():
    if os.path.isfile(roboauto_state["waiting_queue_file"]):
        nicks_waiting = file_json_read(roboauto_state["waiting_queue_file"])
        if nicks_waiting is False:
            print_err("reading waiting queue")
            return False
    else:
        nicks_waiting = []

    return nicks_waiting


def waiting_queue_print():
    nicks_waiting = waiting_queue_get()
    if nicks_waiting is False:
        return False

    for nick in nicks_waiting:
        print_out(f"{nick}")

    return True
