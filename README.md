# Chess Test

Computer vs. Computer & Human vs. Computer control of a physical chess board.

Utilizes the python chess library and Stockfish engine to make move determinations and track game state.

## Setup

First, clone this repository to your computer with the following command,

```https://github.com/kerwin4/chess_test.git```

Then, install all of the necessary packages with

```pip install -r requirements.txt```

To install the chess engine used in this project, navigate to the [Stockfish Download page](https://stockfishchess.org/download/)

Download the correct version for your device, unzip the software, and place the .exe in the root of the repository.

Navigate to ```game_runner.py``` and change the ```STOCKFISH_PATH``` variable to your path to the stockfish exe file. If you are running the actual physical board on a raspberry pi, do the same for the ```gcode_game_runner.py``` file, however you must be running the ARMv8 software.

You are now configured to run a game! Have fun!