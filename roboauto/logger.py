#!/usr/bin/env python3

"""logger.py"""

# pylint: disable=C0116 missing-function-docstring

import sys

from roboauto.global_state import roboauto_state
from roboauto.date_utils import date_get_current


def logger_flush():
    if roboauto_state["logger"] is not None:
        roboauto_state["logger"].flush()


def print_and_log(arg, end="\n", file_stream=None, level: int | bool = True):
    """level is for writing to stdout/stderr, everything is always
    saved to the log file.
    level goes from 0 (True) -> always log also to the terminal
    to higher integers that will be logged to the terminal just
    when roboauto_state["log_level"] is high enough"""

    if level is True:
        level_int = 0
    else:
        level_int = level

    if level_int <= roboauto_state["log_level"]:
        if file_stream is None:
            print(arg, end=end)
        else:
            print(arg, end=end, file=file_stream)

    if roboauto_state["current_command_type"] != "info":
        if roboauto_state["logger"] is None:
            log_file_name = \
                roboauto_state["log_home"] + "/" + \
                roboauto_state["current_command_type"] + \
                ".log"

            try:
                # pylint: disable=R1732 consider-using-with
                roboauto_state["logger"] = open(
                    log_file_name, "a", encoding="utf8"
                )
            except OSError:
                return False

        print(arg, end=end, file=roboauto_state["logger"])

    return True


def print_out(arg, end="\n", date=True, level: int | bool = True):
    string_print = str(arg)

    if roboauto_state["current_command_type"] == "keep-online" and date:
        date_current = date_get_current()
        string_print = "[" + date_current + "] " + string_print

    print_and_log(string_print, end=end, level=level)


def print_stderr(
    error_string, arg, end="\n",
    date=True, error=True, level: int | bool = True
):
    string_print = str(arg)

    if error:
        string_print = error_string + string_print

    if roboauto_state["current_command_type"] == "keep-online" and date:
        date_current = date_get_current()
        string_print = "[" + date_current + "] " + string_print

    print_and_log(string_print, end=end, file_stream=sys.stderr, level=level)


def print_war(arg, end="\n", date=True, error=True, level: int | bool = True):
    print_stderr("warning: ", arg, end=end, date=date, error=error, level=level)


def print_err(arg, end="\n", date=True, error=True, level: int | bool = True):
    print_stderr("error: ", arg, end=end, date=date, error=error, level=level)
