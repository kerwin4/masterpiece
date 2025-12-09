"""
Full game control for computer vs computer physical chess board.
"""

import chess
import chess.engine
import time
import serial
import pigpio
from subprocess import Popen, PIPE
from board_item import BoardItem

# CONFIGURE EVERYTHING
STOCKFISH_PATH = "/home/chess/stockfish/stockfish-android-armv8" # path to stockfish engine, for pi: /home/chess/stockfish/stockfish-android-armv8
ENGINE_TIME = 0.1 # amount of time stockfish has to make a decision
TURN_DELAY = 0.5 # added delay to prevent runaway memory
SHOW_PATHS = True # display planned paths if True

SERVO_PIN = 17  # gpio pin for the servo
SERIAL_PORT = "/dev/ttyACM0" # port for serial cable to arduino
BAUD_RATE = 115200 # GRBL communication rate (MUST BE 115200)

# servo control daemon
def start_pigpio_daemon():
    """
    Starts the pigpio daemon if it's not already running.
    
    Returns:
        int: 0=daemon started, 1=daemon already running, 2=crash
    """
    p = Popen("sudo pigpiod", stdout=PIPE, stderr=PIPE, shell=True)
    s_out, s_err = p.communicate()  # use communicate to wait for process and get output

    if not s_out and not s_err:
        print("pigpiod started")
        return 0  # started
    elif b"pigpio.pid" in s_err:
        print("pigpiod already running")
        return 1  # already started
    else:
        print(f"error pigpiod {s_err.decode()}")
        return 2  # error

# USER INPUT GAME CONFIG
def ask_int(prompt, min_val=0, max_val=20):
    """
    Prompt the user to enter an integer within a specified range.

    Repeats the prompt until a valid integer within the provided range is entered.

    Args:
        prompt (str): The message to display to the user
        min_val (int, optional): Minimum valid value (inclusive). Defaults to 0
        max_val (int, optional): Maximum valid value (inclusive). Defaults to 20

    Returns:
        int: The integer entered by the user within the specified range
    """
    while True:
        val = input(prompt).strip() # get user input
        if val.isdigit(): # make sure it's a number
            val = int(val) # convert to int
            if min_val <= val <= max_val: # make sure it's within the valid range
                return val
        print(f"Please enter a number between {min_val} and {max_val}.") # reprompt the user for new input if they give bad input

def ask_choice(prompt, choices):
    """
    Prompt the user to select a choice from a list.

    Repeats the prompt until a valid choice from "choices" is entered regardless of letter case

    Args:
        prompt (str): The message to display to the user
        choices (list[str]): List of valid choices

    Returns:
        str: The choice selected by the user, returned in its original casing
    """
    choices_lower = {c.lower(): c for c in choices} # make everything lowercase
    while True:
        val = input(prompt).strip().lower() # get input from the user
        if val in choices_lower: # if the input is valid
            return choices_lower[val] # return it
        print("Invalid choice. Options are:", ", ".join(choices)) # otherwise reprompt the user for new input

# choose game mode
mode = ask_choice(
    "\nSelect mode:\n"
    "  1 = Human vs Computer\n"
    "  2 = Computer vs Computer\n"
    "Enter choice: ",
    ["1", "2"]
)

# configure computer vs computer play if selected
if mode == "2":
    AUTO_PLAY = True # no human player
    HUMAN_PLAYS_WHITE = False
    print("\nComputer vs Computer selected.")

    WHITE_SKILL = ask_int("Enter White engine skill level (0-20): ")
    BLACK_SKILL = ask_int("Enter Black engine skill level (0-20): ")

# configure human vs computer play if not computer vs computer
else:
    AUTO_PLAY = False # not computer vs computer
    print("\nHuman vs Computer selected.")

    color_choice = ask_choice(
        "Do you want to play as White or Black? ",
        ["White", "Black"]
    )
    HUMAN_PLAYS_WHITE = (color_choice == "White")

    # only need to configure one chess engine for human vs computer
    if HUMAN_PLAYS_WHITE:
        WHITE_SKILL = None  # Human
        BLACK_SKILL = ask_int("Enter Computer (Black) skill level (0-20): ")
    else:
        BLACK_SKILL = None  # Human
        WHITE_SKILL = ask_int("Enter Computer (White) skill level (0-20): ")

