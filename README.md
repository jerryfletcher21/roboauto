# Roboauto

A [robosats](https://github.com/RoboSats/robosats) command-line interface

Roboauto aims to be a full robosats client, and an alternative to the main
web client. It is mainly intended for makers with multiple offers. To
use it, it requires a lightning node, or a wallet that exposes apis for
creating and paying invoices.

Robots are divided in 4 directories: active, pending, paused and inactive.

Active are all the robots that have an active offer not yet taken.

Pending are robots that have pending offers.

Paused are robots that do not currently have an online offer, for example
robots just generated, and robots that have a paused offer.

Inactive are old robots that have a completed offer.

Main command of roboauto is `keep-online`. After you have generated
robots from different coordinators, and created make offers, `roboauto
keep-online` will automatically recreate offers when they expire, and
notify the user when an order is taken, by running the message-notification
script. Optionally it will also automatically pay escrow/send invoice of
taken orders.

Examples scripts for simplex and mutt are provided.

`roboauto keep-online` should be used inside tmux
(or others terminal multiplexers)

## Installation

#### Local (suggested)
```
$ python3 -m venv robo
$ . robo/bin/activate
$ pip install -r requirements.txt
$ pip install .
```

#### Global
```
$ pip install --break-system-packages -r requirements.txt
$ pip install --break-system-packages .
```

## Configuration

Copy config/config.ini to ~/.config/roboauto/config.ini and edit it.

Create scripts lightning-node and message-notification in
~/.config/roboauto/, some examples are in data/

lightning-node should support 3 actions:
* check: takes an invoice and an amount and exits with an error status
  if the invoice is not for the correct amount
* pay: takes an invoice and a label and pays the invoice
* invoice: takes an amount and a label, create the invoice and prints it
  to stdout

message-notification takes an event and a message, and should send a
message notification.

If you use core lightning and simplex for notifications:
```
cp data/lightning-node-core-lightning ~/.config/roboauto/lightning-node
cp data/message-notification-simplex ~/.config/roboauto/message-notification
```

Source completions/roboauto.bash-completion in ~/.bashrc

If the bash completion package is installed there are better completions in
`create-order`, `recreate-order` and `change-order-expire`

## Usage

#### documentation
```
$ roboauto --help
$ roboauto --verbose-help
```

#### generate robot and order
```
# generate a robot with a coordinator
$ roboauto generate-robot --exp
RobotName

# create the order and lock the bond
$ roboauto create-order RobotName type=sell currency=eur min_amount=300 max_amount=900 payment_method="Instant SEPA" premium=5
RobotName order-id sell eur 300-900 5.00 Instant SEPA Waiting for maker bond
invoice checked successfully
checking if order is bonded...
checking if order is bonded...
RobotName bonded successfully, order is public
RobotName order created successfully

# if you have roboauto keep-online running
# (will add to waiting queue if orders this hour exceed maximum orders per hour)
# $ roboauto create-order --no-bond RobotName type=sell currency=eur min_amount=300 max_amount=900 payment_method="Instant SEPA" premium=5

# print the token if you want to import it in the robosats website
$ roboauto print-token RobotName
************************************
```

#### or import robot from robosats website to roboauto
```
$ roboauto import-robot --exp
insert robot name:
insert token:
```

#### then keep generated and imported robots online (with tmux, it will keep running)
```
# get notified when your offers get taken and recreate them when they expire
# if you want to also pay escrow/send invoice check seconds_pending_order in config.ini
$ roboauto keep-online
# or with less non important erorr messages
# $ roboauto keep-online --quiet
```

#### take an offer
```
# take a look at the books of all the coordinators
$ roboauto list-offers --all usd "strike"
exp ord-id PeerRobotName            sell usd   8h  3.00   4.00%  -      150     300 00:00:00 Strike
...

# lock the bond
$ roboauto take-order YourRobotName order-id 200
YourRobotName PeerRobotName order-id sell usd 150-300 4.00 Strike Waiting for taker bond
invoice checked successfully
checking if order is bonded...
checking if order is bonded...
YourRobotName bonded successfully, order is taken
YourRobotName order-id taken successfully

# submit the invoice
$ roboauto invoice-send YourRobotName
YourRobotName order-id sell usd 200 4.00 Strike Waiting for trade collateral and buyer invoice
YourRobotName order-id invoice sent successfully
# or pay the escrow if you are the seller
# roboauto escrow-pay YourRobotName

# see what your peer is saying
$ roboauto chat-print YourRobotName
1933/04/05 00:00:00 E PeerRobotName
Hello robot!

# chat with your peer
$ roboauto message-send YourRobotName 'Hello! How can I pay you?'
message sent correctly
now E YourRobotName
Hello! How can I pay you?

...

# check the order status to see if the seller confirmed the payment
$ roboauto order-info --simple YourRobotName | jq -r '.status_string'

# confirm you have received the payment
$ roboauto confirm-send YourRobotName

# rate the robosats coordinator 5 stars!
$ roboauto rate-coordinator 5
YourRobotName order-id sell usd 200 4.00 Strike Sucessful trade
YourRobotName order-id robosats rated 5 stars
```

## Features

- [X] simple apis: info historical limits price ticks
- [X] import robot
- [X] generate robot
- [X] list the books of the coordinators
- [X] robot info
- [X] update stealth option
- [X] order info
- [X] create/recreate order
- [X] cancel order
- [X] take order
- [X] toggle pause for order
- [X] pay escrow, send invoice for order
- [X] print chat and send messages
- [X] second/undo confirmations of payments
- [X] start dispute
- [X] rate coordinator
- [X] claim rewards
- [X] keep online orders, recreate them when they expire
- [X] change orders next time they expire
- [X] send message notification when an order is taken
- [X] set a maximum of offer per hour
- [X] different tor circuit for each robot
- [X] automatically pay escrow/send invoice
- [X] core lightning
- [ ] lnd, eclair, ldk, other nodes or wallets with apis
- [ ] update order: `update_address` and `submit_statement`
- [ ] handle expired/unpaid invoices
- [ ] fast chat with websocket

## License

Roboauto is released under the terms of the ISC license.
See [LICENSE](LICENSE) for more details.
