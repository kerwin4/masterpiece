def is_game_square(r, c):
    return 1 <= r <= 8 and 2 <= c <= 9

def is_promo_col(c):
    return c == 0 or c == 11

def is_capture_square(r, c, board_item):
    return (r, c) in board_item.white_captures or (r, c) in board_item.black_captures

def state_to_uci(r, c):
    file = chr(ord('a') + (c - 2))
    rank = str(8 - (r - 1))
    return file + rank

def interpret_human_move(board_item, get_matrix):
    previous = get_matrix()

    start_square = None
    end_square = None
    promotion = None

    capture = False
    captured = False
    capturing = False
    castling = False
    rook_phase = False
    en_passant = False

    captured_piece_square = None

    while True:
        current = get_matrix()
        delta = previous - current
        previous = current

        # SANITY CHECK: no more than 48 pieces
        if current_matrix.sum() > 48:
            raise ValueError(f"Too many pieces detected on board: {current_matrix.sum()}")

        switched = list(zip(*np.where(delta != 0)))
        if len(switched) != 1:
            continue

        r, c = switched[0]
        d = delta[r, c]   # +1 lifted, -1 placed

        # ---------------- PROMOTION PIECE PICKUP ----------------
        if not promotion and d == +1 and is_promo_col(c):
            promo_list = (
                board_item.white_promos if c == 0 else board_item.black_promos
            )
            promotion = promo_list[r].lower()
            continue

        # ---------------- NORMAL LIFT ----------------
        if d == +1 and is_game_square(r, c):
            sq = state_to_uci(r, c)
            piece = board_item.chess_board.piece_at(chess.parse_square(sq))

            if piece is None:
                continue

            if not start_square:
                start_square = sq

                if piece.piece_type == chess.KING:
                    castling = True

            elif capture and not capturing:
                start_square = sq
                capturing = True

                # en passant detection
                if piece.piece_type == chess.PAWN:
                    sr = chess.square_rank(chess.parse_square(start_square))
                    cr = chess.square_rank(chess.parse_square(captured_piece_square))
                    if sr == cr:
                        en_passant = True

            continue

        # ---------------- NORMAL PLACE ----------------
        if d == -1 and is_game_square(r, c):
            sq = state_to_uci(r, c)

            if not end_square:
                end_square = sq

                if start_square:
                    s = chess.parse_square(start_square)
                    e = chess.parse_square(end_square)
                    if abs(chess.square_file(e) - chess.square_file(s)) > 1:
                        castling = True

                if not castling and not promotion and not capture:
                    break

            elif promotion and start_square:
                break

            continue

        # ---------------- CAPTURE HANDLING ----------------
        if d == -1 and is_capture_square(r, c, board_item):
            captured = True
            continue

        if capture and captured and d == +1 and is_game_square(r, c):
            start_square = state_to_uci(r, c)
            capturing = True
            continue

        if capture and capturing and d == -1 and is_game_square(r, c):
            if en_passant:
                end_square = state_to_uci(r, c)
            break

        # ---------------- CASTLING ROOK ----------------
        if castling and d == +1:
            rook_phase = True
            continue

        if castling and rook_phase and d == -1:
            break

    return start_square + end_square + (promotion or "")
