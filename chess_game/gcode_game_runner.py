"""
Full game control for computer vs computer physical chess board.
"""

import chess
import chess.engine
import time
import serial
import pigpio
from board_item import BoardItem

# CONFIGURE EVERYTHING
STOCKFISH_PATH = "/home/chess/stockfish/stockfish-android-armv8"
ENGINE_TIME = 0.1
TURN_DELAY = 0.5
WHITE_SKILL = 15
BLACK_SKILL = 10
AUTO_PLAY = True
HUMAN_PLAYS_WHITE = True
SHOW_PATHS = True

SERVO_PIN = 17  # GPIO pin for the servo
SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200

# === Initialize pigpio servo ===
pi = pigpio.pi()
if not pi.connected:
    raise RuntimeError("pigpiod broken")

def servo_up():
    print("[PI] Servo up")
    pi.set_servo_pulsewidth(SERVO_PIN, 1000)
    time.sleep(0.4)

def servo_down():
    print("[PI] Servo down")
    pi.set_servo_pulsewidth(SERVO_PIN, 1900)
    time.sleep(0.4)

def servo_neutral():
    pi.set_servo_pulsewidth(SERVO_PIN, 0)


# === Connect to GRBL ===
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)
arduino.reset_input_buffer()


# ---------------------------------------------------------
#   GRBL Initialization
# ---------------------------------------------------------
def wait_for_ok():
    while True:
        resp = arduino.readline().decode("utf-8").strip()
        if resp == "ok":
            return
        elif resp:
            print(f"[GRBL INIT] {resp}")

arduino.write(b"$H\n")      # Home axes
wait_for_ok()

arduino.write(b"G92 X0 Y0\n")  # Zero coordinates
wait_for_ok()

arduino.write(b"G20 G90\n")    # Set units to inches & absolute mode
wait_for_ok()


# ---------------------------------------------------------
#   GRBL Real-time Status Polling
# ---------------------------------------------------------
def wait_until_idle(timeout=30.0):
    """
    Poll GRBL until machine is idle or timeout is reached.
    """
    start_time = time.time()
    while True:
        arduino.reset_input_buffer()
        arduino.write(b"?\n")
        time.sleep(0.05)  # short delay for GRBL to respond

        while arduino.in_waiting:
            status = arduino.readline().decode("utf-8").strip()
            if status.startswith("<Idle"):
                return
            # Optional: you could also check for <Run|...> if needed

        if time.time() - start_time > timeout:
            raise TimeoutError("GRBL did not become idle in time")

# ---------------------------------------------------------
#   Send G-code or Servo Commands
# ---------------------------------------------------------
def send_gcode_line(line):
    """
    Send one G-code line or handle a servo command.
    Only proceeds to the next line when the machine is idle.
    """
    line = line.strip()
    print(line)
    if not line:
        return

    # Servo commands handled in Python
    if line == "servo_up":
        wait_until_idle()
        servo_up()
        return
    elif line == "servo_down":
        wait_until_idle()
        servo_down()
        return

    # Send normal G-code line
    arduino.write((line + "\n").encode("utf-8"))

    # Wait until the motion is finished
    wait_until_idle()


# ---------------------------------------------------------
#   Game Setup
# ---------------------------------------------------------
board_item = BoardItem()
board_item.display_board()
board_item.display_state()
board_item.display_nodes()

white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

white_engine.configure({"Skill Level": WHITE_SKILL})
black_engine.configure({"Skill Level": BLACK_SKILL})


# ---------------------------------------------------------
#   Main Game Loop
# ---------------------------------------------------------
turn = 0
while not board_item.chess_board.is_game_over():

    color = "White" if board_item.chess_board.turn == chess.WHITE else "Black"
    print(f"\n[{turn}] {color}'s turn")

    # Choose engine or human
    if (
        AUTO_PLAY
        or (color == "White" and not HUMAN_PLAYS_WHITE)
        or (color == "Black" and HUMAN_PLAYS_WHITE)
    ):
        engine = white_engine if board_item.chess_board.turn == chess.WHITE else black_engine
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        move_uci = result.move.uci()
        print(f"{color} (Stockfish) plays: {move_uci}")
    else:
        move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()

    # Promotion check
    promotion = None
    if len(move_uci) == 5:
        promotion = move_uci[-1]
        move_uci = move_uci[:4]

    # Plan the move path
    move_path = board_item.plan_path(move_uci, promotion=promotion)
    if SHOW_PATHS:
        board_item.display_paths(move_path)

    # Generate G-code
    gcode_str = BoardItem.generate_gcode(move_path)

    # Execute line by line with real-time status check
    for line in gcode_str.splitlines():
        send_gcode_line(line)

    # Update internal board state
    board_item.move_piece(move_uci, promotion=promotion)
    board_item.display_board()

    turn += 1
    time.sleep(TURN_DELAY)


# ---------------------------------------------------------
#   Cleanup
# ---------------------------------------------------------
print("\nGame over")
white_engine.quit()
black_engine.quit()
arduino.close()
pi.stop()
