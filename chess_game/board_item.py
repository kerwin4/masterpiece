"""
Create a class to control and visualize the behavior of a physical human vs computer chess board.
"""

import chess
import numpy as np
import heapq

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

        Accounts for captures and promotions should they occur. Promotions are tracked via the
        UCI input

        Args:
            uci_move (str): 4 character UCI move string following the format "e2e4", "e7e8"
            promotion (str, optional): Promotion letter 'Q', 'R', 'B', 'N' if applicable

        Returns:
            None
        """
        # recreate the full UCI so python chess library can interpret it if needed
        # if there is a promotion, it should be included in the full UCI
        full_uci = uci_move + promotion if (promotion and not uci_move.endswith(promotion)) else uci_move
        # determine move legality from python chess library by passing the UCI
        move = self.chess_board.parse_uci(full_uci)
        # determine what piece is making the move by checking what is at the starting square
        moving_piece = self.chess_board.piece_at(move.from_square)
        # check to see if the move will result in a capture by seeing what is at the end square
        captured_piece = self.chess_board.piece_at(move.to_square)
        # if there is a piece at the end square, add it to the opponent's captured pieces
        if captured_piece:
            if captured_piece.color == chess.WHITE:
                self.captured_white.append(captured_piece.symbol())
            else:
                self.captured_black.append(captured_piece.symbol())

        # promotion handling
        # determine that a promotion should occur
        is_promotion = (
            moving_piece # a moving piece is required
            and moving_piece.piece_type == chess.PAWN # the piece must be a pawn
            and promotion or move.promotion # and a promotion piece must be specified in the UCI
            )
        
        if is_promotion: # if a promotion is occuring
            # figure out which piece to communicate to python chess
            promo_map = {'Q': chess.QUEEN, 'R': chess.ROOK, 'B': chess.BISHOP, 'N': chess.KNIGHT}
            # determine the character to use when visualizing
            promo_char = promotion.upper()
            # push the move to python chess so it actually occurs with the promotion
            self.chess_board.push(chess.Move(move.from_square, move.to_square, promotion=promo_map[promo_char]))

            # get the list of promotions for the correct color
            if moving_piece.color == chess.WHITE:
                promo_list = self.white_promos
            else:
                promo_list = self.black_promos

            # swap in a pawn to replace the promoted piece
            for i,p in enumerate(promo_list):
                if p.upper() == promo_char:
                    promo_list[i] = 'P' if moving_piece.color == chess.WHITE else 'p'
                    break
        else:
            self.chess_board.push(move) # make a move as normal if no promotion
        # update the visualizations after the move has occurred
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
        # determine all valid neighboring nodes to a given node
        def neighbors(r, c, goal):
            """
            Return all valid neighboring nodes for a given grid position.

            Check all neighboring nodes in the cardinal direction. if they are empty,
            an empty capture space, or the move end position, the neighbor is a valid move location.

            Args:
                r (int): Row index of the current node
                c (int): Column index of the current node
                goal (tuple[int, int]): Target node coordinates for the end square (row, col)

            Returns:
                list[tuple[int, int]]: List of neighboring (row, col) positions that
                are valid move options
            """
            # placeholder list for valid neighbor nodes
            result = []
            # check all cardinal direction neighbors
            for nr,nc in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]:
                # make sure we don't move outside the board area
                if 0 <= nr < self.node_rows and 0 <= nc < self.node_cols:
                    # analyze the node if it is inside the board area
                    cell = self.node_grid[nr,nc]
                    # the piece is allowed to travel through empty squares, empty capture squares, and the goal
                    if (cell == '.' or (isinstance(cell,str) and cell.isdigit()) or (nr,nc)==goal):
                        # add it to the valid moves
                        result.append((nr,nc))
            return result

        def man_dist(a, b):
            """
            Compute the Manhattan distance (traveling along triangle legs rather than 
            hypoteneuse) between two nodes for A* short path optimization purposes.

            Args:
                a (tuple[int, int]): First node (row, col)
                b (tuple[int, int]): Second node (row, col)

            Returns:
                int: Manhattan distance |a_r - b_r| + |a_c - b_c|
            """
            return abs(a[0]-b[0]) + abs(a[1]-b[1])

        def astar(start, goal):
            """
            Perform A* pathfinding between two nodes on the grid.

            Uses a priority queue where each entry stores:
                (f_score, g_score, current_node, path_taken).

            Movement is restricted according to the rules defined in `neighbors()`.
            If the goal is reachable, the function returns the full path from start
            to goal, inclusive.

            Args:
                start (tuple[int, int]): Starting node coordinates (row, col)
                goal (tuple[int, int]): Target node coordinates (row, col)

            Returns:
                list[tuple[int, int]] | None:
                    The sequence of nodes forming the shortest valid path,
                    or None if no path exists.
            """
            # ff start and goal are the same, the path is just the start
            if start == goal:
                return [start]

            # priority queue for nodes to explore: (estimated total cost, steps so far, current node, path taken)
            open_set = []
            heapq.heappush(open_set, (man_dist(start, goal), 0, start, [start]))

            # keep track of visited nodes so we don't revisit them
            visited = set()

            # loop until there are no more nodes to explore
            while open_set:
                # take the node with the lowest estimated total cost
                _, g, current, path = heapq.heappop(open_set)
                
                # skip if we've already visited this node
                if current in visited:
                    continue
                # add the current node to visited nodes
                visited.add(current)
                
                # if we reached the goal, return the path
                if current == goal:
                    return path
                
                # explore all valid neighboring nodes that haven't already been visited
                r, c = current
                for nbr in neighbors(r, c, goal):
                    if nbr not in visited:
                        # push neighbor into queue with updated cost and path
                        heapq.heappush(open_set, (g + 1 + man_dist(nbr, goal), g + 1, nbr, path + [nbr]))

            # if no more nodes, pathfinding failed
            return None

        # get the piece to move by checking what is at the start square
        piece = self.chess_board.piece_at(start_sq)

        # handle castling
        # if we have a king that's moving more than one space, it must be a castle
        if (piece 
            and piece.piece_type == chess.KING 
            and abs(ec - sc) > 1
        ):
            # find the king's path using A*
            king_path = astar(start_node, end_node)
            # add this first step to the overall move path
            path_seq.append(('castle_king', king_path))

            # check which side the king is castling on to determine where the rook moves to/from
            if ec > sc:
                rook_start_sq = chess.square(7, sr)
                rook_end_sq   = chess.square(ec-1, sr)
            else:
                rook_start_sq = chess.square(0, sr)
                rook_end_sq   = chess.square(ec+1, sr)

            # get the start and end column for the rook based on the squares
            rsf = chess.square_file(rook_start_sq)
            ref = chess.square_file(rook_end_sq)

            # determine the starting and ending nodes
            rook_start_node = ((8-sr)*2, (rsf+2)*2)
            rook_end_node   = ((8-sr)*2, (ref+2)*2)

            # ensure the rook can't move through the king's end position by setting it's end square
            # to be a blocked character temporarily
            saved = self.node_grid[end_node[0], end_node[1]]
            self.node_grid[end_node[0], end_node[1]] = '#'
            # plan the castling rook's path around the king
            # and add the rook's move to the overall move path
            path_seq.append(('castle_rook', astar(rook_start_node, rook_end_node)))
            self.node_grid[end_node[0], end_node[1]] = saved


        else:
            # handle captures
            # get the piece at the end square if any
            captured_piece = self.chess_board.piece_at(end_sq)
            # if there is a piece to be captured, determine which color it is
            if captured_piece:
                if captured_piece.color == chess.WHITE:
                    caps = self.white_captures 
                else: 
                    caps = self.black_captures
                # find the next empty capture space for that color
                for idx,(r,c) in enumerate(caps):
                    if self.state_board[r,c] == str(idx+1):
                        # get the node for the empty capture space
                        cap_node = (r*2, c*2)
                        # plan the path for the captured piece
                        cap_path = astar(end_node, cap_node)
                        # add the captured piece's path to the overall move path
                        path_seq.append(('capture', cap_path))
                        break

            # promotion handling
            # determine if a promotion is occurring, piece being promoted must be a pawn
            is_promo = (
                promotion 
                and piece 
                and piece.piece_type == chess.PAWN
            )

            if is_promo:
                # get the column of promotion pieces for the correct color
                if piece.color == chess.WHITE:
                    promo_col = 0 
                else:
                    promo_col = 11

                promo_node = None
                # find the first node for the desired promotion piece 
                # in the column of promotion pieces
                for r in range(self.state_rows):
                    if self.state_board[r,promo_col].upper() == promotion.upper():
                        promo_node = (r*2, promo_col*2)
                        break

                # pick the node for the pawn's interim position next to the promotion piece
                # depending on which side the promotion is occurring
                if promo_col == 0:
                    side_col = 1
                else:
                    side_col = (self.node_cols - 2)
                # determine the node to the side of the promotion piece where the pawn should 
                # temporarily stop
                side_node = (promo_node[0], side_col)

                # plan the path for the pawn to move next to the promotion piece's starting point
                # and add that path to the overall move path
                path_seq.append(('promotion_pawn', astar(start_node, side_node)))

                # again add the pawn's midpoint as an obstacle so the promotion piece doesn't move
                # through it
                saved = self.node_grid[side_node[0], side_node[1]]
                self.node_grid[side_node[0], side_node[1]] = '#'
                # plan the promotion's piece move around the pawn's interim position
                # and add the path to the overall move path
                path_seq.append(('promotion_piece', astar(promo_node, end_node)))
                self.node_grid[side_node[0], side_node[1]] = saved
                # add the final pawn move to the overall path
                path_seq.append(('promotion_pawn_final', [side_node, promo_node]))

            else:
                # any standard non-capture move plans as normal and is added to the overall path
                path_seq.append(('move', astar(start_node, end_node)))

        # show missing paths
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
