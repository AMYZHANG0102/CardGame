from mpi4py import MPI
import random
import time

TAG_HAND = 10 # dealer → player (send a new hand at the start of a round)
TAG_TURN = 20 # dealer → player (your turn + board card)
TAG_RESULT = 30 # player → dealer (play/pass/win/draw response)
TAG_END = 40 # dealer → player (round over OR game over)

# Nawaf: Tag used only when a player requests to draw a card.
TAG_DRAW = 50 #dealer → player (the single drawn card response)


# =========================
# createDeck(): 52-card deck
# =========================
def createDeck():
    # Define 4 suits and 13 ranks
    suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']

    created_deck = []
    for suit in suits:
        for rank in ranks:
            created_deck.append(f"{rank} of {suit}")
    random.shuffle(created_deck)
    return created_deck


def main():
    # Establishing comm, rank, and size
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank() # Rank identifies which process you are: rank == 0 → dealer, rank > 0 → player
    size = comm.Get_size()  # This is the total process player + dealer

    # Here we will need atleast two processes or else the game cannot run
    if size < 2:
        if rank == 0:
            print("Need at least 2 MPI processes: 1 dealer + >=1 player.")
        return

    # ==========================
    # Dealer Logic Side (rank 0)
    # ==========================
    if rank == 0:
        deck = createDeck()

        # Nawaf - Score system (persists across rounds)
        # Dealer creates + shuffles deck.
        scores = {}
        for player in range(1, size):
            # Initialize the score for each player rank to 0.
            scores[player] = 0


        deck_index = 0  # Nawaf: track the NEXT card to draw from deck
        game_over = False # ends the overall game
        round_no = 0 # counter for rounds

        # Nawaf- Multiple rounds until the deck is empty
        while game_over == False:
            round_no += 1
            print(f"\n================ ROUND {round_no} ================")

            # Deal 4 cards to each player (or fewer if deck is running out)
            # Takes up to 4 cards for that player (could be fewer near end of deck).
            # Moves the deck pointer forward by however many cards were actually dealt.
            for player in range(1, size):
                hand = deck[deck_index: deck_index + 4]
                deck_index += len(hand)

                print(f"Dealer sent cards to Player {player}: {hand}")
                comm.send(hand, dest=player, tag=TAG_HAND)
                time.sleep(0.2)

            # If no cards left to place a board card, end the game
            if deck_index >= len(deck):
                game_over = True
                break

            # Start the round by placing a board card
            current_card = deck[deck_index]
            deck_index += 1
            print(f"Dealer placed initial board card: {current_card}")

            round_over = False
            pass_count = 0 # counts how many players passed in a row.

            # --- Round gameplay loop ---
            while not round_over and not game_over:
                turn_signal = "turn"

                # Nawaf: This loop is ONE round-robin cycle (Player 1 -> Player N-1)
                for player in range(1, size):
                    print(f"\nCurrent board card: {current_card}")
                    comm.send((current_card, turn_signal), dest=player, tag=TAG_TURN)

                    # Player responds with (updated_board_card, status)
                    updated_board_card, status = comm.recv(source=player, tag=TAG_RESULT)
                    time.sleep(0.2)

                    # Nawaf: Draw feature handshake:
                    # If player cannot play, they request a draw ("draw").
                    # Dealer must respond exactly once with TAG_DRAW, then player sends a final result.
                    if status == "draw":
                        if deck_index < len(deck):
                            drawn_card = deck[deck_index]
                            deck_index += 1
                        else:
                            drawn_card = None  # deck empty

                        comm.send(drawn_card, dest=player, tag=TAG_DRAW)

                        # Player now sends the final action after drawing (play/pass/win)
                        updated_board_card, status = comm.recv(source=player, tag=TAG_RESULT)
                        time.sleep(0.2)

                    # --- Handle statuses ---
                    if status == "win":
                        # Nawaf: In Task 5, "win" means the player won THIS ROUND (hand became empty)
                        scores[player] += 1
                        current_card = updated_board_card
                        print(f"\n*** Player {player} WON Round {round_no}! (+1 point) ***")
                        round_over = True
                        break

                    elif status == "pass":
                        pass_count += 1
                        print(f"Player {player} passed. pass_count={pass_count}")

                        # If everyone passed, dealer flips a new board card (if available)
                        if pass_count == size - 1:
                            if deck_index < len(deck):
                                current_card = deck[deck_index]
                                deck_index += 1
                                print(f"All players passed. Dealer replaced board card: {current_card}")
                                pass_count = 0
                                # Continue gameplay with new board card
                            else:
                                # Deck empty and everyone passing => end game
                                print("Deck is empty and all players passed. Ending game.")
                                game_over = True
                                round_over = True
                                break
                        continue

                    else:
                        # status == "play"
                        current_card = updated_board_card
                        pass_count = 0
                        print(f"Player {player} played. New board card: {current_card}")

                if round_over or game_over:
                    break

                # Nawaf
                # Dealer can replace the board card by taking a new card from the deck on each round robin cycle
                # After finishing a full cycle through all players, dealer may replace the board card (if deck has cards).
                if deck_index < len(deck):
                    current_card = deck[deck_index]
                    deck_index += 1
                    pass_count = 0
                    print(f"\nDealer replaced board card at end of cycle: {current_card}")
                else:
                    # No more deck cards available for replacement; round may still finish via play/pass logic.
                    print("\nNo more cards left in deck to replace board card at end of cycle.")

            # --- Round ended: notify all players so they stop waiting for turns and prepare for next hand ---
            cards_left = len(deck) - deck_index
            for p in range(1, size):
                # message: (signal, winner_rank_or_None, scores_dict, cards_left)
                winner_rank = None
                # if someone won this round, they already incremented scores and printed above.
                # We'll detect winner by looking for who has max score change is tricky,
                # so we send None or keep it simple: winner not required for logic.
                comm.send(("round_over", None, dict(scores), cards_left), dest=p, tag=TAG_END)

            print(f"\nRound {round_no} ended. Scores: {scores}. Cards left: {cards_left}")

            # If deck empty now, game ends
            if deck_index >= len(deck):
                game_over = True

        # --- Final termination broadcast (no rank should remain blocked on recv) ---
        for p in range(1, size):
            comm.send(("game_over", None, dict(scores), 0), dest=p, tag=TAG_END)

        print("\n================ GAME OVER ================")
        print("Final Scores:")
        for p in range(1, size):
            print(f"Player {p}: {scores[p]}")

    # =========================
    # Player Logic (rank > 0)
    # =========================
    else:
        hand = []
        scores_snapshot = {}

        while True:
            status_obj = MPI.Status()
            msg = comm.recv(source=0, tag=MPI.ANY_TAG, status=status_obj)

            # --- Receive a new hand at the start of each round ---
            if status_obj.Get_tag() == TAG_HAND:
                hand = msg
                print(f"\nPlayer {rank} received hand: {hand}")
                continue

            # --- Turn messages ---
            if status_obj.Get_tag() == TAG_TURN:
                current_card, signal = msg
                if signal != "turn":
                    continue

                print(f"\nPlayer {rank} turn. Board card: {current_card}")
                print(f"Player {rank} hand before: {hand}")

                board_rank = current_card.split(" of ")[0]
                played_card = None

                # Try to play ONE matching card
                for i, card in enumerate(hand):
                    if card.split(" of ")[0] == board_rank:
                        played_card = hand.pop(i)
                        break

                if played_card is not None:
                    print(f"Player {rank} played: {played_card}")

                    if len(hand) == 0:
                        # Empty hand => ROUND WIN
                        comm.send((played_card, "win"), dest=0, tag=TAG_RESULT)
                        print(f"Player {rank} has no cards left -> ROUND WIN!")
                    else:
                        comm.send((played_card, "play"), dest=0, tag=TAG_RESULT)
                        print(f"Player {rank} hand after: {hand}")

                else:
                    # Nawaf: If no match, request a draw (Task 5)
                    comm.send((current_card, "draw"), dest=0, tag=TAG_RESULT)

                    drawn_card = comm.recv(source=0, tag=TAG_DRAW)
                    if drawn_card is not None:
                        hand.append(drawn_card)
                        print(f"Player {rank} drew: {drawn_card}")
                    else:
                        print(f"Player {rank} tried to draw but deck is empty.")

                    # After drawing, try to play ONLY if the drawn card matches
                    played_after_draw = None
                    if drawn_card is not None and drawn_card.split(" of ")[0] == board_rank:
                        hand.pop()  # remove drawn card from hand to play it
                        played_after_draw = drawn_card

                    if played_after_draw is not None:
                        print(f"Player {rank} played after draw: {played_after_draw}")
                        if len(hand) == 0:
                            comm.send((played_after_draw, "win"), dest=0, tag=TAG_RESULT)
                            print(f"Player {rank} has no cards left -> ROUND WIN!")
                        else:
                            comm.send((played_after_draw, "play"), dest=0, tag=TAG_RESULT)
                            print(f"Player {rank} hand after: {hand}")
                    else:
                        comm.send((current_card, "pass"), dest=0, tag=TAG_RESULT)
                        print(f"Player {rank} passed (no match even after draw).")

            # --- End messages: round over or game over ---
            elif status_obj.Get_tag() == TAG_END:
                signal, winner, scores_snapshot, cards_left = msg

                if signal == "round_over":
                    print(f"\nPlayer {rank}: Round over. Scores snapshot: {scores_snapshot}. Cards left: {cards_left}")
                    # Keep running: next TAG_HAND will arrive for the next round
                    continue

                if signal == "game_over":
                    print(f"\nPlayer {rank}: GAME OVER. Final scores: {scores_snapshot}")
                    break


if __name__ == "__main__":
    main()
