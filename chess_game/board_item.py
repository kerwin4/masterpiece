import chess
import numpy as np
import heapq

class BoardItem:
    """
    A class to handle tracking the 8x8 chess game, the 10x12 state space,
    and the 21x25 node space as 3 different representations of the board.
    Allows move inputs from users, both human and computer, and translates
    those moves between the 3 representations, including path planning
    in the node space to prepare for G-code generation.
    """

    def __init__(self):
        # regular 8x8 chess board
        self.chess_board = chess.Board()

        # physical state space
        self.state_rows = 10
        self.state_cols = 12
        self.state_board = np.full((self.state_rows, self.state_cols), '.', dtype=object)

        # node representation
        self.node_rows = 21
        self.node_cols = 25
        self.node_grid = np.full((self.node_rows, self.node_cols), '.', dtype=object)

        # capture spaces
        self.black_captures = [(3,1),(2,1),(1,1),(0,1),(0,2),(0,3),(0,4),(0,5),
                               (0,6),(0,7),(0,8),(0,9),(0,10),(1,10),(2,10),(3,10)]
        self.white_captures = [(6,1),(7,1),(8,1),(9,1),(9,2),(9,3),(9,4),(9,5),
                               (9,6),(9,7),(9,8),(9,9),(9,10),(8,10),(7,10),(6,10)]

        # tracking for captured pieces
        self.captured_white = []  # pieces captured by black
        self.captured_black = []  # pieces captured by white

        # promotion lists
        self.white_promos = ['B','N','R','Q','Q','Q','Q','B','N','R']
        self.black_promos = ['b','n','r','q','q','q','q','b','n','r']

        # populate the representations
        self._populate_state_board()
        self._populate_node_grid()

    # internal board population
    def _populate_state_board(self):
        self.state_board[:, :] = '.'

        # map python-chess board into rows 1–8, cols 2–9 in the state space
        for rank in range(8):
            for file in range(8):
                square = chess.square(file, 7 - rank)
                piece = self.chess_board.piece_at(square)
                row = rank + 1
                col = file + 2
                self.state_board[row, col] = piece.symbol() if piece else '.'

        # populate promotion zone
        for i, p in enumerate(self.white_promos):
            self.state_board[i, 0] = p
        for i, p in enumerate(self.black_promos):
            self.state_board[i, 11] = p

        # put captured pieces in the right spot
        for idx, p in enumerate(self.captured_black):
            if idx < len(self.black_captures):
                r,c = self.black_captures[idx]
                self.state_board[r,c] = p
        for idx, p in enumerate(self.captured_white):
            if idx < len(self.white_captures):
                r,c = self.white_captures[idx]
                self.state_board[r,c] = p

        # put numbers in empty capture zones so order is maintained
        for idx, (r,c) in enumerate(self.black_captures):
            if self.state_board[r,c] == '.':
                self.state_board[r,c] = str(idx+1)
        for idx, (r,c) in enumerate(self.white_captures):
            if self.state_board[r,c] == '.':
                self.state_board[r,c] = str(idx+1)

    # populate the node grid representation according to the state space
    def _populate_node_grid(self):
        self.node_grid[:, :] = '.'
        for r in range(self.state_rows):
            for c in range(self.state_cols):
                piece = self.state_board[r, c]
                node_r = r*2 + 1
                node_c = c*2 + 1
                if node_r < self.node_rows and node_c < self.node_cols:
                    self.node_grid[node_r, node_c] = piece

    # update board and movement
    def update_from_chess(self):
        self._populate_state_board()
        self._populate_node_grid()

    # move a piece on the board given some UCI representation of the move
    def move_piece(self, uci_move: str, promotion: str = None):
        if promotion and not uci_move.endswith(promotion):
            full_uci = uci_move + promotion
        else:
            full_uci = uci_move

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

            # update the promotion lists
            promo_list = self.white_promos if moving_piece.color == chess.WHITE else self.black_promos

            # find the index in the promotion list that matches the promoted piece on the column
            for i, p in enumerate(promo_list):
                if p.upper() == promo_char:
                    # put the pawn in this slot instead of the promoted piece
                    promo_list[i] = 'P' if moving_piece.color == chess.WHITE else 'p'
                    break
        else:
            # castling or normal move
            self.chess_board.push(move)

        self.update_from_chess()


    # visualize all 3 board states
    def display_board(self):
        print(self.chess_board)

    def display_state(self):
        print("=== 10×12 State Board ===")
        for r in range(self.state_rows):
            print(' '.join(f"{str(cell):>2}" for cell in self.state_board[r, :]))

    def display_nodes(self):
        print("=== 21×25 Node Grid ===")
        for r in range(self.node_rows):
            print(' '.join(f"{str(cell):>2}" for cell in self.node_grid[r, :]))

    # plan path with a star algorithm for a given UCI move
    def plan_path(self, uci_move, promotion=None):
        if promotion and not uci_move.endswith(promotion):
            full_uci = uci_move + promotion
        else:
            full_uci = uci_move

        move = self.chess_board.parse_uci(full_uci)
        start_sq, end_sq = move.from_square, move.to_square
        start_row, start_col = chess.square_rank(start_sq), chess.square_file(start_sq)
        end_row, end_col = chess.square_rank(end_sq), chess.square_file(end_sq)

        start_node = ((8-start_row)*2 + 1, (start_col+2)*2 +1)
        end_node   = ((8-end_row)*2 + 1, (end_col+2)*2 +1)

        node_grid = self.node_grid
        path_seq = []

        # A* helper functions
        def neighbors(r, c, goal):
            candidates = [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
            result = []
            for nr,nc in candidates:
                if 0<=nr<self.node_rows and 0<=nc<self.node_cols:
                    cell = node_grid[nr,nc]
                    if cell=='.' or (isinstance(cell,str) and cell.isdigit() and 1<=int(cell)<=16) or (nr,nc)==goal:
                        result.append((nr,nc))
            return result

        def heuristic(a,b):
            return abs(a[0]-b[0]) + abs(a[1]-b[1])

        def astar(start, goal):
            if start==goal:
                return [start]
            open_set = []
            heapq.heappush(open_set, (heuristic(start,goal),0,start,[start]))
            visited = set()
            while open_set:
                f,g,current,path = heapq.heappop(open_set)
                if current in visited:
                    continue
                visited.add(current)
                if current==goal:
                    return path
                for nbr in neighbors(*current, goal):
                    if nbr not in visited:
                        heapq.heappush(open_set, (g+1+heuristic(nbr,goal), g+1, nbr, path+[nbr]))
            return None

        piece = self.chess_board.piece_at(start_sq)

        # handle castling
        if piece and piece.piece_type==chess.KING and abs(end_col-start_col)>1:
            # king path
            king_path = astar(start_node, end_node)
            path_seq.append(('castle_king', king_path))

            # determine rook start/end
            if end_col>start_col:  # kingside
                rook_start_sq = chess.square(7, start_row)
                rook_end_sq   = chess.square(end_col-1, start_row)
            else:  # queenside
                rook_start_sq = chess.square(0, start_row)
                rook_end_sq   = chess.square(end_col+1, start_row)

            rook_start_node = ((8-start_row)*2+1, (2+chess.square_file(rook_start_sq))*2+1)
            rook_end_node   = ((8-start_row)*2+1, (2+chess.square_file(rook_end_sq))*2+1)

            # temporarily block king's end node
            saved_val = node_grid[end_node[0], end_node[1]]
            node_grid[end_node[0], end_node[1]] = '#'
            rook_path = astar(rook_start_node, rook_end_node)
            node_grid[end_node[0], end_node[1]] = saved_val

            path_seq.append(('castle_rook', rook_path))
        else:
            # capturing a piece
            captured_piece = self.chess_board.piece_at(end_sq)
            if captured_piece:
                captures = self.white_captures if captured_piece.color==chess.WHITE else self.black_captures
                for idx,(r,c) in enumerate(captures):
                    if self.state_board[r,c]==str(idx+1):
                        cap_node=(r*2+1, c*2+1)
                        cap_path=astar(end_node, cap_node)
                        path_seq.append(('capture', cap_path))
                        break

            # promoting a piece
            is_promo = promotion and piece and piece.piece_type==chess.PAWN
            if is_promo:
                promo_col = 0 if piece.color==chess.WHITE else 11
                promo_node = promo_node_above = None
                for r in range(self.state_rows):
                    if self.state_board[r,promo_col].upper()==promotion.upper():
                        promo_node = (r*2+1, promo_col*2+1)
                        promo_node_above = (r*2, promo_col*2+1)
                        break

                # step 1 pawn moves to above promotion piece
                path_seq.append(('promotion_pawn', astar(start_node, promo_node_above)))

                # step 2 promotion piece moves to final square
                saved_val = node_grid[promo_node_above[0], promo_node_above[1]]
                node_grid[promo_node_above[0], promo_node_above[1]] = '#'
                path_seq.append(('promotion_piece', astar(promo_node, end_node)))
                node_grid[promo_node_above[0], promo_node_above[1]] = saved_val

                # step 3 pawn moves down one node to promotion piece former spot
                promo_node_above = (promo_node[0] - 1, promo_node[1])
                path_seq.append(('promotion_pawn_final', [promo_node_above, promo_node]))
            else:
                path_seq.append(('move', astar(start_node, end_node)))

        # check if no path could be found
        for idx,(step,path) in enumerate(path_seq):
            if path is None:
                print(f"Warning: Could not find path for {step}")
                path_seq[idx]=(step, [])

        return path_seq

    # display a move on the node representation
    def display_paths(self, path_seq):
        vis_grid = np.array(self.node_grid, copy=True, dtype=object)
        for step_type, path in path_seq:
            marker = '?'
            if step_type=='move': marker='M'
            elif step_type=='capture': marker='C'
            elif step_type=='promotion_pawn': marker='P'
            elif step_type=='promotion_piece': marker='X'
            elif step_type=='promotion_pawn_final': marker='P'
            elif step_type=='castle_king': marker='K'
            elif step_type=='castle_rook': marker='R'
            for r,c in path:
                vis_grid[r,c]=marker
        print("=== Node Grid with Planned Paths ===")
        for r in range(self.node_rows):
            print(' '.join(f"{str(cell):>2}" for cell in vis_grid[r,:]))

    # figure out what gcode to send to the arduino based on the planned path
    def generate_gcode(path_seq, node_spacing=1.0):
        """
        Generate a sequence of commands for Arduino (G-code) and Pi (servo commands).

        Parameters:
            path_seq: list of tuples (step_type, path)
            node_spacing: distance in inches between adjacent nodes (default=1.0)

        Returns:
            gcode_str: multi-line string of commands ready for serial sending
        """
        gcode_lines = []

        for step_type, path in path_seq:
            if not path:
                continue

            # move to first node of the sequence (rapid move with g0)
            start_r, start_c = path[0]
            x_start = start_r * node_spacing
            y_start = start_c * node_spacing
            gcode_lines.append(f"G0 X{x_start:.3f} Y{y_start:.3f}")  # arduino move

            # servo up at beginning of sequence (interpreted by pi NOT ARDUINO)
            gcode_lines.append("servo_up")

            # move along path (arduino linear moves)
            for r, c in path:
                x = r * node_spacing
                y = c * node_spacing
                gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F50")  # arduino move with lower feedrate determine empirically

            # servo down at end of sequence again INTERPRET WITH PI
            gcode_lines.append("servo_down")

        # combine all lines into one string that can be read line by line
        gcode_str = "\n".join(gcode_lines)
        return gcode_str

