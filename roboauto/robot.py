#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string
# pylint: disable=R0911 too-many-return-statements
# pylint: disable=R0912 too-many-branches
# pylint: disable=R0914 too-many-locals
# pylint: disable=R1705 no-else-return
# pylint: disable=W0511 fixme

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


def robot_input_ask(argv):
    multi_false = False, False
    if len(argv) >= 1:
        robot = argv[0]
        argv = argv[1:]
    else:
        robot = input_ask_robot()
        if robot is False:
            return multi_false
    if robot == "":
        print_err("robot name not set")
        return multi_false

    return robot, argv


def robot_input_ask_and_dir(argv):
    multi_false = False, False, False

    robot, argv = robot_input_ask(argv)
    if robot is False:
        return multi_false

    robot_dir = robot_dir_search(robot)
    if robot_dir is False:
        return multi_false

    return robot, argv, robot_dir


def get_destination_mode(argv):
    multi_false = False, False

    destination_mode = "active"

    if len(argv) >= 1:
        destination_arg = argv[0]
        if destination_arg == "--inactive":
            destination_mode = "inactive"
            argv = argv[1:]
        elif destination_arg == "--paused":
            destination_mode = "paused"
            argv = argv[1:]
        elif re.match('^-', destination_arg) is not None:
            print_err("option %s not recognized" % destination_arg)
            return multi_false

    return destination_mode, argv


def get_robot_dir_from_destination(robot, destination_mode):
    if destination_mode == "active":
        robot_dir = roboauto_state["active_home"] + "/" + robot
    elif destination_mode == "inactive":
        robot_dir = roboauto_state["inactive_home"] + "/" + robot
    elif destination_mode == "paused":
        robot_dir = roboauto_state["paused_home"] + "/" + robot
    else:
        robot_dir = False

    return robot_dir


def robot_dir_search(robot, error_print=True):
    robot_dir = roboauto_state["active_home"] + "/" + robot
    if not os.path.isdir(robot_dir):
        robot_dir = roboauto_state["paused_home"] + "/" + robot
        if not os.path.isdir(robot_dir):
            robot_dir = roboauto_state["inactive_home"] + "/" + robot
            if not os.path.isdir(robot_dir):
                if error_print:
                    print_err("robot " + robot + " not found")
                return False

    return robot_dir


def robot_write_token_coordinator(robot_dir, token, coordinator):
    if os.makedirs(robot_dir) is not None:
        print_err("creating directory")
        return False

    if roboauto_options["federation"].get(coordinator, False) is False:
        print_err("coordinator %s does not exists" % coordinator)
        return False

    if file_write(robot_dir + "/token", token) is False:
        return False

    if file_write(robot_dir + "/coordinator", coordinator) is False:
        return False

    return True


