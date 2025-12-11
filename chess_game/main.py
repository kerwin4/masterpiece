from game_loop import init_hardware, shutdown_hardware, run_game

def main():
    # start pi + arduino once
    pi, arduino = init_hardware()

    while True:
        run_game()   # play a full game

        again = input("\nStart a new game? (y/n): ").strip().lower()
        if again != "y":
            break

    # shutdown everything once the user is done
    shutdown_hardware(pi, arduino)

if __name__ == "__main__":
    main()
