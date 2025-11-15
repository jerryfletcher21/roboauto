#!/usr/bin/env python3

"""global_state.py"""

# options that can be changed in config file
roboauto_options = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    "date_format": "%Y/%m/%d %H:%M:%S",
    "tor_host": "127.0.0.1",
    "tor_port": 9050,
    "seconds_pending_order": 0,
    "order_maximum": 2,
    "robot_maximum_orders": 0,
    "create_new_after_maximum_orders": False,
    "log_level_waiting_for_taker_bond": 0,
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
        "exp": None,
        "sau": None,
        "tos": {
            "short_alias": "temple",
            "url": "http://ngdk7ocdzmz5kzsysa3om6du7ycj2evxp2f2olfkyq37htx3gllwp2yd.onion",
            "nostr_pubkey": "74001620297035daa61475c069f90b6950087fea0d0134b795fac758c34e7191"
        },
        "tbl": {
            "short_alias": "lake",
            "url": "http://4t4jxmivv6uqej6xzx2jx3fxh75gtt65v3szjoqmc4ugdlhipzdat6yd.onion",
            "nostr_pubkey": "f2d4855df39a7db6196666e8469a07a131cddc08dcaa744a344343ffcf54a10c"
        },
        "bve": {
            "short_alias": "veneto",
            "url": "http://mmhaqzuirth5rx7gl24d4773lknltjhik57k7ahec5iefktezv4b3uid.onion",
            "nostr_pubkey": "c8dc40a80bbb41fe7430fca9d0451b37a2341486ab65f890955528e4732da34a"
        },
        "otm": {
            "short_alias": "moon",
            "url": "http://otmoonrndnrddqdlhu6b36heunmbyw3cgvadqo2oqeau3656wfv7fwad.onion",
            "nostr_pubkey": "7af6f7cfc3bfdf8aa65df2465aa7841096fa8ee6b2d4d14fc43d974e5db9ab96"
        },
        "lba": {
            "short_alias": "bazaar",
            "url": "http://librebazovfmmkyi2jekraxsuso3mh622avuuzqpejixdl5dhuhb4tid.onion",
            "nostr_pubkey": "95521a33ba34f5924464f425e81b896b1aa9069796a778368ed053e3612c509b"
        },
        "fds": {
            "short_alias": "freedomsats",
            "url": "http://dqmmejfmtlve7d4ccohk4usriifdtci6xk4wv7igxn2fyaduh25s6did.onion",
            "nostr_pubkey": "ded3dc02a1a9b61ce59d11f496539cb3fd15f00326a16f47e5f8d76baba24bdb"
        },
        "wes": {
            "short_alias": "whiteyesats",
            "url": "http://s4usqbcf2pk2xwghdzaggrxd3paiqpvnl4lm2dxp6dec3wbclgbdyiyd.onion",
            "nostr_pubkey": "5dd5af0c0fbdd785af6bfe2ea1461f4bda4062391fe396661ef4dc4028d64d60"
        }
    }
}

# program state and options that can not be changed in the config file
roboauto_state = {
    "current_command_type": "info",
    "keep_online_hour_relative": False,
    "gpg": None,
    "logger": None,
    "log_level": 0,
    "filelock_timeout": 120,
    "requests_max_retries": 8,
    "sleep_interval": 5,
    "waiting_queue_remove_after": 10,
    "fetch_site": "cross-site",
    # "fetch_site": "same-origin",
    "config_home": "",
    "data_home": "",
    "active_home": "",
    "pending_home": "",
    "inactive_home": "",
    "paused_home": "",
    "coordinators_home": "",
    "lock_home": "",
    "gnupg_home": "",
    "log_home": "",
    "waiting_queue_file": "",
    "config_file": "",
    "config_file_hash": None,
    "message_notification_command": "",
    "lightning_node_command": "",
}
