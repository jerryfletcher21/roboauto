#!/usr/bin/env python3

"""utils.py"""

# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

import os
import re
import getpass
import json
import configparser
import random
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

    coordinator_value = param[2:]
    if len(coordinator_value) < 3:
        print_err(
            "coordinator name should be at least 3 characters long: "
            f"{coordinator_value} invalid"
        )
        return multi_false
    coordinator_found = False
    coordinator = ""
    for name in roboauto_options["federation"]:
        if name[:3] == coordinator_value[:3]:
            coordinator = name
            coordinator_found = True
            break
    if coordinator_found is False:
        print_err(f"coordinator {coordinator_value} not present")
        return multi_false

    return coordinator, roboauto_options["federation"][coordinator]


def roboauto_get_coordinator_from_argv(argv) -> tuple:
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


def roboauto_get_multi_coordinators_from_argv(argv) -> tuple:
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


def string_is_false_none_null(string):
    # pylint: disable=R1703 simplifiable-if-statement
    if string in (
        "false", "False", "FALSE",
        "none", "None", "NONE",
        "null", "Null", "NULL"
    ):
        return True
    else:
        return False


def update_single_option(name, new_value, print_info=False):
    if roboauto_options[name] != new_value:
        old_value = roboauto_options[name]
        roboauto_options[name] = new_value
        if print_info:
            print_out(
                "option %s changed from %s to %s" %
                (name, str(old_value), str(new_value))
            )


def update_federation_option(name, new_value, print_info=False):
    if len(name) < 3:
        print_err("coordinators name should be longer than 3 letters %s not valid" % name)
        return False
    for key in roboauto_options["federation"]:
        if name != key and name[:3] == key[:3]:
            print_err("coordinator name %s not valid, similar to %s" % (name, key))
            return False

    new_value_is_none = string_is_false_none_null(new_value)

    old_value = roboauto_options["federation"].get(name, False)
    if old_value is False:
        if new_value_is_none is False:
            roboauto_options["federation"].update({name: new_value})
            if print_info:
                print_out("new coordinator %s added with url %s" % (name, new_value))
    elif old_value != new_value:
        if new_value_is_none is True:
            del roboauto_options["federation"][name]
            if print_info:
                print_out(
                    "coordinator %s deactivated old url %s" %
                    (name, str(old_value))
                )
        else:
            roboauto_options["federation"][name] = new_value
            if print_info:
                print_out(
                    "coordinator %s changed from %s to %s" %
                    (name, str(old_value), str(new_value))
                )

    return True


def update_roboauto_options(print_info=False):
    # pylint: disable=R1702 too-many-nested-blocks

    if os.path.isfile(roboauto_state["config_file"]):
        parser = configparser.RawConfigParser()
        parser.read(roboauto_state["config_file"])

        general_section = "general"
        federation_section = "federation"

        for section in list(parser):
            if section not in (
                "DEFAULT", general_section, federation_section
            ):
                print_err(f"section {section} not recognized")
                return False

        if parser.has_section(general_section):
            for option in parser.options(general_section):
                if option not in roboauto_options:
                    print_err(f"option {option} not recognied")
                    return False
                elif isinstance(roboauto_options[option], dict):
                    print_err(f"{option} is a section not an option")
                    return False

            for option in (
                "user_agent", "date_format"
            ):
                if parser.has_option(general_section, option):
                    new_value = parser.get(general_section, option).strip("'\"")
                    update_single_option(option, new_value, print_info=print_info)

            option = "create_new_after_maximum_orders"
            if parser.has_option(general_section, option):
                new_value = parser.getboolean(general_section, option)
                update_single_option(option, new_value, print_info=print_info)

            for option in (
                "seconds_pending_order", "order_maximum", "robot_maximum_orders",
                "tab_size", "routing_budget_ppm", "requests_timeout", "orders_timeout",
                "active_interval", "pending_interval", "pay_interval", "error_interval",
                "default_duration", "default_escrow"
            ):
                if parser.has_option(general_section, option):
                    try:
                        new_value = parser.getint(general_section, option)
                    except (ValueError, TypeError):
                        print_err("reading %s" % option)
                        return False

                    if option == "seconds_pending_order":
                        seconds_min_value = 300
                        if \
                            new_value != 0 and \
                            (-1 * seconds_min_value) < new_value < seconds_min_value:
                            print_err(
                                f"{option} if not 0, absolute value can "
                                f"not be less than {seconds_min_value}"
                            )
                            return False
                    elif new_value < 0:
                        print_err(f"{option} can not be negative")
                        return False

                    update_single_option(option, new_value, print_info=print_info)

            for option in (
                "default_bond_size"
            ):
                if parser.has_option(general_section, option):
                    try:
                        new_value = parser.getfloat(general_section, option)
                    except (ValueError, TypeError):
                        print_err("reading %s" % option)
                        return False

                    if new_value < 0:
                        print_err(f"{option} can not be negative")
                        return False

                    update_single_option(option, new_value, print_info=print_info)

        if parser.has_section(federation_section):
            for key in parser.options(federation_section):
                value = parser.get(federation_section, key).strip("'\"")
                if update_federation_option(key, value, print_info=print_info) is False:
                    return False

    return True


