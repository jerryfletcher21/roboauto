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
def roboauto_get_coordinator(coordinator):
    coord = roboauto_options["federation"].get(coordinator, False)
    if coord is False:
        print_err(f"coordinator {coordinator} not valid")
        return False

    return coord


def roboauto_get_coordinator_url(coordinator):
    coord = roboauto_get_coordinator(coordinator)
    if coord is False:
        return False

    url = coord.get("url", False)
    if url is False:
        print_err(f"coordinator {coordinator} does not have url")
        return False

    return url


def roboauto_get_short_alias(coordinator):
    coord = roboauto_get_coordinator(coordinator)
    if coord is False:
        return False

    short_alias = coord.get("short_alias", False)
    if short_alias is False:
        print_err(f"coordinator {coordinator} does not have short_alias")
        return False

    return short_alias


def roboauto_get_coordinator_nostr_pubkey(coordinator):
    coord = roboauto_get_coordinator(coordinator)
    if coord is False:
        return False

    nostr_pubkey = coord.get("nostr_pubkey", False)
    if nostr_pubkey is False:
        print_err(f"coordinator {coordinator} does not have nostr_pubkey")
        return False

    return nostr_pubkey


def roboauto_get_coordinator_from_url(coordinator_url):
    for coordinator in roboauto_options["federation"]:
        if roboauto_options["federation"][coordinator].get("url", False) == coordinator_url:
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

    return coordinator, roboauto_options["federation"][coordinator].get("url", False)


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


def roboauto_get_coordinator_url_from_argv(argv) -> tuple:
    """get a single coordinator or custom url from argv"""
    multi_false = False, False, False

    if re.match('^--coord-url=', argv[0]) is not None:
        coord_url = argv[0].split("=", 1)[1]
        argv = argv[1:]
        user = sha256_single(coord_url)
    else:
        user, coord_url, argv = roboauto_get_coordinator_from_argv(argv)
        if coord_url is False:
            return multi_false

    return user, coord_url, argv


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


def get_file_hash(filename):
    try:
        with open(filename, 'rb') as file:
            file_content = file.read()
            return hashlib.sha256(file_content).hexdigest()
    except FileNotFoundError:
        return None


def update_roboauto_options(print_info=False):
    # pylint: disable=R1702 too-many-nested-blocks

    if not os.path.isfile(roboauto_state["config_file"]):
        if roboauto_state["config_file_hash"] is not None:
            roboauto_state["config_file_hash"] = None
            if print_info:
                print_out("config file removed")
        return True
    else:
        if roboauto_state["config_file_hash"] is None:
            if print_info:
                print_out("config file present")

    new_config_file_hash = get_file_hash(roboauto_state["config_file"])
    if new_config_file_hash != roboauto_state["config_file_hash"]:
        roboauto_state["config_file_hash"] = new_config_file_hash
    else:
        return True

    parser = configparser.RawConfigParser()
    parser.read(roboauto_state["config_file"])

    general_section = "general"

    for section in list(parser):
        if section not in ("DEFAULT", general_section):
            if re.match('^federation.', section) is None:
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
            "user_agent", "date_format", "tor_host"
        ):
            if parser.has_option(general_section, option):
                new_value = parser.get(general_section, option).strip("'\"")
                update_single_option(option, new_value, print_info=print_info)

        option = "create_new_after_maximum_orders"
        if parser.has_option(general_section, option):
            new_value = parser.getboolean(general_section, option)
            update_single_option(option, new_value, print_info=print_info)

        for option in (
            "tor_port", "seconds_pending_order", "order_maximum", "robot_maximum_orders",
            "log_level_waiting_for_taker_bond", "tab_size", "routing_budget_ppm",
            "requests_timeout", "orders_timeout", "active_interval",
            "pending_interval", "pay_interval", "error_interval",
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

    new_coordinator_list = []
    for federation_section in list(parser):
        if re.match('^federation.', federation_section) is not None:
            federation_section_options = parser.options(federation_section)
            coord_name = federation_section.split(".", 1)[1]
            new_coordinator_list.append(coord_name)

            coord_sections = ("short_alias", "url", "nostr_pubkey")
            coord_dict = {key: "" for key in coord_sections}
            for key in federation_section_options:
                if key not in coord_sections:
                    print_err(f"{coord_name} wrong key {key}")
                    return False
                coord_dict[key] = parser.get(federation_section, key).strip("'\"")
            for key in coord_dict:
                if key != "nostr_pubkey" and not coord_dict[key]:
                    print_err(f"{coord_name} key {key} not set")
                    return False

            coord_is_new = coord_name not in list(roboauto_options["federation"])
            if not coord_is_new:
                for key in federation_section_options:
                    old_value = roboauto_options["federation"][coord_name][key]
                    new_value = coord_dict[key]
                    if old_value != new_value:
                        roboauto_options["federation"][coord_name][key] = new_value
                        if print_info:
                            print_out(
                                f"{coord_name} {key} changed from {old_value} to {new_value}"
                            )
            else:
                if print_info:
                    print_out(f"{coord_name} added as new coordinator")
                roboauto_options["federation"].update({coord_name: coord_dict})
                for key in federation_section_options:
                    value = coord_dict[key]
                    if print_info:
                        print_out(f"{coord_name} {key} set to {value}")

    for coord_name in list(roboauto_options["federation"]):
        if coord_name not in new_coordinator_list:
            del roboauto_options["federation"][coord_name]
            if print_info:
                print_out(f"coordinator {coord_name} removed")

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


def bool_none_to_int_string(bool_none):
    if bool_none is True:
        return "1"
    elif bool_none is False:
        return "0"
    else:
        return "-"


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

    # return bad_request in (
    #     "This order has been cancelled by the maker",
    #     "This order has been cancelled collaborativelly"
    # )
    # 220b4263b4324beff4189ac71de8b90d55737861
    return bad_request == "This order has been cancelled"


def bad_request_is_wrong_robot(bad_request):
    if not isinstance(bad_request, str):
        return False

    # pylint: disable=C0301 line-too-long
    return bad_request in (
        "Robot token SHA256 was provided in the header. However it is not a valid 39 or 40 characters Base91 string."
        "On the first request to a RoboSats coordinator, you must provide as well a valid public and encrypted private PGP keys"
    )
