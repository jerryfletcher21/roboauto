# roboauto

a [robosats](https://github.com/RoboSats/robosats) command-line interface

Main function is keep-online, after you have imported one or more robots from
different coordinators, run roboauto keep-online to automatically recreate the
orders when they expires, and get notified if the order is taken, running the
message-send script. An example for simplex is provided

## installation

#### local
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

create scripts pay-invoide, check-invoice and message-send in ~/.config/roboauto/,
some examples are in data/

source completions/roboauto.bash-completion in ~/.bashrc

## usage

```
$ roboauto --help
$ roboauto --verbose-help
```

```
$ roboauto import-robot --exp
insert robot name:
insert token:

# with tmux
roboauto keep-online
```

## license

roboauto is released under the terms of the ISC license.
See [LICENSE](LICENSE) for more details.
