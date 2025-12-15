# MASTERPIECE
## The Robotic Chessboard

Play a game of chess against the board itself! Masterpiece allows you to conduct human vs. human, human vs. computer, 
and computer vs. computer chess games on a physical chess board. This repository contains all of the source code to control
the board.

After you complete the setup steps, navigate to main.py and run to play on the board!

## Dependencies

[RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/?lai_vid=53JjVNAVjI6PJ&lai_sr=0-4&lai_sl=l&lai_p=1&lai_na=611310) - Remote access to Raspberry Pi

[GRBL](https://github.com/grbl/grbl) - Arduino gantry control

[Raspberry Pi Imager](https://www.raspberrypi.com/software/) - Used to flash the OS to the Raspberry Pi

[Raspberry Pi OS 64-bit](https://www.raspberrypi.com/software/operating-systems/) - The operating system for the Raspberry Pi

[Universal G-code Sender](https://winder.github.io/ugs_website/download/) - Used as configuration software for the gantry

[Stockfish](https://stockfishchess.org/download/) - Chess engine for computer move determination

[pigpio](https://abyz.me.uk/rpi/pigpio/) - Servo control on Raspberry Pi

[Python Chess](https://github.com/niklasf/python-chess) - Internal chess board and game state tracking

[NumPy](https://numpy.org/) - Basic numerical computing

[PySerial](https://pypi.org/project/pyserial/) - Serial communication between Pi and Arduino

## Setup

Add GRBL setup instructions

First, set up the Raspberry Pi by downloading the Raspberry Pi OS (64-bit) onto a micro-SD card, insert it 
into the slot on the Pi, and power it on. Allow 2-3 minutes for the Pi to boot

Next, [download RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/?lai_vid=53JjVNAVjI6PJ&lai_sr=0-4&lai_sl=l&lai_p=1&lai_na=611310) to access the Pi remotely with it's IP address.
From the device you are using to access the pi, you can use ```ping [YOUR PI NAME].local``` to discover it's IP. Or, if you have access to the router, use the router's page to find the IP address.
Input the IP address to RealVNC Viewer and you will have remote access to the Pi.

Once you have access to the Pi, install [Universal G-Code Sender](https://winder.github.io/ugs_website/download/) and [Stockfish](https://stockfishchess.org/download/) using the ARM64 
compatible versions. You can place these in any directory, but you will need to remember the file paths.

Then, clone this repository to the Pi from the terminal with the command,

```git clone https://github.com/kerwin4/chess_test.git```

Navigate into the repo, and create a python virtual environment with the following commands

```sudo apt update```
```sudo apt install python3-venv```
```python3 -m venv .[YOUR VIRTUAL ENVIRONMENT NAME HERE]```

This will allow use to use pip to install the necessary python packages. When installing packages
or running code from this repo, first ensure you are in the root of the repo and run the following,

```source [YOUR VIRTUAL ENVIRONMENT NAME HERE]/bin/activate```

You will see the name of your virtual environment appear in parentheses in the command line. This means
you have activated it successfully. Activate the venv any time you are working in the repo. You can
deactivate it at any time with ```deactivate```.

With the venv activated, run the following command to install the necessary python libraries.

```pip install -r requirements.txt```

Additionally, you will need the pigpio tools which can not be installed via pip. Instead, use apt to install the package.

```sudo apt update```
```sudo apt install python3-pigpio pigpio-tools```

This will ensure you have the pigpio daemon installed which is necessary for servo control.

From this point on, you have installed all of the dependencies and will now configure the gantry.
Launch Universal G-code Sender and connect to the Arduino on the correct port.
You will configure important gantry settings with the following commands. Unfortunately you will
need to send each line one at a time using the UGS terminal.

```$21 = 1``` (hard limits, bool)
```$22 = 1``` (homing cycle, bool)
```$23 = 3``` (homing dir invert mask:00000011)
```$24 = 25.000``` (homing feed, mm/min)
```$25 = 1500.000``` (homing seek, mm/min)
```$26 = 250``` (homing debounce, msec)
```$27 = 3.000``` (homing pull-off, mm)
```$100 = 40.323``` (x, step/mm)
```$101 = 40.323``` (y, step/mm)
```$110 = 5000.000``` (x max rate, mm/min)
```$111 = 5000.000``` (y max rate, mm/min)
```$120 = 100.000``` (x accel, mm/sec^2)
```$121 = 100.000``` (y accel, mm/sec^2)
```$130 = 500.000``` (x max travel, mm)
```$131 = 600.000``` (y max travel, mm)

You are now ready to run a game! Return to the root of the repo, activate your venv,
and navigate to the ```chess_game``` directory. Make sure you are no longer connected
to the Arduino in UGS as only one serial connection is allowed at a time.

Run a game with ```python main.py``` and you are all set!