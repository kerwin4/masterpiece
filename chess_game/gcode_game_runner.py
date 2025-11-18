import chess
import chess.engine
import time
import serial
from gpiozero import Servo
from board_item import BoardItem

# ===================== CONFIGURATION =====================
STOCKFISH_PATH = "stockfish-windows-x86-64-avx2.exe"  # stockfish path for pi: /tmp/stockfish/stockfish-android-armv8

ENGINE_TIME = 0.1
TURN_DELAY = 0.5
WHITE_SKILL = 15
BLACK_SKILL = 10
AUTO_PLAY = True          # True = computer vs computer
HUMAN_PLAYS_WHITE = True  # if False, human plays black
SHOW_PATHS = True
SERIAL_PORT = "COM3" # /dev/ttyUSB0 for pi
BAUD_RATE = 115200
SERVO_PIN = 18            # GPIO pin connected to servo signal wire
# ==========================================================


# === Initialize servo ===
servo = Servo(SERVO_PIN)
def servo_up():
    servo.value = -1  # adjust depending on physical setup
    time.sleep(0.5)

def servo_down():
    servo.value = 1
    time.sleep(0.5)


# === Initialize GRBL Serial Connection ===
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # allow GRBL to initialize
arduino.reset_input_buffer()

def send_gcode_line(line):
    """Send one G-code line to Arduino and wait for 'ok'."""
    line = line.strip()
    if not line:
        return
    if line == "servo_up":
        servo_up()
        print("[PI] Servo up")
        return
    elif line == "servo_down":
        servo_down()
        print("[PI] Servo down")
        return

    print(f"[GRBL] Sending: {line}")
    arduino.write((line + "\n").encode("utf-8"))

    # Wait for ok from GRBL
    while True:
        response = arduino.readline().decode("utf-8").strip()
        if response == "ok":
            break
        elif response:
            print(f"[GRBL] {response}")


# === Initialize board and engines ===
board_item = BoardItem()
board_item.display_board()
board_item.display_state()
board_item.display_nodes()

white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
white_engine.configure({"Skill Level": WHITE_SKILL})
black_engine.configure({"Skill Level": BLACK_SKILL})

turn = 0
while not board_item.chess_board.is_game_over():
    color = "White" if board_item.chess_board.turn == chess.WHITE else "Black"
    print(f"\n[{turn}] {color}'s turn")

    # Determine if this is a human or computer move
    if AUTO_PLAY or (color == "White" and not HUMAN_PLAYS_WHITE) or (color == "Black" and HUMAN_PLAYS_WHITE):
        # Stockfish move
        engine = white_engine if board_item.chess_board.turn == chess.WHITE else black_engine
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        move_uci = result.move.uci()
        print(f"{color} (Stockfish) plays: {move_uci}")
    else:
        # Human move
        move_uci = input(f"Enter your move for {color} (e.g., e2e4): ").strip()

    promotion = None
    if len(move_uci) == 5:
        promotion = move_uci[-1]
        move_uci = move_uci[:4]

    # Plan and display the move
    move_path = board_item.plan_path(move_uci, promotion=promotion)
    if SHOW_PATHS:
        board_item.display_paths(move_path)

    # Generate G-code and send to Arduino
    gcode_str = BoardItem.generate_gcode(move_path)
    gcode_lines = gcode_str.splitlines()

    print(f"Executing G-code for {color}...")
    for line in gcode_lines:
        send_gcode_line(line)

    # Apply the move on the chess board
    board_item.move_piece(move_uci, promotion=promotion)
    board_item.display_board()

    # Pause if promotion occurred
    #if promotion is not None:
    #    print("promotion occurred")
    #    time.sleep(5)

    turn += 1
    time.sleep(TURN_DELAY)

# === Game over ===
print("\nGame over!")
print("Result:", board_item.chess_board.result())

white_engine.quit()
black_engine.quit()
arduino.close()
