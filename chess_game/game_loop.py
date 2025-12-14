"""
Full game control for physical gantry chess board.
"""

import chess
import chess.engine
import time
import serial
import pigpio
from subprocess import Popen, PIPE
from board_item import BoardItem, PremadeGameMode

# GENERAL CONFIGURATION
STOCKFISH_PATH = "/home/chess/stockfish/stockfish-android-armv8" # path to stockfish engine, for pi: /home/chess/stockfish/stockfish-android-armv8
ENGINE_TIME = 0.2 # amount of time stockfish has to make a decision
TURN_DELAY = 0 # added delay to prevent runaway memory if desired
SHOW_PATHS = True # display planned paths if True

SERVO_PIN = 17  # gpio pin for the servo
SERIAL_PORT = "/dev/ttyACM0" # port for serial cable to arduino
BAUD_RATE = 115200 # GRBL communication rate (MUST BE 115200)

# PI GPIO DAEMON
def start_pigpio_daemon():
    """
    Starts the pigpio daemon if it's not already running.

    Returns:
        None
    """
    p = Popen("sudo pigpiod", stdout=PIPE, stderr=PIPE, shell=True)
    s_out, s_err = p.communicate()  # use communicate to wait for process and get output

    if not s_out and not s_err:
        print("pigpiod started")
    elif b"pigpio.pid" in s_err:
        print("pigpiod already running")
    else:
        print(f"error pigpiod {s_err.decode()}")
    
def stop_pigpio_daemon():
    """
    Stops the pigpio daemon if it's running.

    Returns:
        None
    """
    # attempt to stop gracefully
    p = Popen("sudo killall pigpiod", stdout=PIPE, stderr=PIPE, shell=True)
    _, s_err = p.communicate()

    # check to see what happened
    if p.returncode == 0:
        print("pigpiod stopped")
    elif p.returncode == 1:
        print("pigpiod was not running")
    else:
        print(f"error stopping pigpiod: {s_err.decode()}")

# USER INPUT GAME CONFIG
def ask_int(prompt, min_val=1350, max_val=3190):
    """
    Prompt the user to enter an integer within a specified range.
    Repeats the prompt until a valid integer within the provided range is entered.
    Primarily used for determining stockfish ELO.

    Args:
        prompt (str): the message to display to the user
        min_val (int): minimum valid value, defaults to 1350
        max_val (int): maximum valid value, defaults to 3190

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
        prompt (str): the message to display to the user
        choices (list[str]): list of valid choices

    Returns:
        str: the choice selected by the user, returned in its original casing
    """
    choices_lower = {c.lower(): c for c in choices} # make everything lowercase
    while True:
        val = input(prompt).strip().lower() # get input from the user
        if val in choices_lower: # if the input is valid
            return choices_lower[val] # return it
        print("Invalid choice. Options are:", ", ".join(choices)) # otherwise reprompt the user for new input

# SERVO COMMAND FUNCTIONS
def servo_up(pi):
    """
    Move the servo to the "up" position.
    Sends the appropriate PWM signal to the configured GPIO pin and waits 0.4s
    for motion to complete.

    Args:
        pi (pigpio.pi): raspberry pi gpio controller for servo control

    Returns:
        None
    """
    pi.set_servo_pulsewidth(SERVO_PIN, 1250)
    time.sleep(0.4)

def servo_down(pi):
    """
    Move the servo to the "down" position.
    Sends the appropriate PWM signal to the configured GPIO pin and waits 0.4s
    for motion to complete.

    Args:
        pi (pigpio.pi): raspberry pi gpio controller for servo control

    Returns:
        None
    """
    pi.set_servo_pulsewidth(SERVO_PIN, 1900)
    time.sleep(0.4)

def servo_neutral(pi):
    """
    Stop sending PWM signals to the servo.
    Sets the servo to neutral/off state.

    Args:
        pi (pigpio.pi): raspberry pi gpio controller for servo control
    
    Returns:
        None
    """
    pi.set_servo_pulsewidth(SERVO_PIN, 0)

# GRBL queues moves if it receives them faster than it's executing them,
# so this function only confirms that a line has been added to the queue
def wait_for_ok(arduino):
    """
    Wait for a response of 'ok' from the GRBL controller.
    Continuously reads serial lines from the Arduino until 'ok' is received.
    Any other responses are printed for informational purposes.

    Args:
        arduino (serial.Serial): serial connection to arduino/grbl for gantry control

    Returns:
        None
    """
    while True:
        resp = arduino.readline().decode("utf-8").strip()
        if resp == "ok":
            return
        elif resp:
            print(f"[GRBL INIT] {resp}")

