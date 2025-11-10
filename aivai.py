import chess.engine
import time

class AIvsAI:
    def __init__(self, board_item, engine_path_white, engine_path_black, time_limit=0.1):
        """
        board_item: your BoardItem instance
        engine_path_white: path to engine for White
        engine_path_black: path to engine for Black
        time_limit: thinking time per move in seconds
        """
        self.board_item = board_item
        self.time_limit = time_limit
        self.engines = {
            chess.WHITE: chess.engine.SimpleEngine.popen_uci(engine_path_white),
            chess.BLACK: chess.engine.SimpleEngine.popen_uci(engine_path_black)
        }

    def play_game(self, display=True, visualize_paths=True, delay=0.2):
        while not self.board_item.chess_board.is_game_over():
            turn = self.board_item.chess_board.turn
            engine = self.engines[turn]

            # Ask engine for best move
            result = engine.play(self.board_item.chess_board, chess.engine.Limit(time=self.time_limit))
            move = result.move.uci()

            # Detect promotion
            promotion_piece = None
            from_square = result.move.from_square
            to_square = result.move.to_square
            piece = self.board_item.chess_board.piece_at(from_square)
            if piece.piece_type == chess.PAWN:
                rank_to = chess.square_rank(to_square)
                if (turn == chess.WHITE and rank_to == 7) or (turn == chess.BLACK and rank_to == 0):
                    promotion_piece = 'Q'

            # --- PLAN PATH BEFORE MOVING ---
            path_seq = self.board_item.plan_path(move, promotion=promotion_piece)
            if visualize_paths:
                print(f"\n{'White' if turn else 'Black'} planned move: {move} {'(promotion)' if promotion_piece else ''}")
                self.board_item.display_paths(path_seq)

            # --- EXECUTE MOVE ---
            self.board_item.move_piece(move, promotion=promotion_piece)

            if display:
                print(f"{'White' if turn else 'Black'} executed move: {move}")
                self.board_item.display_state()
                self.board_item.display_nodes()
                time.sleep(delay)

        print("Game over!")
        print("Result:", self.board_item.chess_board.result())
        for engine in self.engines.values():
            engine.quit()
