#!/usr/bin/env python3

"""global_state.py"""

# options that can be changed in config file
roboauto_options = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0",
    "book_interval": 120,
    "pending_interval": 120,
    "pay_interval": 2,
    "error_interval": 5,
    "time_zone": 0,
    "tab_size": 4,
    "order_maximum": 2,
    "routing_budget_ppm": 1000,
    "default_duration": "86400",
    "default_escrow": "28800",
    "default_bond_size": "3.00",
    "date_format": "%Y/%m/%d %H:%M:%S",
    "federation": {
        "exp": "http://robosats6tkf3eva7x2voqso3a5wcorsnw34jveyxfqi2fu7oyheasid.onion",
        "sau": "http://satstraoq35jffvkgpfoqld32nzw2siuvowanruindbfojowpwsjdgad.onion",
        "tos": "http://ngdk7ocdzmz5kzsysa3om6du7ycj2evxp2f2olfkyq37htx3gllwp2yd.onion",
        "tbl": "http://4t4jxmivv6uqej6xzx2jx3fxh75gtt65v3szjoqmc4ugdlhipzdat6yd.onion",
        "bve": "http://mmhaqzuirth5rx7gl24d4773lknltjhik57k7ahec5iefktezv4b3uid.onion"
    }
}

# program state and options that can not be changed in the config file
roboauto_state = {
    "should_log": False,
    "keep_online_hour_relative": False,
    "gpg": None,
    "logger": None,
    "filelock_timeout": 120,
    "sleep_interval": 5,
    "fetch_site": "cross-site",
    # "fetch_site": "same-origin",
    "robot_date_format": "%Y-%m-%dT%H:%M:%S.%fZ",
    "active_home": "",
    "pending_home": "",
    "inactive_home": "",
    "paused_home": "",
    "lock_home": "",
    "gnupg_home": "",
    "waiting_queue_file": "",
    "log_file": "",
    "config_file": "",
    "message_notification_command": "",
    "lightning_node_command": "",
}