# servo synchronization function
# since the servo is controlled by the pi but the gantry is controlled
# by the arduino, we need to move the servo at the right moments.
# By waiting until a sequence of moves is completed and the gantry is idle,
# we can guarantee the servo moves at the right time
def wait_until_idle(arduino, timeout=60.0):
    """
    Wait until the grbl controller reports that it is idle.

    Args:
        arduino (serial.Serial): serial connection to arduino/grbl for gantry control
        timeout (float): maximum number of seconds to wait, raises timeout error if exceeded, defaults to 60.0

    Raises:
        TimeoutError: if grbl does not become idle within "timeout" seconds
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
def send_gcode_line(line, arduino, pi, next_line=None):
    """
    Send a single line of gcode from the pi to the arduino.
    If the next line is a servo command, wait for the gantry to become idle before moving on.

    Args:
        line (str): the line of gcode to send to grbl
        pi (pigpio.pi): raspberry pi gpio controller for servo control
        arduino (serial.Serial): serial connection to arduino/grbl for gantry control
        next_line (str): the next line of gcode that will be sent to grbl

    Returns:
        None
    """
    line = line.strip()
    if not line:
        return

    # servo control functions
    if line == "servo_up":
        wait_until_idle(arduino)
        servo_up(pi)
        return

    if line == "servo_down":
        wait_until_idle(arduino)
        servo_down(pi)
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
        wait_until_idle(arduino)

def run_game(pi, arduino):
    """
    Run a full round of chess configured by user input

    Args:
        pi (pigpio.pi): raspberry pi gpio controller for servo control
        arduino (serial.Serial): serial connection to arduino/grbl for gantry control

    Returns:
        None
    """
    arduino.reset_input_buffer()
    board_item = BoardItem()

    # choose game mode
    mode = ask_choice(
        "\nSelect mode:\n"
        "  1 = Human vs Computer\n"
        "  2 = Computer vs Computer\n"
        "  3 = Human vs Human\n"
        "  4 = Deterministic short game\n"
        "Enter choice: ",
        ["1", "2", "3", "4"]
    )

    # configuration flags
    AUTO_PLAY = False
    HUMAN_PLAYS_WHITE = True
    HUMAN_VS_HUMAN = False
    WHITE_SKILL = None
    BLACK_SKILL = None

    # configure modes
    if mode == "2":
        AUTO_PLAY = True
        HUMAN_PLAYS_WHITE = False
        print("\nComputer vs Computer selected.")
        WHITE_SKILL = ask_int("Enter White engine skill level (1350-3190): ")
        BLACK_SKILL = ask_int("Enter Black engine skill level (1350-3190): ")
    elif mode == "1":
        print("\nHuman vs Computer selected.")
        color_choice = ask_choice("Do you want to play as White or Black? ", ["White", "Black"])
        HUMAN_PLAYS_WHITE = (color_choice == "White")
        if HUMAN_PLAYS_WHITE:
            BLACK_SKILL = ask_int("Enter Computer (Black) skill level (1350-3190): ")
        else:
            WHITE_SKILL = ask_int("Enter Computer (White) skill level (1350-3190): ")
    elif mode == "4":
        game_mode = PremadeGameMode(board_item, arduino, pi)
        turn = 1
        # start gantry setup
        servo_down(pi)
        arduino.write(b"$H\n")
        wait_for_ok(arduino)
        arduino.write(b"G92 X0 Y0\n")
        wait_for_ok(arduino)
        arduino.write(b"G20 G90\n")
        wait_for_ok(arduino)
        while game_mode.play_next_move(send_gcode_line):
            print(f"[{turn}] Deterministic move played")
            board_item.display_board()
            turn += 1
            time.sleep(TURN_DELAY)

    else:
        print("\nHuman vs Human selected.")
        HUMAN_VS_HUMAN = True

    # display configuration
    print("\nConfiguration complete:")
    print(" Computer vs computer?", AUTO_PLAY)
    print(" Human vs Human?", HUMAN_VS_HUMAN)
    print(" Human plays white?", HUMAN_PLAYS_WHITE)
    print(" White computer skill:", WHITE_SKILL)
    print(" Black computer skill:", BLACK_SKILL)

    # start gantry setup
    servo_down(pi)
    arduino.write(b"$H\n")
    wait_for_ok(arduino)
    arduino.write(b"G92 X0 Y0\n")
    wait_for_ok(arduino)
    arduino.write(b"G20 G90\n")
    wait_for_ok(arduino)

    # display start board
    board_item.display_state()

    # set up chess engines if needed
    white_engine = None
    black_engine = None
    if AUTO_PLAY or (not HUMAN_VS_HUMAN and not HUMAN_PLAYS_WHITE):
        if AUTO_PLAY or not HUMAN_PLAYS_WHITE:
            black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            black_engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": BLACK_SKILL
            })
        if AUTO_PLAY or HUMAN_PLAYS_WHITE == False:
            white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            white_engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": WHITE_SKILL
            })

    # main game loop
    turn = 1
    while not board_item.chess_board.is_game_over():
        color = "White" if board_item.chess_board.turn == chess.WHITE else "Black"
        print(f"\n[{turn}] {color}'s turn")

        # determine move type
        move_uci = None

        if HUMAN_VS_HUMAN:
            # both players are human
            while True:
                move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()
                if len(move_uci) not in (4, 5):
                    print("Invalid format. Use e2e4 or e7e8q.")
                    continue
                try:
                    move = chess.Move.from_uci(move_uci)
                except ValueError:
                    print("Invalid notation. Try again.")
                    continue
                if move not in board_item.chess_board.legal_moves:
                    print("Illegal move. Try again.")
                    continue
                break

        elif AUTO_PLAY or (color == "White" and not HUMAN_PLAYS_WHITE) or (color == "Black" and HUMAN_PLAYS_WHITE):
            # computer move
            engine = white_engine if board_item.chess_board.turn == chess.WHITE else black_engine
            result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
            move_uci = result.move.uci()
            print(f"{color} (Stockfish) plays: {move_uci}")

        else:
            # human move
            while True:
                # get input
                move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()
                # check if the move is in the correct format
                if len(move_uci) not in (4, 5):
                    print("Invalid format. Use e2e4 or e7e8q.")
                    continue
                try:
                    # pass the move to python chess to see if it can be parsed
                    move = chess.Move.from_uci(move_uci)
                except ValueError:
                    print("Invalid notation. Try again.")
                    continue
                # check if the move is legal
                if move not in board_item.chess_board.legal_moves:
                    print("Illegal move. Try again.")
                    continue
                break

        # plan and execute move
        move_path = board_item.plan_path(move_uci)
        # show the path if desired
        if SHOW_PATHS:
            board_item.display_paths(move_path)
        # make the gcode
        gcode_str = BoardItem.generate_gcode(move_path)
        lines = gcode_str.splitlines()
        # send the gcode
        for i, line in enumerate(lines):
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            send_gcode_line(line, arduino, pi, next_line)
        # move the piece for internal tracking
        board_item.move_piece(move_uci)
        # show the board
        board_item.display_board()
        turn += 1
        time.sleep(TURN_DELAY)

    # game over
    print("\nGame over")
    print("Result:", board_item.chess_board.result())
    if white_engine:
        white_engine.quit()
    if black_engine:
        black_engine.quit()

    # board reset option
    resp = input("\nWould you like to reset the board to the starting position? (y/n): ").strip().lower()
    if resp == "y":
        print("Resetting board...")
        gcode = board_item.reset_board_physical()
        lines = gcode.splitlines()
        for i, line in enumerate(lines):
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            send_gcode_line(line, arduino, pi, next_line)
    else:
        print("Board will not be reset.")

def init_hardware():
    """
    Initialize all of the necessary processes to run a game on the board.

    Returns:
        pi (pigpio.pi): raspberry pi gpio controller for servo control
        arduino (serial.Serial): serial connection to arduino/grbl for gantry control
    """

    start_pigpio_daemon()
    time.sleep(1)
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("pigpiod broken")

    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()

    return pi, arduino

def shutdown_hardware(pi, arduino):
    """
    Close all of the processes that were initialized at the beginning of the game

    Args:
        pi (pigpio.pi): raspberry pi gpio controller for servo control
        arduino (serial.Serial): serial connection to arduino/grbl for gantry control

    Returns:
        None
    """

    arduino.close()
    servo_neutral(pi)
    pi.stop()
    stop_pigpio_daemon()