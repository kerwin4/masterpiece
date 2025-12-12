"""
Create a class to control and visualize the behavior of a physical human vs computer chess board.
"""

import chess
import numpy as np
import heapq
import random

class BoardItem:
    """
    Combined logical and physical chessboard representation for a robot-controlled
    chess system.

    This class handles
    - A standard 8×8 python-chess board representation
    - A 10×12 physical state grid representing pieces, capture slots, and promotions
    - A 19×23 node grid used for A* move pathfinding
    - Capture tracking for both sides
    - Promotion slot management
    - Full A* path planning for normal moves, captures, castling, and promotions
    - Rudimentary G-code generation for robotic movement

    Attributes:
        chess_board (chess.Board): The logical chessboard storing current game state from the python chess library.
        state_rows (int): Number of rows in the 10×12 state grid.
        state_cols (int): Number of columns in the 10×12 state grid.
        state_board (np.ndarray): 10×12 array storing piece positions and capture/promo info.
        node_rows (int): Number of rows in the 19×23 node grid.
        node_cols (int): Number of columns in the 19×23 node grid.
        node_grid (np.ndarray): 19×23 array pathfinding grid.
        black_captures (list[tuple[int, int]]): Slots for black's captured pieces.
        white_captures (list[tuple[int, int]]): Slots for white's captured pieces.
        captured_white (list[str]): List of white pieces that have been captured.
        captured_black (list[str]): List of black pieces that have been captured.
        white_promos (list[str]): Promotion piece indicators for white.
        black_promos (list[str]): Promotion piece indicators for black.

    Methods:
        update_from_chess():
            Regenerate both state and node grids from the current chess position.

        move_piece(uci_move, promotion=None):
            Execute a move on the logical chessboard and update all internal
            representations.

        display_board():
            Print the 8×8 python-chess board.

        display_state():
            Print the 10×12 state board.

        display_nodes():
            Print the 19×23 node grid.

        plan_path(uci_move, promotion=None):
            Compute A* path planning steps for the move, including captures,
            castling, and promotions.

        display_paths(path_seq):
            Visualize planned A* paths by overlaying markers on the node grid.

        generate_gcode(path_seq, node_spacing=1.0):
            Convert a path sequence into a formatted G-code program suitable for
            the gantry.
    """

    def __init__(self):
        # python-chess board (8x8)
        self.chess_board = chess.Board()

        # physical state (10×12)
        self.state_rows = 10
        self.state_cols = 12
        self.state_board = np.full((self.state_rows, self.state_cols), '.', dtype=object)

        # node grid (19×23)
        self.node_rows = 19
        self.node_cols = 23
        self.node_grid = np.full((self.node_rows, self.node_cols), '.', dtype=object)

        # pre-allocated capture square indices
        self.black_captures = [(3,1),(2,1),(1,1),(0,1),(0,2),(0,3),(0,4),(0,5),
                               (0,6),(0,7),(0,8),(0,9),(0,10),(1,10),(2,10),(3,10)]
        self.white_captures = [(6,1),(7,1),(8,1),(9,1),(9,2),(9,3),(9,4),(9,5),
                               (9,6),(9,7),(9,8),(9,9),(9,10),(8,10),(7,10),(6,10)]

        # storage lists for captured pieces
        self.captured_white = []
        self.captured_black = []

        # starting promotion piece layout order
        self.white_promos = ['B','N','R','Q','Q','Q','Q','B','N','R']
        self.black_promos = ['b','n','r','q','q','q','q','b','n','r']

        # set up the various board representations
        self._populate_state_board()
        self._populate_node_grid()

    # set up the state board with all piece locations given the 8x8 chess board
    def _populate_state_board(self):
        """
        Populate or rebuild the 10×12 physical state board.

        - Maps the 8×8 python-chess board into rows 1–8, columns 2–9
        - Inserts promotion indicators in columns 0 (white) and 11 (black)
        - Places captured pieces into their corresponding capture slots
        - Numbers empty capture slots with indices (1-16)

        Returns:
            None
        """
        # set up the visualization array with periods, so empty spaces are shown
        self.state_board[:, :] = '.'

        # map 8×8 chessboard into rows 1–8, cols 2–9
        for rank in range(8):
            for file in range(8):
                # get the square number from the chess board
                square = chess.square(file, 7 - rank)
                # get the piece at the square
                piece = self.chess_board.piece_at(square)
                # place the piece in our representation if the square isn't empty
                if piece:
                    self.state_board[rank + 1, file + 2] = piece.symbol()

        # promotion lanes
        for i, p in enumerate(self.white_promos):
            self.state_board[i, 0] = p # place the white promotion options in the left-most column
        for i, p in enumerate(self.black_promos):
            self.state_board[i, 11] = p # place the black promotion options in the right-most column

        # add captured pieces
        # iterate through the captured pieces
        for idx, p in enumerate(self.captured_black):
            # for each piece, find the corresponding capture space where it should be placed
            r,c = self.black_captures[idx]
            # place the piece at that square
            self.state_board[r,c] = p
        # repeat for white pieces
        for idx, p in enumerate(self.captured_white):
            r,c = self.white_captures[idx]
            self.state_board[r,c] = p

        # number the empty capture slots
        # iterate through the pre-allocated capture locations
        for idx, (r,c) in enumerate(self.black_captures):
            if self.state_board[r,c] == '.': # if a capture space doesn't have a capture
                self.state_board[r,c] = str(idx+1) # display the corresponding index number
        # repeat for white capture locations
        for idx, (r,c) in enumerate(self.white_captures):
            if self.state_board[r,c] == '.':
                self.state_board[r,c] = str(idx+1)

    # set up the node representation by spacing out the state board
    def _populate_node_grid(self):
        """
        Populate or rebuild the 19×23 node grid used for pathfinding.

        Each cell in the 10×12 state board maps to coordinates:
        (row * 2, col * 2) in the node grid. Newly created travel
        indices marked with periods.

        Returns:
            None
        """
        # fill in the entire 19x23 array with periods denoting empty spaces
        self.node_grid[:, :] = '.'
        # iterate through every index from the state board
        for r in range(self.state_rows):
            for c in range(self.state_cols):
                piece = self.state_board[r,c] # get the piece from the state board for the given index
                node_r = r * 2 # create the new node index by multiplying indices by 2
                node_c = c * 2
                self.node_grid[node_r, node_c] = piece # place the piece in the node space

    # helper function to update the visualizations
    def update_from_chess(self):
        """
        Update the state board and node grid based on the current game progression.

        Returns:
            None
        """
        self._populate_state_board()
        self._populate_node_grid()

    # move a piece and update all of the visualizations
    def move_piece(self, uci_move: str, promotion: str = None):
        """
        Execute a chess move on the logical board and update internal grids.
        Handles captures, promotions, and en passant.
        """
        # recreate full UCI for python-chess
        full_uci = uci_move + promotion if (promotion and not uci_move.endswith(promotion)) else uci_move
        move = self.chess_board.parse_uci(full_uci)
        moving_piece = self.chess_board.piece_at(move.from_square)
        captured_piece = self.chess_board.piece_at(move.to_square)

        # Detect en passant: pawn moves diagonally to empty square
        is_en_passant = False
        if moving_piece and moving_piece.piece_type == chess.PAWN:
            from_rank, from_file = chess.square_rank(move.from_square), chess.square_file(move.from_square)
            to_rank, to_file = chess.square_rank(move.to_square), chess.square_file(move.to_square)
            if abs(to_file - from_file) == 1 and captured_piece is None:
                is_en_passant = True
                # Captured pawn is on the same file as destination, rank of the starting pawn
                captured_sq = chess.square(to_file, from_rank)
                captured_piece = self.chess_board.piece_at(captured_sq)

        # Update captured pieces
        if captured_piece:
            if captured_piece.color == chess.WHITE:
                self.captured_white.append(captured_piece.symbol())
            else:
                self.captured_black.append(captured_piece.symbol())

        # Promotion handling
        is_promotion = (
            moving_piece
            and moving_piece.piece_type == chess.PAWN
            and (promotion or move.promotion)
        )

        if is_promotion:
            promo_map = {'Q': chess.QUEEN, 'R': chess.ROOK, 'B': chess.BISHOP, 'N': chess.KNIGHT}
            promo_char = promotion.upper()
            self.chess_board.push(chess.Move(move.from_square, move.to_square, promotion=promo_map[promo_char]))

            promo_list = self.white_promos if moving_piece.color == chess.WHITE else self.black_promos
            for i,p in enumerate(promo_list):
                if p.upper() == promo_char:
                    promo_list[i] = 'P' if moving_piece.color == chess.WHITE else 'p'
                    break
        else:
            self.chess_board.push(move)

        # Update visualizations
        self.update_from_chess()


    # visualize boards
    def display_board(self):
        """
        Print the current 8×8 python-chess board to terminal.

        Returns:
            None
        """
        print(self.chess_board)

    def display_state(self):
        """
        Print the 10×12 state board to terminal.

        Returns:
            None
        """
        print("=== 10×12 State Board ===")
        for r in range(self.state_rows):
            # use 2 character wide cells for even display and a space between each cell
            print(" ".join(f"{str(cell):>2}" for cell in self.state_board[r,:]))

    def display_nodes(self):
        """
        Print the 19×23 node grid to terminal.

        Returns:
            None
        """
        print("=== 19×23 Node Grid ===")
        for r in range(self.node_rows):
            # use 2 character wide cells for even display and a space between each cell
            print(" ".join(f"{str(cell):>2}" for cell in self.node_grid[r,:]))

    # A star path planning
    def plan_path(self, uci_move, promotion=None):
        """
        Plan an A* navigation path for executing a chess move.

        Args:
            uci_move (str): 4 character UCI chess move
            promotion (str, optional): Promotion letter ('Q', 'R', 'B', 'N')

        Returns:
            list[tuple[str, list[tuple[int, int]]]]

                A sequence of labeled steps:
                [
                    ("move", [(r, c), ...]),
                    ("capture", [...]),
                    ("promotion_pawn", [...]),
                    ("promotion_piece", [...]),
                    ("promotion_pawn_final", [...]),
                    ("castle_king", [...]),
                    ("castle_rook", [...])
                ]

                Each list contains node-grid coordinates representing the path 
                with the string corresponding to the type of move occuring.
        """
        # create the full UCI including the promotion character if necessary
        if promotion and not uci_move.endswith(promotion):
            full_uci = uci_move + promotion
        else:
            full_uci = uci_move

        # pass the UCI to python chess to determine move legality and start/end positions
        move = self.chess_board.parse_uci(full_uci)
        start_sq = move.from_square
        end_sq = move.to_square

        # determine board row/column for start and end positions
        sr = chess.square_rank(start_sq)
        sc = chess.square_file(start_sq)
        er = chess.square_rank(end_sq)
        ec = chess.square_file(end_sq)

        # determine node row/column for start and end positions based on board indices
        start_node = ((8 - sr) * 2, (sc + 2) * 2)
        end_node   = ((8 - er) * 2, (ec + 2) * 2)

        # create a placeholder for the path list
        path_seq = []

        # helper functions for pathfinding
        def neighbors(r, c, goal):
            result = []
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.node_rows and 0 <= nc < self.node_cols:
                    cell = self.node_grid[nr, nc]
                    if cell == '.' or (isinstance(cell, str) and cell.isdigit()) or (nr,nc) == goal:
                        if abs(dr) == 1 and abs(dc) == 1:
                            blocked = False
                            for sr2 in [r, nr]:
                                for sc2 in [c, nc]:
                                    if (sr2, sc2) != (r, c) and self.node_grid[sr2, sc2] not in ('.', str(sr2*sc2), self.node_grid[nr,nc]):
                                        blocked = True
                            if blocked:
                                continue
                        result.append((nr, nc))
            return result

        def man_dist(a, b):
            return abs(a[0]-b[0]) + abs(a[1]-b[1])

        def astar(start, goal):
            if start == goal:
                return [start]
            open_set = []
            heapq.heappush(open_set, (man_dist(start, goal), 0, start, [start]))
            visited = set()
            while open_set:
                _, g, current, path = heapq.heappop(open_set)
                if current in visited:
                    continue
                visited.add(current)
                if current == goal:
                    return path
                r, c = current
                for nbr in neighbors(r, c, goal):
                    if nbr not in visited:
                        heapq.heappush(open_set, (g + 1 + man_dist(nbr, goal), g + 1, nbr, path + [nbr]))
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
            saved = self.node_grid[end_node[0], end_node[1]]
            self.node_grid[end_node[0], end_node[1]] = '#'
            path_seq.append(('castle_rook', astar(rook_start_node, rook_end_node)))
            self.node_grid[end_node[0], end_node[1]] = saved

        else:
            captured_piece = self.chess_board.piece_at(end_sq)
            # --- EN PASSANT DETECTION ---
            is_en_passant = False
            en_passant_node = None
            if piece and piece.piece_type == chess.PAWN:
                if abs(ec - sc) == 1 and captured_piece is None:
                    # pawn moved diagonally but destination empty -> en passant
                    is_en_passant = True
                    captured_sq = chess.square(ec, sr)  # pawn captured is on the same rank as start
                    captured_piece = self.chess_board.piece_at(captured_sq)
                    en_passant_node = ((8 - sr) * 2, (ec + 2) * 2)

            if captured_piece:
                if captured_piece.color == chess.WHITE:
                    caps = self.white_captures
                else:
                    caps = self.black_captures
                if is_en_passant:
                    # Determine node coordinates of the captured pawn's actual position
                    captured_sq = chess.square(ec, sr)  # captured pawn is on same rank as start
                    captured_node = ((8 - sr) * 2, (ec + 2) * 2)  # node grid coordinates

                    # Find next empty capture slot for captured pawn
                    caps = self.white_captures if captured_piece.color == chess.WHITE else self.black_captures
                    capture_slot_node = None
                    for idx, (r, c) in enumerate(caps):
                        if self.state_board[r, c] == str(idx + 1):
                            capture_slot_node = (r * 2, c * 2)
                            break

                    # Add the captured pawn movement path from its current square to the capture slot
                    if captured_node and capture_slot_node:
                        path_seq.append(('capture', astar(captured_node, capture_slot_node)))

                else:
                    for idx,(r,c) in enumerate(caps):
                        if self.state_board[r,c] == str(idx+1):
                            cap_node = (r*2, c*2)
                            cap_path = astar(end_node, cap_node)
                            path_seq.append(('capture', cap_path))
                            break

            # promotion handling
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
                saved = self.node_grid[side_node[0], side_node[1]]
                self.node_grid[side_node[0], side_node[1]] = '#'
                path_seq.append(('promotion_piece', astar(promo_node, end_node)))
                self.node_grid[side_node[0], side_node[1]] = saved
                path_seq.append(('promotion_pawn_final', [side_node, promo_node]))
            else:
                path_seq.append(('move', astar(start_node, end_node)))

        for i,(step,path) in enumerate(path_seq):
            if path is None:
                print(f"path not found for {step}")
                path_seq[i] = (step, [])

        return path_seq

    # path visualization
    def display_paths(self, path_seq):
        """
        Print a node-grid visualization of a planned path sequence.

        'M' = normal movement
        'C' = capture handling
        'P' = promotion pawn movement
        'X' = promotion piece retrieval
        'K' = castling king path
        'R' = castling rook path

        Args:
            path_seq (list): Path sequence returned from plan_path()

        Returns:
            None
        """
        # make a copy of the node grid to add marks to
        vis = np.array(self.node_grid, copy=True, dtype=object)
        for step_type, path in path_seq:
            # skip any non-path instructions
            if not path: continue
            # get the correct marker for the type of move
            marker = {
                'move':'M','capture':'C','promotion_pawn':'P',
                'promotion_piece':'X','promotion_pawn_final':'P',
                'castle_king':'K','castle_rook':'R'
            }.get(step_type,'?')
            # place the marker at each node along the path
            for r,c in path:
                vis[r,c] = marker
        # display the visualization with markers
        print("=== Node Grid with Planned Paths ===")
        for r in range(self.node_rows):
            print(" ".join(f"{str(cell):>2}" for cell in vis[r,:]))

    # make g code always available using static method
    @staticmethod
    def generate_gcode(path_seq, node_spacing=1.0):
        """
        Convert a planned path sequence into G-code instructions.

        - Move to start of each segment with G0 rapid move
        - Raise servo "servo_up"
        - Follow path using linear moves (G1 X... Y... F50)
        - Lower servo "servo_down"

        Args:
            path_seq (list): Path sequence from plan_path()
            node_spacing (float, optional): Scale factor converting grid units to real units if that should change on the real board

        Returns:
            str: A multi-line G-code program.
        """
        # storage for gcode instructions
        lines = []
        # get each node in the path
        for _, path in path_seq:
            # if it isn't a node, move on
            if not path: continue
            # get row and column for the sequence start node
            sr, sc = path[0]
            # get the physical gantry location using known physical spacing
            x0, y0 = sr*node_spacing, sc*node_spacing
            # rapid move to the position
            lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")
            # add a servo up command to magnetize the piece
            lines.append("servo_up")
            # iterate along the path sequence until the sequence is up
            for r,c in path:
                # convert into physical gantry locations with known physical spacing
                x, y = r*node_spacing, c*node_spacing
                # move at slower specified feedrate using G1 move
                lines.append(f"G1 X{x:.3f} Y{y:.3f} F150")
            # lower the servo once the sequence is done
            lines.append("servo_down")
        # combine all of the commands into a single string
        return "\n".join(lines)
    
    def _direct_path(self, start_node, end_node):
        """
        Compute a direct path from start_node to end_node using BFS/A*-like search on node_grid.
        Avoids obstacles (non-empty squares) and returns a list of node coordinates.
        
        Args:
            start_node (tuple[int,int]): Starting node (row, col)
            end_node (tuple[int,int]): Target node (row, col)
        
        Returns:
            list[tuple[int,int]]: Path from start_node to end_node (inclusive)
        """
        from collections import deque

        if start_node == end_node:
            return [start_node]

        visited = set()
        queue = deque([(start_node, [start_node])])
        
        while queue:
            current, path = queue.popleft()
            if current == end_node:
                return path
            r, c = current
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.node_rows and 0 <= nc < self.node_cols:
                    if (nr, nc) not in visited:
                        # Allow moving through empty squares only
                        if self.node_grid[nr, nc] == '.' or (nr, nc) == end_node:
                            visited.add((nr, nc))
                            queue.append(((nr, nc), path + [(nr, nc)]))
        return []  # if no path found
    
    def reset_board_physical(self):
        """
        Reset the board to the starting state.

        - Moves all normal pieces to their starting squares.
        - Moves promotion pieces back to promotion lanes if needed.
        - Leaves capture squares empty.
        - Resolves blocking pieces by temporarily moving them to free squares.
        - Never moves a promotion piece that is already in the correct promotion lane.
        - Updates internal state and node grid after each move to prevent collisions.

        Returns:
            str: G-code instructions to reset the board
        """
        # Starting board positions by piece type
        starting_positions = {
            'R': [(8,2), (8,9)], 'N': [(8,3), (8,8)], 'B': [(8,4), (8,7)],
            'Q': [(8,5)], 'K': [(8,6)], 'P': [(7,c) for c in range(2,10)],
            'r': [(1,2), (1,9)], 'n': [(1,3), (1,8)], 'b': [(1,4), (1,7)],
            'q': [(1,5)], 'k': [(1,6)], 'p': [(2,c) for c in range(2,10)]
        }

        # Promotion nodes in node coordinates (19x23)
        white_promo_nodes = [(i*2, 0*2) for i in range(len(self.white_promos))]
        black_promo_nodes = [(i*2, 11*2) for i in range(len(self.black_promos))]

        temp_board = self.state_board.copy()
        reset_paths = []
        locked_squares = set()

        # Lock any normal piece already in its correct starting square
        for piece_type, targets in starting_positions.items():
            for t in targets:
                if temp_board[t] == piece_type:
                    locked_squares.add(t)

        # Lock promotion pieces already in the correct square
        for i, p in enumerate(self.white_promos):
            promo_square = (white_promo_nodes[i][0]//2, white_promo_nodes[i][1]//2)
            if temp_board[promo_square] == p:
                locked_squares.add(promo_square)
        for i, p in enumerate(self.black_promos):
            promo_square = (black_promo_nodes[i][0]//2, black_promo_nodes[i][1]//2)
            if temp_board[promo_square] == p:
                locked_squares.add(promo_square)

        # Helper to pick a random free square (not starting, promotion, or capture)
        def random_free_square():
            free_squares = [
                (r,c) for r in range(self.state_rows)
                    for c in range(self.state_cols)
                    if temp_board[r,c] == '.' and (r,c) not in locked_squares and c not in (0,11)
            ]
            return random.choice(free_squares) if free_squares else None

        # Reset normal pieces to starting squares
        for piece_type, targets in starting_positions.items():
            # Get all current positions of this piece type
            current_positions = list(zip(*np.where(temp_board == piece_type)))
            # Exclude locked promotion squares
            current_positions = [pos for pos in current_positions if pos not in locked_squares]

            for target in targets:
                if target in locked_squares:
                    continue  # target is already correct and locked
                if not current_positions:
                    break  # no pieces left to move

                # If target occupied, move blocker first
                if temp_board[target] != '.':
                    blocking_piece = temp_board[target]
                    free_sq = random_free_square()
                    if free_sq:
                        start_node = (target[0]*2, target[1]*2)
                        end_node = (free_sq[0]*2, free_sq[1]*2)
                        reset_paths.append(self._direct_path(start_node, end_node))
                        # Update temp_board and node grid
                        temp_board[free_sq] = blocking_piece
                        temp_board[target] = '.'
                        self.node_grid[start_node[0]:start_node[0]+1, start_node[1]:start_node[1]+1] = '.'
                        self.node_grid[end_node[0]:end_node[0]+1, end_node[1]:end_node[1]+1] = blocking_piece

                # Move current piece to target
                piece_pos = current_positions.pop(0)
                start_node = (piece_pos[0]*2, piece_pos[1]*2)
                end_node = (target[0]*2, target[1]*2)
                reset_paths.append(self._direct_path(start_node, end_node))

                # Update temp_board and node_grid
                temp_board[target] = piece_type
                temp_board[piece_pos] = '.'
                self.node_grid[start_node[0]:start_node[0]+1, start_node[1]:start_node[1]+1] = '.'
                self.node_grid[end_node[0]:end_node[0]+1, end_node[1]:end_node[1]+1] = piece_type

        # Reset promotion pieces if not in correct square
        for i, p in enumerate(self.white_promos):
            promo_square = (white_promo_nodes[i][0]//2, white_promo_nodes[i][1]//2)
            pos = np.where(temp_board == p)
            if len(pos[0]) > 0:
                start_node = (pos[0][0]*2, pos[1][0]*2)
                end_node = (promo_square[0]*2, promo_square[1]*2)
                if temp_board[promo_square] != p:
                    reset_paths.append(self._direct_path(start_node, end_node))
                    temp_board[promo_square] = p
                    temp_board[start_node[0]//2, start_node[1]//2] = '.'
                    self.node_grid[start_node[0], start_node[1]] = '.'
                    self.node_grid[end_node[0], end_node[1]] = p

        for i, p in enumerate(self.black_promos):
            promo_square = (black_promo_nodes[i][0]//2, black_promo_nodes[i][1]//2)
            pos = np.where(temp_board == p)
            if len(pos[0]) > 0:
                start_node = (pos[0][0]*2, pos[1][0]*2)
                end_node = (promo_square[0]*2, promo_square[1]*2)
                if temp_board[promo_square] != p:
                    reset_paths.append(self._direct_path(start_node, end_node))
                    temp_board[promo_square] = p
                    temp_board[start_node[0]//2, start_node[1]//2] = '.'
                    self.node_grid[start_node[0], start_node[1]] = '.'
                    self.node_grid[end_node[0], end_node[1]] = p

        # Generate G-code
        gcode = self.generate_gcode([("move", path) for path in reset_paths])
        return gcode
