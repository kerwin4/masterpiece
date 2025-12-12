"""
Software testing for human vs computer chess board control.
"""

from board_item import BoardItem
import chess.engine
import time

# GAME CONFIGURATION
STOCKFISH_PATH = "stockfish-windows-x86-64-avx2.exe"  # stockfish path for pi: /home/stockfish/stockfish/stockfish-android-armv8 for windows: stockfish-windows-x86-64-avx2.exe
ENGINE_TIME = 0.1 # seconds for stockfish to choose
TURN_DELAY = 0 # delay between computer turns
WHITE_SKILL = 20 # stockfish skill white
BLACK_SKILL = 0 # stockfish skill black
SHOW_PATHS = True # show/hide path planning
AUTO_PLAY = True # if true, play computer vs computer

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
        move_uci = input("Enter your move (UCI notation like e2e4): ").strip()

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
stuff = board_item.reset_board_physical()
print(stuff)
