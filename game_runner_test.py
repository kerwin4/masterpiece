from board_item_test import BoardItem
import chess.engine
import time

# CONFIGURE GAME
STOCKFISH_PATH = "stockfish-windows-x86-64-avx2.exe"  # stockfish path
ENGINE_TIME = 0.1        # seconds for stockfish to choose
TURN_DELAY = 0         # delay between computer turns
WHITE_SKILL = 15          # stockfish skill white
BLACK_SKILL = 10         # stockfish skill black
SHOW_PATHS = True        # show/hide path planning
AUTO_PLAY = True         # if true, play computer vs computer

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
turn = 0
while not board_item.chess_board.is_game_over():
    color = "White" if board_item.chess_board.turn == chess.WHITE else "Black"
    print(f"\n[{turn}] {color}'s turn")

    if AUTO_PLAY or color == "Black":  # stockfish turn
        engine = white_engine if board_item.chess_board.turn == chess.WHITE else black_engine
        result = engine.play(board_item.chess_board, chess.engine.Limit(time=ENGINE_TIME))
        move_uci = result.move.uci()
        print(f"{color} (Stockfish) plays: {move_uci}") # show stockfish move

        promotion = None # promotion placeholder
        if len(move_uci) == 5: # detect if a promotion is being made
            promotion = move_uci[-1]
            move_uci = move_uci[:4]

        # path plan and display computer move
        move_path = board_item.plan_path(move_uci, promotion=promotion)
        if SHOW_PATHS:
            print(move_path)
            print(f"{color} move path:")
            board_item.display_paths(move_path)
        gcode_str = BoardItem.generate_gcode(move_path)
        print(f"G-code for {color}:")
        print(gcode_str)

    else:
        # human move
        move_uci = input("Enter your move (UCI notation like e2e4): ").strip()
        promotion = None
        if len(move_uci) == 5:  # e.g., e7e8q
            promotion = move_uci[-1]
            move_uci = move_uci[:4]

    # show the board states post-move
    board_item.move_piece(move_uci, promotion=promotion)
    board_item.display_state()
    board_item.display_nodes()
    board_item.display_board()

    # pause so I can check if promotions work
    if promotion is not None:
        print(f"Promotion occurred! Pausing for 20 seconds...")
        time.sleep(20)

    # delay if desired
    time.sleep(TURN_DELAY)
    turn += 1

# game over conditions
print("\nGame over!")
print("Result:", board_item.chess_board.result())

# quit engines cleanly
white_engine.quit()
black_engine.quit()
