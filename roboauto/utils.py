#!/usr/bin/env python3

"""utils.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

import os
import re
import datetime
import getpass
import json
import subprocess
import configparser
import secrets
import hashlib
import struct

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_options, roboauto_state


def roboauto_first_coordinator():
    return next(iter(roboauto_options["federation"]))


# if this is called with robot_dic["coordinator"] do not check for False
# already checked when creating the robot_dic in robot_get_dic
def roboauto_get_coordinator_url(coordinator):
    url = roboauto_options["federation"].get(coordinator, False)
    if url is False:
        print_err(f"coordinator {coordinator} not valid")
        return False

    return url


def roboauto_get_coordinator_from_url(coordinator_url):
    for coordinator in roboauto_options["federation"]:
        if roboauto_options["federation"][coordinator] == coordinator_url:
            return coordinator

    return "---"


def get_coordinator_from_param(param):
    multi_false = False, False

    coordinator_option = param[2:]
    if len(coordinator_option) < 3:
        print_err(
            "coordinator name should be at least 3 characters long: "
            f"{coordinator_option} invalid"
        )
        return multi_false
    coordinator_found = False
    for name in roboauto_options["federation"]:
        if name[:3] == coordinator_option[:3]:
            coordinator = name
            coordinator_found = True
            break
    if coordinator_found is False:
        print_err(f"coordinator {coordinator_option} not present")
        return multi_false

    return coordinator, roboauto_options["federation"][coordinator]


def roboauto_get_coordinator_from_argv(argv):
    """get a single coordinator from argv"""
    multi_false = False, False, False
    coordinator = False

    if len(argv) < 1:
        print_err("insert coordinator")
        return multi_false

    first_param = argv[0]
    argv = argv[1:]

    if re.match('^--', first_param) is None:
        print_err("insert coordinator")
        return multi_false

    coordinator, coordinator_url = get_coordinator_from_param(first_param)
    if coordinator is False:
        return multi_false

    return coordinator, coordinator_url, argv


def roboauto_get_multi_coordinators_from_argv(argv):
    """get multiple coordinators from argv, with also --all"""
    multi_false = False, False
    coordinators = []

    if len(argv) < 1:
        print_err("insert coordinators")
        return multi_false

    if argv[0] == "--all":
        return roboauto_options["federation"].keys(), argv[1:]

    while len(argv) > 0:
        first_param = argv[0]

        if re.match('^--', first_param) is None:
            break

        argv = argv[1:]

        coordinator, _ = get_coordinator_from_param(first_param)
        if coordinator is False:
            return multi_false

        coordinators.append(coordinator)

    if len(coordinators) < 1:
        print_err("insert coordinators")
        return multi_false

    return coordinators, argv


def dir_make_sure_exists(directory):
    if not os.path.exists(directory):
        if os.makedirs(directory) is not None:
            print_err("creating " + directory)
            return False
    elif not os.path.isdir(directory):
        print_err(directory + " is not a directory")
        return False

    return True


def update_single_option(name, new_option, print_info=False):
    if roboauto_options[name] != new_option:
        old_option = roboauto_options[name]
        roboauto_options[name] = new_option
        if print_info:
            print_out(
                "option %s changed from %s to %s" %
                (name, str(old_option), str(new_option))
            )


def update_federation_option(name, new_option, print_info=False):
    # pylint: disable=R0912 too-many-branches

    if len(name) < 3:
        print_err("coordinators name should be longer than 3 letters %s not valid" % name)
        return False
    for key in roboauto_options["federation"]:
        if name != key and name[:3] == key[:3]:
            print_err("coordinator name %s not valid, similar to %s" % (name, key))
            return False

    # pylint: disable=R1703 simplifiable-if-statement
    if new_option in ("false", "False", "FALSE", "none", "None", "NONE"):
        new_option_is_none = True
    else:
        new_option_is_none = False

    old_option = roboauto_options["federation"].get(name, False)
    if old_option is False:
        if new_option_is_none is False:
            roboauto_options["federation"].update({name: new_option})
            if print_info:
                print_out("new coordinator %s added with url %s" % (name, new_option))
    elif old_option != new_option:
        if new_option_is_none is True:
            del roboauto_options["federation"][name]
            if print_info:
                print_out(
                    "coordinator %s deactivated old url %s" %
                    (name, str(old_option))
                )
        else:
            roboauto_options["federation"][name] = new_option
            if print_info:
                print_out(
                    "coordinator %s changed from %s to %s" %
                    (name, str(old_option), str(new_option))
                )

    return True


def update_roboauto_options(print_info=False):
    if os.path.isfile(roboauto_state["config_file"]):
        parser = configparser.RawConfigParser()
        parser.read(roboauto_state["config_file"])

        general_section = "general"

        if parser.has_section(general_section):
            for option in (
                "user_agent",
                "default_duration", "default_escrow",
                "default_bond_size", "date_format"
            ):
                if parser.has_option(general_section, option):
                    new_option = parser.get(general_section, option).strip("'\"")
                    update_single_option(option, new_option, print_info=print_info)

            for option in (
                "book_interval", "pending_interval", "pay_interval", "error_interval",
                "time_zone", "tab_size", "order_maximum"
            ):
                if parser.has_option(general_section, option):
                    try:
                        new_option = parser.getint(general_section, option)
                    except (ValueError, TypeError):
                        print_err("reading %s" % option)
                        return False
                    update_single_option(option, new_option, print_info=print_info)

        federation_section = "federation"

        if parser.has_section(federation_section):
            for key in parser.options(federation_section):
                value = parser.get(federation_section, key).strip("'\"")
                if update_federation_option(key, value, print_info=print_info) is False:
                    return False

    return True


def global_setup():
    data_home = os.getenv("XDG_DATA_HOME")
    if data_home is None:
        local_home = os.getenv("XDG_LOCAL_HOME")
        if local_home is None:
            local_home = os.getenv("HOME") + "/.local"
        data_home = local_home + "/share"

    config_home = os.getenv("XDG_CONFIG_HOME")
    if config_home is None:
        config_home = os.getenv("HOME") + "/.config"

    roboauto_home = data_home + "/roboauto"
    roboauto_config = config_home + "/roboauto"

    roboauto_state["active_home"] = roboauto_home + "/active"
    roboauto_state["pending_home"] = roboauto_home + "/pending"
    roboauto_state["inactive_home"] = roboauto_home + "/inactive"
    roboauto_state["paused_home"] = roboauto_home + "/paused"
    roboauto_state["lock_home"] = roboauto_home + "/lock"
    roboauto_state["gnupg_home"] = roboauto_home + "/gnupg"

    roboauto_state["waiting_queue_file"] = roboauto_home + "/waiting-queue"
    roboauto_state["log_file"] = roboauto_home + "/roboauto.log"

    roboauto_state["config_file"] = roboauto_config + "/config.ini"
    roboauto_state["message_notification_command"] = roboauto_config + "/message-notification"
    roboauto_state["lightning_node_command"] = roboauto_config + "/lightning-node"

    for directory in (
        roboauto_home, roboauto_config,
        roboauto_state["active_home"],
        roboauto_state["pending_home"],
        roboauto_state["inactive_home"],
        roboauto_state["paused_home"],
        roboauto_state["lock_home"],
        roboauto_state["gnupg_home"]
    ):
        if not dir_make_sure_exists(directory):
            return False

    if not file_is_executable(roboauto_state["lightning_node_command"]):
        print_err(roboauto_state["lightning_node_command"] + " is not an executable script")
        return False

    all_permission = 0o777
    gnupg_home_desired_permission = 0o700
    try:
        gnupg_home_current_permission = \
            os.stat(roboauto_state["gnupg_home"]).st_mode & all_permission
        if gnupg_home_current_permission != gnupg_home_desired_permission:
            os.chmod(roboauto_state["gnupg_home"], gnupg_home_desired_permission)
    except OSError:
        print_err("changing permissions on gnupg home")
        return False

    return True


def global_shutdown():
    if roboauto_state["logger"] is not None:
        roboauto_state["logger"].close()


def get_int(string_number):
    try:
        number = int(string_number)
    except (ValueError, TypeError):
        print_err("%s is not a number" % string_number)
        return False

    return number


def get_uint(string_number):
    number = get_int(string_number)
    if number is False:
        return False

    if number < 0:
        print_err("%s is not positive" % number)
        return False

    return number


def is_float(float_string, additional_check=False):
    try:
        float_float = float(float_string)
        if additional_check == "positive":
            if float_float < 0:
                return False
        elif additional_check == "negative":
            if float_float > 0:
                return False
        elif additional_check == "percentage":
            if float_float < 0 or float_float > 100:
                return False
        return True
    except (ValueError, TypeError):
        return False


def file_is_executable(file_path):
    return os.access(file_path, os.X_OK)


def subprocess_run_command(program, error_print=True):
    try:
        process = subprocess.run(program, capture_output=True, check=False)
    except FileNotFoundError:
        print_err("error: command %s does not exists" % program[0])
        return False
    if process.returncode != 0:
        if error_print:
            print_err(process.stderr.decode(), end="", error=False, date=False)
        return False

    return process.stdout


def json_loads(data):
    try:
        return json.loads(data)
    except json.decoder.JSONDecodeError:
        return False


def json_dumps(data):
    return json.dumps(data, indent=roboauto_options["tab_size"])


def file_write(file_name, string, error_print=True):
    try:
        with open(file_name, "w", encoding="utf8") as file:
            file.write(string + "\n")
    except EnvironmentError:
        if error_print:
            print_err("writing to %s" % file_name)
        return False

    return True


def file_json_write(file_name, data):
    try:
        with open(file_name, "w", encoding="utf8") as file:
            json.dump(data, file, indent=roboauto_options["tab_size"])
    except EnvironmentError:
        print_err("writing json data to %s" % file_name)
        return False

    return True


def file_read(file_name, error_print=True):
    try:
        with open(file_name, "r", encoding="utf8") as file:
            string = file.readline().rstrip()
    except EnvironmentError:
        if error_print:
            print_err("reading from %s" % file_name)
        return False

    return string


def file_json_read(file_name):
    try:
        with open(file_name, "r", encoding="utf8") as file:
            try:
                data = json.load(file)
            except json.decoder.JSONDecodeError:
                return False
    except EnvironmentError:
        print_err("reading json data from %s" % file_name)
        return False

    return data


def input_ask(question):
    try:
        answer = input(question)
    except KeyboardInterrupt:
        print_out("\n", end="", date=False)
        return False

    return answer


def input_ask_robot():
    return input_ask("insert robot name: ")


def password_ask(question):
    try:
        password = getpass.getpass(question)
    except KeyboardInterrupt:
        print_out("\n", end="", date=False)
        return False

    return password


def password_ask_token():
    return password_ask("insert token: ")


def list_configs():
    print_out(json_dumps(roboauto_options))

    return True


def generate_random_token_base62():
    length = 36
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    random_string = ''.join(secrets.choice(characters) for _ in range(length))
    return random_string


def token_get_double_sha256(token_string):
    return hashlib.sha256(
        hashlib.sha256(
            token_string.encode("utf-8")
        ).hexdigest().encode("utf-8")
    ).hexdigest()

    # return hashlib.sha256(
    #     hashlib.sha256(
    #         token_string.encode("utf-8")
    #     ).digest()
    # ).hexdigest()


# from python base91 package
def base91_encode(bindata):
    """encode a bytearray to a base91 string"""
    base91_alphabet = [
        'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
        'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
        'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
        'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
        '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '!', '#', '$',
        '%', '&', '(', ')', '*', '+', ',', '.', '/', ':', ';', '<', '=',
        '>', '?', '@', '[', ']', '^', '_', '`', '{', '|', '}', '~', '"'
   ]

    b = 0
    n = 0
    out = ""
    for count in range(len(bindata)):
        byte = bindata[count:count + 1]
        b |= struct.unpack("B", byte)[0] << n
        n += 8
        if n > 13:
            v = b & 8191
            if v > 88:
                b >>= 13
                n -= 13
            else:
                v = b & 16383
                b >>= 14
                n -= 14
            out += base91_alphabet[v % 91] + base91_alphabet[v // 91]
    if n:
        out += base91_alphabet[b % 91]
        if n > 7 or b > 90:
            out += base91_alphabet[b // 91]

    return out


def token_get_base91(token_string):
    return base91_encode(hashlib.sha256(token_string.encode("utf-8")).digest())


def get_date_short(date_unformat):
    try:
        date_short = date_unformat.split("T")[1].split(".")[0]
    except IndexError:
        date_short = "???"

    return date_short


def directory_get_last_number_file(dir_number, error_print=True):
    list_number = []
    for file_number in os.listdir(dir_number):
        order_number = get_int(file_number)
        if order_number is not False:
            list_number.append(order_number)
    if len(list_number) < 1:
        return 0
    file_number = dir_number + "/" + str(sorted(list_number)[-1])
    if not os.path.isfile(file_number):
        if error_print:
            print_err("%s is not a file" % file_number)
        return False

    return file_number


def string_from_multiline_format(string):
    if string is False or string is None:
        return string

    return string.replace("\\", "\n")


def string_to_multiline_format(string):
    if string is False or string is None:
        return string

    return string.replace("\n", "\\")


def date_to_format(date_string):
    return datetime.datetime.strptime(
        date_string, roboauto_state["robot_date_format"]
    ).strftime(roboauto_options["date_format"])
