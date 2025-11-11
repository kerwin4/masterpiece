import heapq

class PathPlannerAStar:
    def __init__(self, board_item):
        self.board_item = board_item
        self.node_grid = board_item.node_grid

    def neighbors(self, r, c):
        """Return cardinal neighbors that are free (empty or numbered capture slot)"""
        candidates = [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
        result = []
        for nr,nc in candidates:
            if 0 <= nr < self.board_item.node_rows and 0 <= nc < self.board_item.node_cols:
                cell = self.node_grid[nr,nc]
                if cell == '.' or (cell.isdigit() and int(cell) >= 1 and int(cell) <= 16):
                    result.append((nr,nc))
        return result

    def heuristic(self, a, b):
        """Manhattan distance"""
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    def astar(self, start, goal):
        """Return shortest path from start to goal using A*"""
        open_set = []
        heapq.heappush(open_set, (0 + self.heuristic(start, goal), 0, start, [start]))
        visited = set()

        while open_set:
            f, g, current, path = heapq.heappop(open_set)
            if current in visited:
                continue
            visited.add(current)

            if current == goal:
                return path

            for neighbor in self.neighbors(*current):
                if neighbor not in visited:
                    heapq.heappush(open_set, (
                        g+1+self.heuristic(neighbor, goal), 
                        g+1, 
                        neighbor, 
                        path + [neighbor]
                    ))
        return None

    def get_path_for_move(self, uci_move, promotion=None):
        """Return sequence of node positions for a move, including captures/promotions"""
        start_square = self.board_item.chess_board.parse_uci(uci_move).from_square
        end_square = self.board_item.chess_board.parse_uci(uci_move).to_square
        start_row = chess.square_rank(start_square)
        start_col = chess.square_file(start_square)
        end_row = chess.square_rank(end_square)
        end_col = chess.square_file(end_square)

        start_node = (start_row*2+1, start_col*2+1)
        end_node = (end_row*2+1, end_col*2+1)

        path_sequence = []

        # Check capture
        captured_piece = self.board_item.chess_board.piece_at(end_square)
        if captured_piece:
            # Determine which capture ring
            captures = self.board_item.white_captures if captured_piece.color == chess.WHITE else self.board_item.black_captures
            # Find next free capture slot
            for idx, (r,c) in enumerate(captures):
                if self.board_item.state_board[r,c] == str(idx+1):
                    capture_node = (r*2+1, c*2+1)
                    break
            # Path of captured piece to capture slot
            capture_path = self.astar(end_node, capture_node)
            if capture_path:
                path_sequence.append(('capture', capture_path))

        # Handle promotion
        pawn_piece = self.board_item.chess_board.piece_at(start_square)
        is_promotion = promotion is not None and pawn_piece.piece_type == chess.PAWN
        if is_promotion:
            # Move pawn to node above promotion piece
            promo_col = 0 if pawn_piece.color == chess.WHITE else 11
            for r in range(self.board_item.state_rows):
                if self.board_item.state_board[r,promo_col].upper() == promotion.upper():
                    promo_node_above = (r*2, promo_col*2+1)  # node above
                    promo_node = (r*2+1, promo_col*2+1)      # node of promotion piece itself
                    break
            path_sequence.append(('promotion_pawn', self.astar(start_node, promo_node_above)))
            # Move promotion piece to pawn start
            path_sequence.append(('promotion_piece', self.astar(promo_node, start_node)))
            # Move pawn down 1 node onto final square
            final_node = (promo_node_above[0]+1, promo_node_above[1])
            path_sequence.append(('promotion_pawn_final', [final_node]))
        else:
            # Normal move
            path_sequence.append(('move', self.astar(start_node, end_node)))

        return path_sequence
