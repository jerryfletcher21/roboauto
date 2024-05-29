#!/usr/bin/env python3

"""global_state.py"""

# options that can be changed in config file
roboauto_options = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    "date_format": "%Y/%m/%d %H:%M:%S",
    "seconds_pending_order": 0,
    "order_maximum": 2,
    "robot_maximum_orders": 0,
    "tab_size": 4,
    "routing_budget_ppm": 1000,
    "requests_timeout": 120,
    "orders_timeout": 60,
    "active_interval": 80,
    "pending_interval": 120,
    "pay_interval": 2,
    "error_interval": 5,
    "default_duration": 86400,
    "default_escrow": 28800,
    "default_bond_size": 3.00,
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
    "current_command_type": "info",
    "keep_online_hour_relative": False,
    "keep_online_sleep": True,
    "gpg": None,
    "logger": None,
    "log_level": 0,
    "filelock_timeout": 120,
    "requests_max_retries": 8,
    "sleep_interval": 5,
    "waiting_queue_remove_after": 10,
    "fetch_site": "cross-site",
    # "fetch_site": "same-origin",
    "robot_date_format": "%Y-%m-%dT%H:%M:%S.%fZ",
    "active_home": "",
    "pending_home": "",
    "inactive_home": "",
    "paused_home": "",
    "lock_home": "",
    "gnupg_home": "",
    "log_home": "",
    "waiting_queue_file": "",
    "config_file": "",
    "message_notification_command": "",
    "lightning_node_command": "",
}