# display game configuration settings once done
print("\nConfiguration complete:")
print(" Computer vs computer?", AUTO_PLAY)
print(" Human plays white?", HUMAN_PLAYS_WHITE)
print(" White computer skill:", WHITE_SKILL)
print(" Black computer skill:", BLACK_SKILL)

# set up pigpio daemon and give it time to configure
start_pigpio_daemon()
time.sleep(1)
# connect pigpio to the pi
pi = pigpio.pi()
# throw an error if no connection
if not pi.connected:
    raise RuntimeError("pigpiod broken")

# SERVO COMMAND FUNCTIONS
def servo_up():
    """
    Move the servo to the "up" position.

    Sends the appropriate PWM signal to the configured GPIO pin and waits 0.4s
    for motion to complete.
    """
    print("[PI] Servo up")
    pi.set_servo_pulsewidth(SERVO_PIN, 1300)
    time.sleep(0.4)

def servo_down():
    """
    Move the servo to the "down" position.

    Sends the appropriate PWM signal to the configured GPIO pin and waits 0.4s
    for motion to complete.
    """
    print("[PI] Servo down")
    pi.set_servo_pulsewidth(SERVO_PIN, 1900)
    time.sleep(0.4)

def servo_neutral():
    """
    Stop sending PWM signals to the servo.

    Sets the servo to neutral/off state.
    """
    pi.set_servo_pulsewidth(SERVO_PIN, 0)

# connect to GRBL arduino over serial
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)
arduino.reset_input_buffer()

# GRBL queues moves if it receives them faster than it's executing them,
# so this function only confirms that a line has been added to the queue
def wait_for_ok():
    """
    Wait for a response of 'ok' from the GRBL controller.

    Continuously reads serial lines from the Arduino until 'ok' is received.
    Any other responses are printed for informational purposes.

    Returns:
        None
    """
    while True:
        resp = arduino.readline().decode("utf-8").strip()
        if resp == "ok":
            return
        elif resp:
            print(f"[GRBL INIT] {resp}")

# start gantry setup
# ensure the servo is down before homing
servo_down()
arduino.write(b"$H\n") # home x-y axes
wait_for_ok() # ensure GRBL has received it

arduino.write(b"G92 X0 Y0\n")  # zero both axes
wait_for_ok() # ensure GRBL has received it

arduino.write(b"G20 G90\n") # inches + absolute coordinate mode
wait_for_ok() # ensure GRBL has received it

# servo synchronization function
# since the servo is controlled by the pi but the gantry is controlled
# by the arduino, we need to move the servo at the right moments.
# By waiting until a sequence of moves is completed and the gantry is idle,
# we can guarantee the servo moves at the right time
def wait_until_idle(timeout=60.0):
    """
    Wait until the GRBL controller reports that it is idle.

    Polls the controller status with a 0.1s delay between queries until "Idle" is
    found in the response.

    Args:
        timeout (float, optional): Maximum number of seconds to wait. Raises
            TimeoutError if exceeded. Defaults to 60.0

    Raises:
        TimeoutError: If GRBL does not become idle within "timeout" seconds
    """
    start_time = time.time() # when the function is called, start a timer
    while True:
        arduino.reset_input_buffer()
        arduino.write(b"?\n") # request GRBL status
        time.sleep(0.1) # wait a moment for a resonse

        while arduino.in_waiting:
            status = arduino.readline().decode().strip() # get the response
            if "Idle" in status: # if the gantry is idle, we can move on
                return
        # if gantry is not idle, keep looping, but make sure we don't
        # exceed the waiting time
        if time.time() - start_time > timeout:
            raise TimeoutError("GRBL did not become idle in time")


