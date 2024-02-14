#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring


# default configs
roboauto_options = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0",
    "book_interval": 120,
    "bond_interval": 10,
    "slowly_paused_interval_global": 1000,
    "error_interval": 5,
    "default_duration": "86400",
    "default_escrow": "28800",
    "default_bond_size": "3.00",
    "date_format": "%Y/%m/%d %H:%M:%S",
    "tab_size": 4,
    "order_maximum": 2,
    "federation": {
        "exp": "http://robosats6tkf3eva7x2voqso3a5wcorsnw34jveyxfqi2fu7oyheasid.onion",
        "sau": "http://satstraoq35jffvkgpfoqld32nzw2siuvowanruindbfojowpwsjdgad.onion",
        "tos": "http://ngdk7ocdzmz5kzsysa3om6du7ycj2evxp2f2olfkyq37htx3gllwp2yd.onion",
        "tbl": "http://4t4jxmivv6uqej6xzx2jx3fxh75gtt65v3szjoqmc4ugdlhipzdat6yd.onion"
    }
}

roboauto_state = {
    "print_date": False,
    "filelock_timeout": 120,
    "sleep_interval": 5,
    "active_home": "",
    "inactive_home": "",
    "paused_home": "",
    "lock_home": "",
    "waiting_queue_file": "",
    "keep_online_refresh_file": "",
    "config_file": "",
    "message_command": "",
    "check_command": "",
    "pay_command": ""
}