def global_setup(config_dir=None, data_dir=None):
    if config_dir is None:
        home = os.getenv("HOME")
        if home is None:
            print_err("HOME not set")
            return False
        config_home = os.getenv("XDG_CONFIG_HOME")
        if config_home is None:
            config_home = home + "/.config"
        roboauto_config = config_home + "/roboauto"
    else:
        roboauto_config = config_dir

    if data_dir is None:
        home = os.getenv("HOME")
        if home is None:
            print_err("HOME not set")
            return False
        data_home = os.getenv("XDG_DATA_HOME")
        if data_home is None:
            local_home = os.getenv("XDG_LOCAL_HOME")
            if local_home is None:
                local_home = home + "/.local"
            data_home = local_home + "/share"
        roboauto_home = data_home + "/roboauto"
    else:
        roboauto_home = data_dir

    roboauto_state["config_home"] = roboauto_config
    roboauto_state["data_home"] = roboauto_home

    roboauto_state["active_home"] = roboauto_home + "/active"
    roboauto_state["pending_home"] = roboauto_home + "/pending"
    roboauto_state["inactive_home"] = roboauto_home + "/inactive"
    roboauto_state["paused_home"] = roboauto_home + "/paused"
    roboauto_state["coordinators_home"] = roboauto_home + "/coordinators"
    roboauto_state["lock_home"] = roboauto_home + "/lock"
    roboauto_state["gnupg_home"] = roboauto_home + "/gnupg"
    roboauto_state["log_home"] = roboauto_home + "/logs"

    roboauto_state["waiting_queue_file"] = roboauto_home + "/waiting-queue"

    roboauto_state["config_file"] = roboauto_config + "/config.ini"
    roboauto_state["message_notification_command"] = roboauto_config + "/message-notification"
    roboauto_state["lightning_node_command"] = roboauto_config + "/lightning-node"

    for directory in (
        roboauto_home, roboauto_config,
        roboauto_state["active_home"],
        roboauto_state["pending_home"],
        roboauto_state["inactive_home"],
        roboauto_state["coordinators_home"],
        roboauto_state["paused_home"],
        roboauto_state["lock_home"],
        roboauto_state["gnupg_home"],
        roboauto_state["log_home"]
    ):
        if not dir_make_sure_exists(directory):
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


def state_set_command_type(command_type):
    roboauto_state["current_command_type"] = command_type


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


def is_float(float_string, additional_check : str | bool = False):
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


def file_json_write(file_name, data, error_print=True):
    try:
        with open(file_name, "w", encoding="utf8") as file:
            json.dump(data, file, indent=roboauto_options["tab_size"])
            file.write("\n")
    except EnvironmentError:
        if error_print:
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


