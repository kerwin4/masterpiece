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

    mode = "idle"
    phase = 0

    while True:
        current = get_matrix()
        delta = previous - current
        previous = current

        switched = list(zip(*np.where(delta != 0)))
        if len(switched) != 1:
            continue

        r, c = switched[0]
        d = delta[r, c]   # +1 lifted, -1 placed

        # ======================================================
        # PROMOTION (promo piece ? pawn)
        # ======================================================
        if mode == "idle" and d == +1 and is_promo_col(c):
            promo_list = (
                board_item.white_promos if c == 0 else board_item.black_promos
            )
            promotion = promo_list[r].lower()
            mode = "promo"
            phase = 1
            continue

        if mode == "promo":
            # pawn lift
            if phase == 1 and d == +1 and is_game_square(r, c):
                start_square = state_to_uci(r, c)
                phase = 2
                continue

            # pawn place (onto promo start square)
            if phase == 2 and d == -1 and is_game_square(r, c):
                end_square = state_to_uci(r, c)
                break

            continue

        # ======================================================
        # CAPTURE (normal OR en passant) � captured first
        # ======================================================
        if mode == "idle" and d == +1 and is_capture_square(r, c, board_item):
            mode = "capture"
            phase = 1
            continue

        if mode == "capture":
            # capturer lift
            if phase == 1 and d == +1 and is_game_square(r, c):
                start_square = state_to_uci(r, c)
                phase = 2
                continue

            # capturer place
            if phase == 2 and d == -1 and is_game_square(r, c):
                end_square = state_to_uci(r, c)
                break

            continue

        # ======================================================
        # CASTLING (king ? rook)
        # ======================================================
        if mode == "idle" and d == +1 and is_game_square(r, c):
            start_square = state_to_uci(r, c)

            piece = board_item.chess_board.piece_at(
                chess.parse_square(start_square)
            )

            if piece and piece.piece_type == chess.KING:
                mode = "castle"
                phase = 1
            else:
                mode = "normal"

            continue

        if mode == "castle":
            # king place
            if phase == 1 and d == -1 and is_game_square(r, c):
                end_square = state_to_uci(r, c)
                phase = 2
                continue

            # rook lift
            if phase == 2 and d == +1 and is_game_square(r, c):
                phase = 3
                continue

            # rook place
            if phase == 3 and d == -1 and is_game_square(r, c):
                break

            continue

        # ======================================================
        # NORMAL MOVE
        # ======================================================
        if mode == "normal":
            if d == -1 and is_game_square(r, c):
                end_square = state_to_uci(r, c)
                break

    return start_square + end_square + (promotion or "")
