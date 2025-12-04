"""
Full game control for computer vs computer physical chess board.
"""

import chess
import chess.engine
import time
import serial
from board_item import BoardItem

# CONFIGURE EVERYTHING
STOCKFISH_PATH = "/home/chess/stockfish/stockfish-android-armv8"  # path to stockfish on Pi
ENGINE_TIME = 0.1 # how much time the chess engine has to determine a move
TURN_DELAY = 0.5 # added delay between turns
WHITE_SKILL = 15 # skill for the white engine
BLACK_SKILL = 10 # skill for the black engine
AUTO_PLAY = True # True = computer vs computer
HUMAN_PLAYS_WHITE = True # if False, human plays black
SHOW_PATHS = True # True = visualizations of board are shown in terminal

SERIAL_PORT = "/dev/ttyACM0"  # Pi: /dev/ttyACM0
BAUD_RATE = 115200            # MUST BE 115200!!!
SERVO_PIN = 13                # GPIO pin connected to servo signal wire

# === Initialize pigpio servo ===
#factory = PiGPIOFactory()
#servo = Servo(SERVO_PIN, pin_factory=factory, min_pulse_width=0.0005, max_pulse_width=0.0025)

'''
def servo_up():
    servo.value = 0.75  # adjust based on your physical setup
    time.sleep(0.5)

def servo_down():
    servo.value = -0.75
    time.sleep(0.5)

def servo_neutral():
    servo.value = 0
    time.sleep(0.5)
'''

# connect to arduino over serial
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # allow GRBL to initialize before sending commands
arduino.reset_input_buffer()

# send homing, zeroing, and G20 G90 on startup
arduino.write(b"$H\n")
while True:
    resp = arduino.readline().decode("utf-8").strip()
    if resp == "ok":
        break
    elif resp:
        print(f"[GRBL INIT] {resp}")

arduino.write(b"G92 X0 Y0\n")
while True:
    resp = arduino.readline().decode("utf-8").strip()
    if resp == "ok":
        break
    elif resp:
        print(f"[GRBL INIT] {resp}")

arduino.write(b"G20 G90\n")
while True:
    resp = arduino.readline().decode("utf-8").strip()
    if resp == "ok":
        break
    elif resp:
        print(f"[GRBL INIT] {resp}")

# function to send each line of gcode or move the servo
def send_gcode_line(line):
    """
    Send a single G-code command to an Arduino running GRBL and wait for 'ok' acknowledgment.

    This function handles both standard G-code commands and special
    servo commands directly on the Raspberry Pi.

    Args:
        line (str): A single G-code command or a servo instruction

    Returns:
        None
    """
    line = line.strip()
    if not line:
        return
    # servo commands handled directly by Pi
    if line == "servo_up":
        #servo_up()
        print("[PI] Servo up")
        return
    elif line == "servo_down":
        #servo_down()
        print("[PI] Servo down")
        return

    # send line to GRBL over serial
    arduino.write((line + "\n").encode("utf-8"))
    # wait for ok before continuing
    while True:
        response = arduino.readline().decode("utf-8").strip()
        if response == "ok":
            break
        elif response:
            print(f"[GRBL] {response}")

# set up the game in the class
board_item = BoardItem()
# show starting visualizations
board_item.display_board()
board_item.display_state()
board_item.display_nodes()

# set up chess engines
white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
white_engine.configure({"Skill Level": WHITE_SKILL})
black_engine.configure({"Skill Level": BLACK_SKILL})

# main game loop
turn = 0
while not board_item.chess_board.is_game_over():
    # determine whose turn it is
    if board_item.chess_board.turn == chess.WHITE:
        color = "White" 
    else:
        color = "Black"
    print(f"\n[{turn}] {color}'s turn")

    # decide if human or computer moves
    if (
        AUTO_PLAY 
        or (color == "White" and not HUMAN_PLAYS_WHITE) 
        or (color == "Black" and HUMAN_PLAYS_WHITE)
    ):
        # determine which engine to use
        if board_item.chess_board.turn == chess.WHITE:
            engine = white_engine 
        else:
            engine = black_engine
        # get the computer move
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        # get the move as UCI
        move_uci = result.move.uci()
        print(f"{color} (Stockfish) plays: {move_uci}")
    else:
        # human input if human is playing
        move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()
    # determine if the move involves a promotion based on number of characters
    promotion = None
    if len(move_uci) == 5:
        promotion = move_uci[-1]
        move_uci = move_uci[:4]

    # plan the move path
    move_path = board_item.plan_path(move_uci, promotion=promotion)
    if SHOW_PATHS:
        board_item.display_paths(move_path)

    # generate G-code and send one line at a time
    gcode_str = BoardItem.generate_gcode(move_path)
    for line in gcode_str.splitlines():
        send_gcode_line(line)

    # update board state
    board_item.move_piece(move_uci, promotion=promotion)
    board_item.display_board()

    turn += 1
    time.sleep(TURN_DELAY)

# clean up once game is done
print("\nGame over")
white_engine.quit()
black_engine.quit()
arduino.close()
#servo_neutral()
