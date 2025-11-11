# arduino

# setup

# motor control library
# sensor setup
# electromagnet declaration

# loop

# check board state
# check for turn confirmation over serial from arduino

# if receive human turn
# continuously send board state to arduino over serial

    # if receive turn illegal
    # move to current piece location
    # turn electromagnet on
    # follow A* to the target location
    # turn electromagnet off
    # send confirmation that the board is reset to the arduino

# if receive robot turn
# send back one board state
# wait until motor commands are received
# move to start position
# move magnet up
# follow A* path
# move magnet down
# send confirmation that the move is complete


# functions

# hall effect check
# get readings from all sensors and create a board state 

# magnet_on(bool)
# move the magnet up or down to be on or off effectively

# A* parser
# unpack start square, end square, and motor commands from python serial message
# handle if there's multiple moves to make