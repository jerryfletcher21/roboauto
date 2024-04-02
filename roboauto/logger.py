#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring

import sys
import datetime

from roboauto.global_state import roboauto_options, roboauto_state


def get_date():
    return datetime.datetime.today().strftime(roboauto_options["date_format"])


def print_and_log(arg, end="\n", file=None):
    if file is not None:
        print(arg, end=end)
    else:
        print(arg, end=end, file=file)

    if roboauto_state["should_log"] is True:
        if roboauto_state["logger"] is None:
            try:
                # pylint: disable=R1732 consider-using-with
                roboauto_state["logger"] = open(
                    roboauto_state["log_file"], "a", encoding="utf8"
                )
            except OSError:
                return False

        print(arg, end=end, file=roboauto_state["logger"])

    return True


def print_out(arg, end="\n", date=True):
    if roboauto_state["should_log"] and date:
        date_current = get_date()
        print_and_log("[" + date_current + "] ", end="")
    print_and_log(arg, end=end)


def print_stderr(error_string, arg, end="\n", date=True, error=True):
    if roboauto_state["should_log"] and date:
        date_current = get_date()
        print_and_log("[" + date_current + "] ", end="", file=sys.stderr)
    if error:
        print_and_log(error_string, end="", file=sys.stderr)
    print_and_log(arg, end=end, file=sys.stderr)


def print_war(arg, end="\n", date=True, error=True):
    print_stderr("warning: ", arg, end, date, error)


def print_err(arg, end="\n", date=True, error=True):
    print_stderr("error: ", arg, end, date, error)
