# imports
from stockfish import Stockfish
import chess
import time

# initialize Stockfish engine
stockfish = Stockfish("stockfish-windows-x86-64-avx2.exe")
stockfish.set_depth(20)
stockfish.set_skill_level(20)

# initialize chess board
board = chess.Board()

# choose mode
mode = input("Mode: (1) You vs Stockfish, (2) Stockfish vs Stockfish: ").strip()
if mode not in ["1", "2"]:
    print("Invalid choice, defaulting to You vs Stockfish.")
    mode = "1"

if mode == "1":
    # ask player color
    player_color = input("Play as White or Black? (w/b): ").strip().lower()
    if player_color not in ["w", "b"]:
        print("Invalid choice, defaulting to White.")
        player_color = "w"

    print("\nStarting position:")
    print(board)

    # if user is black, Stockfish moves first
    if player_color == "b":
        stockfish.set_fen_position(board.fen())
        best_move = stockfish.get_best_move()
        print(f"\nStockfish opens with: {best_move}")
        board.push_uci(best_move)
        print(board)

    # --- user vs stockfish loop ---
    while not board.is_game_over():
        user_move = input("\nYour move (in SAN, e.g., e4, Nf3): ")
        try:
            board.push_san(user_move)
        except ValueError:
            print("Illegal move, try again.")
            continue

        print("\nBoard after your move:")
        print(board)

        if board.is_game_over():
            break

        stockfish.set_fen_position(board.fen())
        top_moves = stockfish.get_top_moves(3)
        print("\nStockfish's top 3 moves:")
        for i, move in enumerate(top_moves):
            score = move["Centipawn"]
            if score is not None:
                score_str = f"{score/100:.2f} (cp)"
            elif move["Mate"] is not None:
                score_str = f"Mate in {move['Mate']}"
            else:
                score_str = "N/A"
            print(f"{i+1}. {move['Move']} — Eval: {score_str}")

        best_move = top_moves[0]["Move"]
        print(f"\nStockfish plays: {best_move}")
        board.push_uci(best_move)
        print("\nBoard after Stockfish's move:")
        print(board)

else:
    # --- Stockfish vs Stockfish mode ---
    print("\nStockfish vs Stockfish begins!")
    print(board)
    time.sleep(1)

    while not board.is_game_over():
        stockfish.set_fen_position(board.fen())
        best_move = stockfish.get_best_move()
        print(f"Move {len(board.move_stack)+1}: {best_move}")
        board.push_uci(best_move)
        print(board)
        print()
        time.sleep(0.5)  # pause between moves for readability

# --- Game over ---
print("\nGame over!")
result = board.result()
if result == "1-0":
    print("White wins! 🎉")
elif result == "0-1":
    print("Black wins! 🤖")
else:
    print("It's a draw! 🤝")

print("\nFinal position:")
print(board)
