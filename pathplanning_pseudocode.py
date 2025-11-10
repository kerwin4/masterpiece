# A star pseudocode

# use a class?

# Make a board object at the right size
# using the board state, create obstacles in the corresponding locations which updates each turn

# function
# take in starting square, ending square, start square 2 and end square 2 if multiple pieces need to be moved
# ultimately return the start square, end square, and motor commands to send to the arduino over serial

# using start position, end position, and obstacles on path, create a path for the piece to follow
# translate the path into a reference frame the gantry can follow
# determine motor commands to follow the path
# package the start square, end square, and motor commands into a message to send to the arduino over serial

# A*
#literally just calculating the theoretical path given a start and end location