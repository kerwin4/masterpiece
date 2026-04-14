from game_loop import init_hardware, shutdown_hardware, run_game

def main():
    # start pi + arduino once
    pi, arduino = init_hardware()

    while True:
        run_game(pi, arduino) # play a full game
        # repeat if desired
        again = input("\nstart a new game? (y/n): ").strip().lower()
        if again != "y":
            break

    # shutdown everything once done
    shutdown_hardware(pi, arduino)

if __name__ == "__main__":
    main()