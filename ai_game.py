import board_item
import aivai

board = board_item.BoardItem()

# Paths to Stockfish executables for each AI
engine_path_white = "stockfish-windows-x86-64-avx2.exe"
engine_path_black = "stockfish-windows-x86-64-avx2.exe"

game = aivai.AIvsAI(board, engine_path_white, engine_path_black)
game.play_game(display=True, delay=0.5)
