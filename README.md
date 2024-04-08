# roboauto

a [robosats](https://github.com/RoboSats/robosats) command-line interface

main function is keep-online, after you have imported one or more robots from
different coordinators, run `roboauto keep-online` to automatically recreate the
orders when they expire, and get notified if the order is taken, running the
message-notification script. An example for simplex is provided

## installation

#### local (preferred)
```
$ python3 -m venv robo
$ . robo/bin/activate
$ pip install -r requirements.txt
$ pip install .
```

#### global
```
$ pip install --break-system-packages -r requirements.txt
$ pip install --break-system-packages .
```

copy config/config.ini in ~/.config/roboauto/ and edit it

create scripts lightning-node and message-notification in ~/.config/roboauto/,
some examples are in data/

if you use core lightning and simplex for notifications:
```
cp data/lightning-node-core-lightning ~/.config/roboauto/lightning-node
cp data/message-notification-simplex ~/.config/roboauto/message-notification
```

source completions/roboauto.bash-completion in ~/.bashrc

## usage

```
$ roboauto --help
$ roboauto --verbose-help
```

```
# generate robot and order

$ roboauto generate-robot --exp
RobotName

$ roboauto create-order RobotName type=sell currency=eur min_amount=300 max_amount=900 payment_method="Instant SEPA" premium=5
RobotName order-id sell eur 300-900 5.00 Instant SEPA Waiting for maker bond
invoice checked successfully
checking if order is bonded...
checking if order is bonded...
RobotName bonded successfully, order is public
RobotName order created successfully

$ roboauto print-token RobotName
************************************
# this can be imported in robosats website


# or import robot from robosats website to roboauto

$ roboauto import-robot --exp
insert robot name:
insert token:


# then (with tmux, it will keep running)

$ roboauto keep-online
```

## roadmap

* full exchange pipeline

## license

roboauto is released under the terms of the ISC license.
see [LICENSE](LICENSE) for more details.