def robot_import(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    destination_mode, argv = get_destination_mode(argv)
    if destination_mode is False:
        return False

    robot, argv = robot_input_ask(argv)
    if robot is False:
        return False

    robot_dir = get_robot_dir_from_destination(robot, destination_mode)

    if os.path.exists(robot_dir):
        if not os.path.isdir(robot_dir):
            print_err("%s exists and is not a directory" % robot_dir)
        else:
            print_err("robot %s already exists" % robot_dir)
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

    return robot_write_token_coordinator(robot_dir, token, coordinator)


def robot_remove_from_dir(directory, robot, directory_name):
    if os.path.exists(directory):
        try:
            shutil.rmtree(directory)
        except OSError:
            return False
        print_out("%s removed from %s directory" % (robot, directory_name))
        return 1
    else:
        return 0


def robot_remove(argv):
    robot, argv = robot_input_ask(argv)
    if robot is False:
        return False

    robot_exists = False

    robot_active = roboauto_state["active_home"] + "/" + robot
    remove_active = robot_remove_from_dir(robot_active, robot, "active")
    if remove_active is False:
        return False
    elif remove_active == 1:
        robot_exists = True

    robot_inactive = roboauto_state["inactive_home"] + "/" + robot
    remove_inactive = robot_remove_from_dir(robot_inactive, robot, "inactive")
    if remove_inactive is False:
        return False
    elif remove_inactive == 1:
        robot_exists = True

    robot_paused = roboauto_state["paused_home"] + "/" + robot
    remove_paused = robot_remove_from_dir(robot_paused, robot, "paused")
    if remove_paused is False:
        return False
    elif remove_paused == 1:
        robot_exists = True

    if not robot_exists:
        print_err("robot %s does not exists" % robot)
        return False

    return True


def robot_get_token_base91(robot, robot_dir):
    if not os.path.isdir(robot_dir):
        print_err(robot + " does not exists")
        return False

    token_string = file_read(robot_dir + "/token")
    if token_string is False:
        print_err(robot + " does not have the token")
        return False

    return token_get_base91(token_string)


def robot_get_coordinator(robot, robot_dir, warning_print=True):
    if not os.path.isdir(robot_dir):
        if warning_print:
            print_war(robot + " does not exists, using default coordinator")
        return roboauto_first_coordinator()

    coordinator = file_read(robot_dir + "/coordinator", error_print=False)
    if coordinator is False:
        if warning_print:
            print_war(robot + " does not have a coordinator, using default")
        return roboauto_first_coordinator()

    return coordinator


def robot_print_token(argv):
    use_base91 = False
    if len(argv) >= 1:
        if argv[0] == "--base91":
            use_base91 = True
            argv = argv[1:]

    robot, argv, robot_dir = robot_input_ask_and_dir(argv)
    if robot is False:
        return False

    if use_base91 is False:
        token_string = file_read(robot_dir + "/token")
        if token_string is False:
            print_err(robot + " does not have the token")
            return False
    else:
        token_string = robot_get_token_base91(robot, robot_dir)
        if token_string is False:
            return False

    print_out(token_string)

    return True


def robot_print_coordinator(argv):
    robot, argv = robot_input_ask(argv)
    if robot is False:
        return False

    robot_dir = robot_dir_search(robot)
    if robot_dir is False:
        return False

    coordinator = robot_get_coordinator(robot, robot_dir)
    if robot_dir is False:
        return False

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


def get_waiting_queue():
    if os.path.isfile(roboauto_state["waiting_queue_file"]):
        nicks_waiting = file_json_read(roboauto_state["waiting_queue_file"])
        if nicks_waiting is False:
            print_err("reading waiting queue")
            return False
    else:
        nicks_waiting = []

    return nicks_waiting


def waiting_queue_print():
    nicks_waiting = get_waiting_queue()
    if nicks_waiting is False:
        return False

    for nick in nicks_waiting:
        print_out("%s" % nick)

    return True


def robot_set_dir(destination_dir, argv):
    robot, argv = robot_input_ask(argv)
    if robot is False:
        return False

    if destination_dir not in (
        roboauto_state["active_home"],
        roboauto_state["inactive_home"],
        roboauto_state["paused_home"]
    ):
        print_err("%s is not an available destination directory" % destination_dir)
        return False

    if robot != "--all":
        if destination_dir == roboauto_state["active_home"]:
            first_dir = roboauto_state["paused_home"] + "/" + robot
            second_dir = roboauto_state["inactive_home"] + "/" + robot
        elif destination_dir == roboauto_state["inactive_home"]:
            first_dir = roboauto_state["active_home"] + "/" + robot
            second_dir = roboauto_state["paused_home"] + "/" + robot
        elif destination_dir == roboauto_state["paused_home"]:
            first_dir = roboauto_state["active_home"] + "/" + robot
            second_dir = roboauto_state["inactive_home"] + "/" + robot

        robot_dir = first_dir
        if not os.path.isdir(robot_dir):
            robot_dir = second_dir
            if not os.path.isdir(robot_dir):
                print_err(
                    "%s and %s are not directories" %
                    (first_dir, second_dir)
                )
                return False

        try:
            shutil.move(robot_dir, destination_dir)
        except OSError:
            print_err(
                "moving %s to %s" %
                (robot_dir, destination_dir)
            )
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
                print_err("moving %s to %s" % (robot_dir, destination_dir))
                return False

    return True


def robot_get_data(robot, robot_dir):
    multi_false = False, False, False

    if robot_dir is False:
        return multi_false

    token_base91 = robot_get_token_base91(robot, robot_dir)
    if token_base91 is False:
        print_err("getting token base91 for " + robot)
        return multi_false

    coordinator = robot_get_coordinator(robot, robot_dir)
    coordinator_url = roboauto_get_coordinator_url(coordinator)

    return token_base91, coordinator, coordinator_url


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


def robot_get_lock_file(robot):
    return roboauto_state["lock_home"] + "/" + robot


def robot_generate(argv):
    coordinator, coordinator_url, argv = roboauto_get_coordinator_from_argv(argv)
    if coordinator_url is False:
        return False

    destination_mode, argv = get_destination_mode(argv)
    if destination_mode is False:
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

    robot = generate_response_json.get("nickname", False)
    if robot is False:
        print_err(generate_response_json, error=False, date=False)
        print_err("getting robot name")
        return False

    robot_dir = get_robot_dir_from_destination(robot, destination_mode)

    if os.path.exists(robot_dir):
        if not os.path.isdir(robot_dir):
            print_err("%s exists and is not a directory" % robot_dir)
        else:
            print_err("robot %s already exists" % robot_dir)
        return False

    print_out(robot)

    if robot_write_token_coordinator(robot_dir, token, coordinator) is False:
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
