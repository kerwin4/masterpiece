import chess
import chess.engine
import time
import serial
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from board_item import BoardItem

# ===================== CONFIGURATION =====================
STOCKFISH_PATH = "/home/chess/stockfish/stockfish-android-armv8"  # path to stockfish on Pi
ENGINE_TIME = 0.1
TURN_DELAY = 0.5
WHITE_SKILL = 15
BLACK_SKILL = 10
AUTO_PLAY = True          # True = computer vs computer
HUMAN_PLAYS_WHITE = True  # if False, human plays black
SHOW_PATHS = True

SERIAL_PORT = "/dev/ttyACM0"  # Pi: /dev/ttyACM0
BAUD_RATE = 115200
SERVO_PIN = 13                # GPIO pin connected to servo signal wire
# ==========================================================

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

# === Initialize GRBL Serial Connection ===
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # allow GRBL to initialize
arduino.reset_input_buffer()

# === Send homing and G20 G90 on startup ===
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


def send_gcode_line(line):
    """Send one G-code line to Arduino and wait for 'ok'."""
    line = line.strip()
    if not line:
        return
    # Servo commands handled directly by Pi
    if line == "servo_up":
        #servo_up()
        print("[PI] Servo up")
        return
    elif line == "servo_down":
        #servo_down()
        print("[PI] Servo down")
        return

    # Send G-code to GRBL
    arduino.write((line + "\n").encode("utf-8"))
    while True:
        response = arduino.readline().decode("utf-8").strip()
        if response == "ok":
            break
        elif response:
            print(f"[GRBL] {response}")

# === Initialize chess board and engines ===
board_item = BoardItem()
board_item.display_board()
board_item.display_state()
board_item.display_nodes()

white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
white_engine.configure({"Skill Level": WHITE_SKILL})
black_engine.configure({"Skill Level": BLACK_SKILL})

# === Main game loop ===
turn = 0
try:
    while not board_item.chess_board.is_game_over():
        color = "White" if board_item.chess_board.turn == chess.WHITE else "Black"
        print(f"\n[{turn}] {color}'s turn")

        # Decide if human or computer moves
        if AUTO_PLAY or (color == "White" and not HUMAN_PLAYS_WHITE) or (color == "Black" and HUMAN_PLAYS_WHITE):
            engine = white_engine if board_item.chess_board.turn == chess.WHITE else black_engine
            result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
            move_uci = result.move.uci()
            print(f"{color} (Stockfish) plays: {move_uci}")
        else:
            move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()

        promotion = None
        if len(move_uci) == 5:
            promotion = move_uci[-1]
            move_uci = move_uci[:4]

        # Plan the move path
        move_path = board_item.plan_path(move_uci, promotion=promotion)
        if SHOW_PATHS:
            board_item.display_paths(move_path)

        # Generate G-code and send
        gcode_str = BoardItem.generate_gcode(move_path)
        for line in gcode_str.splitlines():
            send_gcode_line(line)

        # Update board state
        board_item.move_piece(move_uci, promotion=promotion)
        board_item.display_board()

        turn += 1
        time.sleep(TURN_DELAY)

finally:
    print("\nGame over or interrupted. Cleaning up...")
    white_engine.quit()
    black_engine.quit()
    arduino.close()
    #servo_neutral()
