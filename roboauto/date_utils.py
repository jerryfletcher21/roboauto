#!/usr/bin/env python3

"""date_utils.py"""

# pylint: disable=C0116 missing-function-docstring

import time
import calendar
import datetime

from roboauto.global_state import roboauto_options, roboauto_state


def timestamp_from_utc_date(time_input):
    """calendar.timegm tuple in UTC --> seconds since epoch"""

    return calendar.timegm(time_input)


def timestamp_from_date_string(
    date_string, input_format=roboauto_state["robot_date_format"]
):
    return timestamp_from_utc_date(time.strptime(
        date_string, input_format
    ))


def date_convert_time_zone_and_format(time_input, output_format):
    """used by date_convert_time_zone_and_format_string and
    date_convert_time_zone_and_format_timestamp
    time.localtime seconds since epoch --> tuple in local timezone"""

    return time.strftime(
        output_format,
        time.localtime(timestamp_from_utc_date(time_input))
    )


def date_convert_time_zone_and_format_string(
    date_string,
    output_format=roboauto_options["date_format"],
    input_format=roboauto_state["robot_date_format"]
):
    """convert a date string utc in input format to a local
    time zone date string in output format"""

    return date_convert_time_zone_and_format(
        time.strptime(date_string, input_format),
        output_format
    )


def date_convert_time_zone_and_format_timestamp(
    timestamp, output_format
):
    """convert a timestamp utc to a local
    time zone date string in output format"""

    return date_convert_time_zone_and_format(
        time.gmtime(timestamp),
        output_format
    )


def get_current_hour_from_timestamp(timestamp):
    return int(date_convert_time_zone_and_format_timestamp(
        timestamp, "%H"
    ))


def get_current_minutes_from_timestamp(timestamp):
    return int(date_convert_time_zone_and_format_timestamp(
        timestamp, "%M"
    ))


def get_hour_offer(hour_date, current_timestamp, relative):
    """get the hour from the timestamp, if relative the hour relative
    to current timestamp"""

    if relative:
        unix_time = int(timestamp_from_date_string(hour_date))

        date_hour = (24 - int((current_timestamp - unix_time) / 3600)) % 24
    else:
        date_hour = int(date_convert_time_zone_and_format_string(
            hour_date, output_format="%H"
        ))

    return date_hour


def get_current_timestamp():
    return int(datetime.datetime.now().timestamp())


def date_get_current(date_format=roboauto_options["date_format"]):
    return datetime.datetime.now().strftime(date_format)


def date_get_yesterday(date_format=roboauto_options["date_format"]):
    return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(date_format)
