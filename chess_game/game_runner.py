"""
Software testing for human vs computer chess board control.
"""

from board_item import BoardItem
import chess.engine
import time
import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer, SetLogLevel

MODEL_PATH = "vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000

PROMOTION_MAP = {
    "queen": "q",
    "rook": "r",
    "bishop": "b",
    "knight": "n",
}

LETTER_MAP = {
    "a": "a", "b": "b", "c": "c", "d": "d",
    "e": "e", "f": "f", "g": "g", "h": "h"
}

NUMBER_MAP = {
    "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "fiv": "5", "six": "6", "seven": "7",
    "seve": "7", "sev": "7", "eig": "8", "eigh": "8",
    "eight": "8"
}

def filter_number_tokens(tokens):
    skip_next = False
    filtered = []

    for t in tokens:
        t = t.lower()

        if skip_next:
            skip_next = False
            continue

        filtered.append(t)

        if t in ("fiv", "sev", "seve", "eig"):
            skip_next = True

    return filtered

def extract_square(tokens, i):
    if i + 1 >= len(tokens):
        return None

    file = LETTER_MAP.get(tokens[i].lower())
    rank = NUMBER_MAP.get(tokens[i + 1].lower())

    if file and rank:
        return file + rank
    return None

def speech_to_uci(text):
    tokens = text.lower().split()
    tokens = [t for t in tokens if t != "to"]
    tokens = filter_number_tokens(tokens)

    squares = []
    i = 0

    while i < len(tokens) - 1 and len(squares) < 2:
        sq = extract_square(tokens, i)
        if sq:
            squares.append(sq)
            i += 2
        else:
            i += 1

    if len(squares) != 2:
        return None

    move = squares[0] + squares[1]

    # Optional promotion piece after destination square
    if i < len(tokens):
        promo = PROMOTION_MAP.get(tokens[i])
        if promo:
            move += promo

    return move

def listen_for_valid_move(board, model, grammar_file="chess_grammar.json"):
    """
    Keep listening until a legal move is spoken.
    Returns legal UCI string.
    """
    SetLogLevel(-1)

    with open(grammar_file) as f:
        grammar_list = json.load(f)

    recognizer = KaldiRecognizer(
        model,
        SAMPLE_RATE,
        json.dumps(grammar_list)
    )

    q = queue.Queue()

    def audio_callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(bytes(indata))

    while True:
        print("Speak your move...")

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=2000,
            dtype="int16",
            channels=1,
            callback=audio_callback
        ):
            while True:
                data = q.get()

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")

                    if not text:
                        continue

                    print("Heard:", text)

                    uci = speech_to_uci(text)

                    if not uci:
                        print("Could not parse move. Try again.")
                        break

                    try:
                        move = board.parse_uci(uci)
                    except ValueError:
                        print("Invalid move format. Try again.")
                        break

                    if move in board.legal_moves:
                        print("Accepted:", uci)
                        return uci
                    else:
                        print("Illegal move. Try again.")
                        break

# GAME CONFIGURATION
STOCKFISH_PATH = "stockfish-windows-x86-64-avx2.exe"  # stockfish path for pi: /home/stockfish/stockfish/stockfish-android-armv8 for windows: stockfish-windows-x86-64-avx2.exe
ENGINE_TIME = 0.5 # seconds for stockfish to choose
TURN_DELAY = 0 # delay between computer turns
WHITE_SKILL = 20 # stockfish skill white
BLACK_SKILL = 0 # stockfish skill black
SHOW_PATHS = False # show/hide path planning
AUTO_PLAY = False # if true, play computer vs computer

# BOARD SETUP
board_item = BoardItem() # create board item
board_item.display_state() # show all 3 initial visualizations
board_item.display_nodes()
board_item.display_board()

# ENGINE SETUP
white_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
black_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
white_engine.configure({"Skill Level": WHITE_SKILL})
black_engine.configure({"Skill Level": BLACK_SKILL})
speech_model = Model(MODEL_PATH)

# GAME LOOP
# keep track of turns
turn = 0
# while the game isn't over
while not board_item.chess_board.is_game_over():
    # determine whose turn it is and display that
    if board_item.chess_board.turn == chess.WHITE:
        color = "White" 
    else:
        color = "Black"
    print(f"\n[{turn}] {color}'s turn")

    if AUTO_PLAY or color == "Black":  # stockfish turn
        # pick which engine is playing
        if board_item.chess_board.turn == chess.WHITE:
            engine = white_engine 
        else:
            engine = black_engine
        # pass the current board to the engine to get the move
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        # get the move in UCI notation
        move_uci = result.move.uci()
        print(f"{color} (Stockfish) plays: {move_uci}") # show stockfish move

        # path plan and display computer move
        move_path = board_item.plan_path(move_uci)
        if SHOW_PATHS:
            print(move_path)
            print(f"{color} move path:")
            board_item.display_paths(move_path)
        # generate the corresponding gcode for the move
        gcode_str = BoardItem.generate_gcode(move_path)
        print(f"G-code for {color}:")
        print(gcode_str)

    else:
        # human move
        move_uci = listen_for_valid_move(board_item.chess_board, speech_model)

    # show the board states post-move
    # make the move
    board_item.move_piece(move_uci)
    # visualize
    board_item.display_state()
    board_item.display_nodes()
    board_item.display_board()

    # pause so I can check if promotions work
    #if promotion is not None:
    #    print(f"Promotion occurred! Pausing for 20 seconds...")
    #    time.sleep(20)

    # delay if desired
    time.sleep(TURN_DELAY)
    turn += 1

# game over conditions
print("\nGame over!")
print("Result:", board_item.chess_board.result())

# quit engines cleanly
white_engine.quit()
black_engine.quit()
#stuff = board_item.reset_board_physical()
#print(stuff)