# send a single line of gcode from the pi to the arduino function
def send_gcode_line(line, next_line=None):
    """
    Only wait for idle if the NEXT line is a servo command.
    """
    line = line.strip()
    if not line:
        return

    # servo control functions
    if line == "servo_up":
        wait_until_idle()
        servo_up()
        return

    if line == "servo_down":
        wait_until_idle()
        servo_down()
        return

    # send normal gcode to arduino
    arduino.write((line + "\n").encode("utf-8"))

    # wait for the line to be accepted
    while True:
        resp = arduino.readline().decode().strip()
        if resp == "ok":
            break
        elif resp:
            print("[GRBL]", resp)

    # if the next move is a servo move, wait until the gantry is done
    if next_line in ("servo_up", "servo_down"):
        wait_until_idle()


# finally set up the game and display the starting board representations
board_item = BoardItem()
#board_item.display_board()
board_item.display_state()
#board_item.display_nodes()

# set up the chess engines
white_engine = None
black_engine = None

# if computer vs computer play, set up 2 engines
if AUTO_PLAY:
    white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    white_engine.configure({"Skill Level": WHITE_SKILL})
    black_engine.configure({"Skill Level": BLACK_SKILL})

# if human vs computer play, only set up one engine according to which
# color the human player picked
else:
    if HUMAN_PLAYS_WHITE:
        # human = white, computer = black
        black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        black_engine.configure({"Skill Level": BLACK_SKILL})
    else:
        # human = black, computer = white
        white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        white_engine.configure({"Skill Level": WHITE_SKILL})

# main game loop
turn = 1
# keep looping until checkmate
while not board_item.chess_board.is_game_over():
    # determine whose turn it is
    color = "White" if board_item.chess_board.turn == chess.WHITE else "Black"
    print(f"\n[{turn}] {color}'s turn")

    # determine if it's a computer's move
    if (
        AUTO_PLAY
        or (color == "White" and not HUMAN_PLAYS_WHITE)
        or (color == "Black" and HUMAN_PLAYS_WHITE)
    ):
        # pick the correct engine to play
        if board_item.chess_board.turn == chess.WHITE:
            engine = white_engine
        else:
            engine = black_engine
        # get the move from stockfish
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        move_uci = result.move.uci()
        # show the move
        print(f"{color} (Stockfish) plays: {move_uci}")
    # if it's not a computer move then it's a human move
    else:
        while True:
            # get user input move
            move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()

            # uci moves must be 4 or 5 characters
            if len(move_uci) not in (4, 5):
                print("Invalid format. Use format like e2e4 or e7e8q.")
                # if wrong length try again
                continue

            try:
                # try to parse the move python chess
                move = chess.Move.from_uci(move_uci)
            except ValueError:
                # if it's wrong notation try again
                print("Invalid notation. Try again.")
                continue

            # check move legality, if illegal try again
            if move not in board_item.chess_board.legal_moves:
                print("Illegal move. Try again.")
                continue

            # if good move, break out of the loop, otherwise try again
            break

    # check to see if a promotion is involved and get the promotion piece
    promotion = None
    if len(move_uci) == 5:
        promotion = move_uci[-1]
        move_uci = move_uci[:4]

    # plan the move path
    move_path = board_item.plan_path(move_uci, promotion=promotion)
    if SHOW_PATHS:
        # display the path if desired
        board_item.display_paths(move_path)

    # generate the gcode for the move
    gcode_str = BoardItem.generate_gcode(move_path)
    lines = gcode_str.splitlines()

    # execute the move by sending gcode
    for i, line in enumerate(lines):
        next_line = lines[i+1] if i+1 < len(lines) else None
        send_gcode_line(line, next_line)

    # update the internal board state
    board_item.move_piece(move_uci, promotion=promotion)
    board_item.display_board()
    # update the turn
    turn += 1
    time.sleep(TURN_DELAY)

# clean up once game is over
print("\nGame over")
print("Result:", board_item.chess_board.result())

# ask user if they want to reset the board
resp = input("\nWould you like to reset the board to the starting position? (y/n): ").strip().lower()
if resp == "y":
    print("Resetting board...")
    #board_item.reset_board()   # you implement this method inside BoardItem
else:
    print("Board will not be reset.")

# shut down engines + hardware
if white_engine:
    white_engine.quit()
if black_engine:
    black_engine.quit()

arduino.close()
servo_neutral()
pi.stop()

