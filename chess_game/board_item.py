import chess
import numpy as np
import heapq

class BoardItem:
    """
    Handles the 8x8 chess board, a 10x12 state space,
    and a 19x23 node grid. Supports path planning for robotic movement.
    """

    def __init__(self):
        # python-chess board
        self.chess_board = chess.Board()

        # physical state (10 × 12)
        self.state_rows = 10
        self.state_cols = 12
        self.state_board = np.full((self.state_rows, self.state_cols), '.', dtype=object)

        # node grid (19 × 23)
        self.node_rows = 19
        self.node_cols = 23
        self.node_grid = np.full((self.node_rows, self.node_cols), '.', dtype=object)

        # capture spaces (same as original)
        self.black_captures = [(3,1),(2,1),(1,1),(0,1),(0,2),(0,3),(0,4),(0,5),
                               (0,6),(0,7),(0,8),(0,9),(0,10),(1,10),(2,10),(3,10)]
        self.white_captures = [(6,1),(7,1),(8,1),(9,1),(9,2),(9,3),(9,4),(9,5),
                               (9,6),(9,7),(9,8),(9,9),(9,10),(8,10),(7,10),(6,10)]

        self.captured_white = []
        self.captured_black = []

        # promotions
        self.white_promos = ['B','N','R','Q','Q','Q','Q','B','N','R']
        self.black_promos = ['b','n','r','q','q','q','q','b','n','r']

        self._populate_state_board()
        self._populate_node_grid()

    # set up the state board with all piece locations given the 8x8 chess board
    def _populate_state_board(self):
        self.state_board[:, :] = '.'

        # map 8×8 chessboard into rows 1–8, cols 2–9
        for rank in range(8):
            for file in range(8):
                square = chess.square(file, 7 - rank)
                piece = self.chess_board.piece_at(square)
                self.state_board[rank + 1, file + 2] = piece.symbol() if piece else '.'

        # promotion lanes
        for i, p in enumerate(self.white_promos):
            self.state_board[i, 0] = p
        for i, p in enumerate(self.black_promos):
            self.state_board[i, 11] = p

        # add captured pieces
        for idx, p in enumerate(self.captured_black):
            r,c = self.black_captures[idx]
            self.state_board[r,c] = p
        for idx, p in enumerate(self.captured_white):
            r,c = self.white_captures[idx]
            self.state_board[r,c] = p

        # numbered capture slots
        for idx, (r,c) in enumerate(self.black_captures):
            if self.state_board[r,c] == '.':
                self.state_board[r,c] = str(idx+1)
        for idx, (r,c) in enumerate(self.white_captures):
            if self.state_board[r,c] == '.':
                self.state_board[r,c] = str(idx+1)

    # set up the node representation by spacing out the state board
    def _populate_node_grid(self):
        self.node_grid[:, :] = '.'
        for r in range(self.state_rows):
            for c in range(self.state_cols):
                piece = self.state_board[r,c]
                node_r = r * 2
                node_c = c * 2
                if node_r < self.node_rows and node_c < self.node_cols:
                    self.node_grid[node_r, node_c] = piece

    # helper function to update the visualizations
    def update_from_chess(self):
        self._populate_state_board()
        self._populate_node_grid()

    # move a piece and update all of the visualizations
    def move_piece(self, uci_move: str, promotion: str = None):
        full_uci = uci_move + promotion if (promotion and not uci_move.endswith(promotion)) else uci_move
        move = self.chess_board.parse_uci(full_uci)

        captured_piece = self.chess_board.piece_at(move.to_square)
        if captured_piece:
            if captured_piece.color == chess.WHITE:
                self.captured_white.append(captured_piece.symbol())
            else:
                self.captured_black.append(captured_piece.symbol())

        moving_piece = self.chess_board.piece_at(move.from_square)

        # promotion handling
        is_promotion = moving_piece and moving_piece.piece_type == chess.PAWN and (promotion or move.promotion)
        if is_promotion:
            promo_map = {'Q': chess.QUEEN, 'R': chess.ROOK, 'B': chess.BISHOP, 'N': chess.KNIGHT}
            promo_char = promotion.upper() if promotion else 'Q'
            self.chess_board.push(chess.Move(move.from_square, move.to_square, promotion=promo_map[promo_char]))

            promo_list = self.white_promos if moving_piece.color == chess.WHITE else self.black_promos
            for i,p in enumerate(promo_list):
                if p.upper() == promo_char:
                    promo_list[i] = 'P' if moving_piece.color == chess.WHITE else 'p'
                    break
        else:
            self.chess_board.push(move)

        self.update_from_chess()

    # visualize boards
    def display_board(self):
        print(self.chess_board)

    def display_state(self):
        print("=== 10×12 State Board ===")
        for r in range(self.state_rows):
            print(" ".join(f"{str(cell):>2}" for cell in self.state_board[r,:]))

    def display_nodes(self):
        print("=== 19×23 Node Grid ===")
        for r in range(self.node_rows):
            print(" ".join(f"{str(cell):>2}" for cell in self.node_grid[r,:]))

    # A star path planning
    def plan_path(self, uci_move, promotion=None):
        full_uci = uci_move + promotion if (promotion and not uci_move.endswith(promotion)) else uci_move

        move = self.chess_board.parse_uci(full_uci)
        start_sq, end_sq = move.from_square, move.to_square

        sr, sc = chess.square_rank(start_sq), chess.square_file(start_sq)
        er, ec = chess.square_rank(end_sq), chess.square_file(end_sq)

        start_node = ((8 - sr) * 2, (sc + 2) * 2)
        end_node   = ((8 - er) * 2, (ec + 2) * 2)

        node_grid = self.node_grid
        path_seq = []

        # neighbors
        def neighbors(r,c,goal):
            result = []
            for nr,nc in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]:
                if 0 <= nr < self.node_rows and 0 <= nc < self.node_cols:
                    cell = node_grid[nr,nc]
                    if (cell == '.' or (isinstance(cell,str) and cell.isdigit()) or (nr,nc)==goal):
                        result.append((nr,nc))
            return result

        def heuristic(a,b):
            return abs(a[0]-b[0]) + abs(a[1]-b[1])

        def astar(start,goal):
            if start == goal:
                return [start]
            open_set = []
            heapq.heappush(open_set,(heuristic(start,goal),0,start,[start]))
            visited=set()
            while open_set:
                f,g,current,path = heapq.heappop(open_set)
                if current in visited: continue
                visited.add(current)
                if current == goal: return path
                for nbr in neighbors(*current,goal):
                    if nbr not in visited:
                        heapq.heappush(open_set,(g+1+heuristic(nbr,goal), g+1, nbr, path+[nbr]))
            return None

        piece = self.chess_board.piece_at(start_sq)

        # handle castling
        if piece and piece.piece_type == chess.KING and abs(ec - sc) > 1:
            king_path = astar(start_node, end_node)
            path_seq.append(('castle_king', king_path))

            if ec > sc:
                rook_start_sq = chess.square(7, sr)
                rook_end_sq   = chess.square(ec-1, sr)
            else:
                rook_start_sq = chess.square(0, sr)
                rook_end_sq   = chess.square(ec+1, sr)

            rsf = chess.square_file(rook_start_sq)
            ref = chess.square_file(rook_end_sq)

            rook_start_node = ((8-sr)*2, (rsf+2)*2)
            rook_end_node   = ((8-sr)*2, (ref+2)*2)

            saved = node_grid[end_node[0], end_node[1]]
            node_grid[end_node[0], end_node[1]] = '#'
            rook_path = astar(rook_start_node, rook_end_node)
            node_grid[end_node[0], end_node[1]] = saved

            path_seq.append(('castle_rook', rook_path))

        else:
            # capture
            captured_piece = self.chess_board.piece_at(end_sq)
            if captured_piece:
                caps = self.white_captures if captured_piece.color == chess.WHITE else self.black_captures
                for idx,(r,c) in enumerate(caps):
                    if self.state_board[r,c] == str(idx+1):
                        cap_node = (r*2, c*2)
                        cap_path = astar(end_node, cap_node)
                        path_seq.append(('capture', cap_path))
                        break

            # promotions
            is_promo = promotion and piece and piece.piece_type == chess.PAWN
            if is_promo:
                promo_col = 0 if piece.color == chess.WHITE else 11

                promo_node = None
                for r in range(self.state_rows):
                    if self.state_board[r,promo_col].upper() == promotion.upper():
                        promo_node = (r*2, promo_col*2)
                        break

                side_col = 1 if promo_col == 0 else (self.node_cols - 2)
                side_node = (promo_node[0], side_col)

                path_seq.append(('promotion_pawn', astar(start_node, side_node)))

                saved = node_grid[side_node[0], side_node[1]]
                node_grid[side_node[0], side_node[1]] = '#'
                path_seq.append(('promotion_piece', astar(promo_node, end_node)))
                node_grid[side_node[0], side_node[1]] = saved

                path_seq.append(('promotion_pawn_final', [side_node, promo_node]))

            else:
                path_seq.append(('move', astar(start_node, end_node)))

        # fix missing paths
        for i,(step,path) in enumerate(path_seq):
            if path is None:
                print(f"Warning: path not found for {step}")
                path_seq[i] = (step, [])

        return path_seq

    # path visualization
    def display_paths(self, path_seq):
        vis = np.array(self.node_grid, copy=True, dtype=object)
        for step_type, path in path_seq:
            if not path: continue
            marker = {
                'move':'M','capture':'C','promotion_pawn':'P',
                'promotion_piece':'X','promotion_pawn_final':'P',
                'castle_king':'K','castle_rook':'R'
            }.get(step_type,'?')
            for r,c in path:
                vis[r,c] = marker
        print("=== Node Grid with Planned Paths ===")
        for r in range(self.node_rows):
            print(" ".join(f"{str(cell):>2}" for cell in vis[r,:]))

    # make g code always available
    @staticmethod
    def generate_gcode(path_seq, node_spacing=1.0):
        lines = []
        for step_type, path in path_seq:
            if not path: continue

            sr, sc = path[0]
            x0, y0 = sr*node_spacing, sc*node_spacing
            lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")
            lines.append("servo_up")

            for r,c in path:
                x, y = r*node_spacing, c*node_spacing
                lines.append(f"G1 X{x:.3f} Y{y:.3f} F50")

            lines.append("servo_down")

        return "\n".join(lines)
