#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring
# pylint: disable=C0209 consider-using-f-string

import os
import sys
import getpass
import json
import subprocess
import configparser
import secrets

from roboauto.logger import print_out, print_err
from roboauto.global_state import roboauto_options, roboauto_state


def dir_make_sure_exists(directory):
    if not os.path.exists(directory):
        if os.makedirs(directory) is not None:
            print_err("creating " + directory)
            return False
    elif not os.path.isdir(directory):
        print_err(directory + " is not a directory")
        return False

    return True


def update_single_option(option, new_option, print_info=False):
    if roboauto_options[option] != new_option:
        old_option = roboauto_options[option]
        roboauto_options[option] = new_option
        if print_info:
            print_out(
                "option %s changed from %s to %s" %
                (option, str(old_option), str(new_option))
            )


def update_roboauto_options(print_info=False):
    if os.path.isfile(roboauto_state["config_file"]):
        parser = configparser.RawConfigParser()
        with open(roboauto_state["config_file"], encoding="utf8") as stream:
            default_section = "DEFAULT"
            parser.read_string("[" + default_section + "]\n" + stream.read())

            for option in (
                "robosats_url", "user_agent", "default_duration",
                "default_escrow", "date_format"
            ):
                if parser.has_option(default_section, option):
                    new_option = parser.get(default_section, option).strip("'\"")
                    update_single_option(option, new_option, print_info=print_info)

            for option in (
                "book_interval", "bond_interval", "slowly_paused_interval_global",
                "error_interval", "tab_size", "order_maximum"
            ):
                if parser.has_option(default_section, option):
                    new_option = parser.getint(default_section, option)
                    update_single_option(option, new_option, print_info=print_info)


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
    roboauto_state["inactive_home"] = roboauto_home + "/inactive"
    roboauto_state["paused_home"] = roboauto_home + "/paused"
    roboauto_state["lock_home"] = roboauto_home + "/lock"

    roboauto_state["waiting_queue_file"] = roboauto_home + "/waiting-queue"

    roboauto_state["config_file"] = roboauto_config + "/config.ini"
    roboauto_state["message_command"] = roboauto_config + "/message-send"
    roboauto_state["check_command"] = roboauto_config + "/check-invoice"
    roboauto_state["pay_command"] = roboauto_config + "/pay-invoice"

    for directory_global in (
        roboauto_home, roboauto_config,
        roboauto_state["active_home"],
        roboauto_state["inactive_home"],
        roboauto_state["paused_home"],
        roboauto_state["lock_home"]
    ):
        if not dir_make_sure_exists(directory_global):
            sys.exit(1)

    update_roboauto_options()


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


def subprocess_run_command(program, print_error=True):
    try:
        process = subprocess.run(program, capture_output=True, check=False)
    except FileNotFoundError:
        print_err("error: command %s does not exists" % program[0])
        return False
    if process.returncode != 0:
        if print_error:
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


def file_write(file_name, string):
    try:
        with open(file_name, "w", encoding="utf8") as file:
            file.write(string + "\n")
    except EnvironmentError:
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


def file_read(file_name):
    try:
        with open(file_name, "r", encoding="utf8") as file:
            string = file.readline().rstrip()
    except EnvironmentError:
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


def get_date_short(date_unformat):
    try:
        date_short = date_unformat.split("T")[1].split(".")[0]
    except IndexError:
        date_short = "???"

    return date_short
