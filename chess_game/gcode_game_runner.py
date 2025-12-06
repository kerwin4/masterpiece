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
STOCKFISH_PATH = "/home/chess/stockfish/stockfish-android-armv8" # path to stockfish engine, for pi: /home/chess/stockfish/stockfish-android-armv8
ENGINE_TIME = 0.1 # amount of time stockfish has to make a decision
TURN_DELAY = 0.5 # added delay to prevent runaway memory
SHOW_PATHS = True # display planned paths if True

SERVO_PIN = 17  # gpio pin for the servo
SERIAL_PORT = "/dev/ttyACM0" # port for serial cable to arduino
BAUD_RATE = 115200 # GRBL communication rate (MUST BE 115200)

# USER INPUT GAME CONFIG
def ask_int(prompt, min_val=0, max_val=20):
    """Ask for an integer in a valid range, re-prompt until valid."""
    while True:
        val = input(prompt).strip()
        if val.isdigit():
            val = int(val)
            if min_val <= val <= max_val:
                return val
        print(f"Please enter a number between {min_val} and {max_val}.")

def ask_choice(prompt, choices):
    """Ask for a choice from a list, re-prompt until valid."""
    choices_lower = {c.lower(): c for c in choices}
    while True:
        val = input(prompt).strip().lower()
        if val in choices_lower:
            return choices_lower[val]
        print("Invalid choice. Options are:", ", ".join(choices))

# choose game mode
mode = ask_choice(
    "\nSelect mode:\n"
    "  1 = Human vs Computer\n"
    "  2 = Computer vs Computer\n"
    "Enter choice: ",
    ["1", "2"]
)

if mode == "2":
    AUTO_PLAY = True
    HUMAN_PLAYS_WHITE = False
    print("\nComputer vs Computer selected.")

    WHITE_SKILL = ask_int("Enter White engine skill level (0-20): ")
    BLACK_SKILL = ask_int("Enter Black engine skill level (0-20): ")

else:
    AUTO_PLAY = False
    print("\nHuman vs Computer selected.")

    color_choice = ask_choice(
        "Do you want to play as White or Black? ",
        ["White", "Black"]
    )
    HUMAN_PLAYS_WHITE = (color_choice == "White")

    if HUMAN_PLAYS_WHITE:
        WHITE_SKILL = None  # Human
        BLACK_SKILL = ask_int("Enter Computer (Black) skill level (0-20): ")
    else:
        BLACK_SKILL = None  # Human
        WHITE_SKILL = ask_int("Enter Computer (White) skill level (0-20): ")

print("\nConfiguration complete:")
print(" Computer vs computer?", AUTO_PLAY)
print(" Human plays white?", HUMAN_PLAYS_WHITE)
print(" White computer skill:", WHITE_SKILL)
print(" Black computer skill:", BLACK_SKILL)

# === Initialize pigpio servo ===
pi = pigpio.pi()
if not pi.connected:
    raise RuntimeError("pigpiod broken")

def servo_up():
    print("[PI] Servo up")
    pi.set_servo_pulsewidth(SERVO_PIN, 1300)
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

servo_down()
arduino.write(b"$H\n")      # Home axes
wait_for_ok()

arduino.write(b"G92 X0 Y0\n")  # Zero coordinates
wait_for_ok()

arduino.write(b"G20 G90\n")    # Inches + absolute mode
wait_for_ok()


# ---------------------------------------------------------
#   GRBL Real-time Status Polling
# ---------------------------------------------------------
def wait_until_idle(timeout=60.0):
    start_time = time.time()
    while True:
        arduino.reset_input_buffer()
        arduino.write(b"?\n")
        time.sleep(0.1)

        while arduino.in_waiting:
            status = arduino.readline().decode().strip()
            if "Idle" in status:
                return

        if time.time() - start_time > timeout:
            raise TimeoutError("GRBL did not become idle in time")


# ---------------------------------------------------------
#   Send G-code or Servo Commands (LOOK-AHEAD LOGIC)
# ---------------------------------------------------------
def send_gcode_line(line, next_line=None):
    """
    Only wait for idle if the NEXT line is a servo command.
    """
    line = line.strip()
    if not line:
        return

    # ----------------------------
    # Direct servo commands
    # ----------------------------
    if line == "servo_up":
        wait_until_idle()
        servo_up()
        return

    if line == "servo_down":
        wait_until_idle()
        servo_down()
        return

    # ----------------------------
    # G-code lines
    # ----------------------------
    arduino.write((line + "\n").encode("utf-8"))

    # Wait only for "ok" (line accepted to buffer)
    while True:
        resp = arduino.readline().decode().strip()
        if resp == "ok":
            break
        elif resp:
            print("[GRBL]", resp)

    # Look ahead — if next command is a servo move, ensure motion is done
    if next_line in ("servo_up", "servo_down"):
        wait_until_idle()


# ---------------------------------------------------------
#   Game Setup
# ---------------------------------------------------------
board_item = BoardItem()
board_item.display_board()
board_item.display_state()
board_item.display_nodes()

# ---------------------------------------------------------
#   Engine Setup (only create what is needed)
# ---------------------------------------------------------

white_engine = None
black_engine = None

if AUTO_PLAY:
    # Computer vs Computer ? both engines needed
    white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    white_engine.configure({"Skill Level": WHITE_SKILL})
    black_engine.configure({"Skill Level": BLACK_SKILL})

else:
    # Human vs Computer ? only one engine needed
    if HUMAN_PLAYS_WHITE:
        # Human = white, Computer = black
        black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        black_engine.configure({"Skill Level": BLACK_SKILL})
    else:
        # Human = black, Computer = white
        white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        white_engine.configure({"Skill Level": WHITE_SKILL})



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
        if board_item.chess_board.turn == chess.WHITE:
            engine = white_engine
        else:
            engine = black_engine
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        move_uci = result.move.uci()
        print(f"{color} (Stockfish) plays: {move_uci}")
    else:
        # --- Get human move safely ---
        while True:
            move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()

            # Basic length check (4 or 5 chars)
            if len(move_uci) not in (4, 5):
                print("Invalid format. Use format like e2e4 or e7e8q.")
                continue

            try:
                # Try to parse the move
                move = chess.Move.from_uci(move_uci)
            except ValueError:
                print("Invalid notation. Try again.")
                continue

            # Check legality
            if move not in board_item.chess_board.legal_moves:
                print("Illegal move. Try again.")
                continue

            # If good: break
            break

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
    lines = gcode_str.splitlines()

    # Execute using look-ahead idle logic
    for i, line in enumerate(lines):
        next_line = lines[i+1] if i+1 < len(lines) else None
        send_gcode_line(line, next_line)

    # Update internal board state
    board_item.move_piece(move_uci, promotion=promotion)
    board_item.display_board()

    turn += 1
    time.sleep(TURN_DELAY)


# ---------------------------------------------------------
#   Cleanup
# ---------------------------------------------------------
print("\nGame over")
print("Result:", board_item.chess_board.result())
white_engine.quit()
black_engine.quit()
arduino.close()
pi.stop()
