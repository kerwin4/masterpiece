
# game loop


# start game

# determine players
# begin turns

# human turn
# send message to arduino that it is the human turn over serial
# arduino constantly sends board reading back over serial
# save first board reading for the turn as turn start state
# compare each signal to turn start state
# if state changes, extrapolate what piece was removed and save the new board state as mid turn state and the square that changed as start square
# when the state changes again, save the board as turn end state and the square moved to as end square

# if a piece was moved to to a capture zone, save that as the end square and wait for another piece to be moved to the end square
# then follow normal process and extrapolate the start square from the next piece that moves

# if a pawn reaches the opposite side of the board, wait for the pawn to be removed, a piece from the promotions to be moved to where the pawn was
# and the pawn to be put in the promotion spot, then assume the turn is done

# check for castling, the king and rook are removed from the board, o-o or o-o-o

# create SAN move from start square and end square
# make the move in the chess engine and check that its legal

# if the move is legal, end the turn with the updated board

# if the move is illegal, use the electromagnet to move the piece from end square back to start square and start turn again
# once reset, go back to waiting for the board state to change

# once turn is successful, check checkmate status and change to robot turn


# robot turn
# send message to the arduino that it is the robot turn over serial
# arduino sends board back once
# convert board into FEN
# pass FEN to stockfish and get move
# use A* to get path
# convert path to motor commands
# send motor commands over serial to arduino
# make move in the chess engine
# save updated board
# check for confirmation from arduino that move is complete
# when move is complete, check for checkmate and switch turn to human


# if checkmate is reached
# see who made the last turn
# declare them the winner
# reset the board by checking which pieces are closest to their starting position and moving those first