def file_json_read(file_name, error_print=True):
    try:
        with open(file_name, "r", encoding="utf8") as file:
            try:
                data = json.load(file)
            except json.decoder.JSONDecodeError:
                return False
    except EnvironmentError:
        if error_print:
            print_err("reading json data from %s" % file_name)
        return False

    return data


def file_remove(file_name):
    try:
        os.remove(file_name)
    except OSError:
        print_err(f"removing {file_name}")
        return False

    return True


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


def print_config_directory():
    print_out(roboauto_state["config_home"])

    return True


def print_data_directory():
    print_out(roboauto_state["data_home"])

    return True


def list_configs():
    print_out(json_dumps(roboauto_options))

    return True


def generate_random_token_base62():
    length = 36
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    random_string = ''.join(secrets.choice(characters) for _ in range(length))
    return random_string


def sha256_single(string):
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


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


def directory_get_file_numbers(dir_number, error_print=True):
    list_number = []
    for file_number in os.listdir(dir_number):
        order_number = get_int(file_number)
        if order_number is not False:
            list_number.append(order_number)
    if len(list_number) < 1:
        return 0

    file_numbers = sorted(list_number)
    for file_number in file_numbers:
        file_path = dir_number + "/" + str(file_number)
        if not os.path.isfile(file_path):
            if error_print:
                print_err(f"{file_path} is not a file")
            return False

    return file_numbers


def string_from_multiline_format(string):
    if string is False or string is None:
        return string

    return string.replace("\\", "\n")


def string_to_multiline_format(string):
    if string is False or string is None:
        return string

    return string.replace("\n", "\\")


def lock_file_name_get(name):
    return roboauto_state["lock_home"] + "/" + name


def invoice_get_correct_amount(amount, budget_ppm):
    return int(amount * (1 - budget_ppm / 1000000))


def arg_key_value_number(var_name, arg):
    if re.match(f"^--{var_name}", arg) is None:
        return None

    key_value = arg[2:].split("=", 1)
    if len(key_value) != 2:
        print_err(f"{var_name} is not --{var_name}=number")
        return False
    key, value = key_value

    if key != var_name:
        print_err(f"key {key} not recognied")
        return False

    value_number = get_uint(value)
    if value_number is False:
        return False

    return value_number


def invoice_amount_calculate_arg(argv):
    budget_ppm = roboauto_options["routing_budget_ppm"]
    if len(argv) >= 1:
        arg_budget_ppm = arg_key_value_number("budget-ppm", argv[0])
        if arg_budget_ppm is False:
            return False
        elif arg_budget_ppm is not None:
            budget_ppm = arg_budget_ppm
            argv = argv[1:]

    if len(argv) < 1:
        print_err("insert full-amount")
        return False

    full_amount = get_int(argv[0])
    if full_amount is False:
        return False
    argv = argv[1:]

    correct_amount = invoice_get_correct_amount(full_amount, budget_ppm)

    print_out(correct_amount)

    return True


def random_interval(max_value):
    return random.randint(1, max_value) - 1


def shuffle_array(ordered: list) -> list:
    shuffled = ordered.copy()
    random.shuffle(shuffled)
    return shuffled


def shuffle_dic(ordered: dict) -> dict:
    keys = list(ordered.keys())
    random.shuffle(keys)
    shuffled = {}
    for key in keys:
        shuffled[key] = ordered[key]
    return shuffled


def bad_request_is_cancelled(bad_request):
    # may be changed in the future
    # https://github.com/RoboSats/robosats/issues/1245

    if not isinstance(bad_request, str):
        return False

    return bad_request in (
        "This order has been cancelled by the maker",
        "This order has been cancelled collaborativelly"
    )


def bad_request_is_wrong_robot(bad_request):
    if not isinstance(bad_request, str):
        return False

    # pylint: disable=C0301 line-too-long
    return bad_request in (
        "Robot token SHA256 was provided in the header. However it is not a valid 39 or 40 characters Base91 string."
        "On the first request to a RoboSats coordinator, you must provide as well a valid public and encrypted private PGP keys"
    )
