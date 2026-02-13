from mpi4py import MPI
import random
import time

TAG_HAND = 10
TAG_TURN = 20
TAG_RESULT = 30
TAG_END = 40

# Setting up the game
def createDeck():
    # Define suits and ranks
    suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
    
    # Create the deck using a list comprehension
    created_deck = [f"{rank} of {suit}" for suit in suits for rank in ranks]
    
    # Shuffle the deck
    random.shuffle(created_deck)
    return created_deck

def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size() # Number of processes (players)
    deck = []
    
    # Dealer Logic        
    if rank == 0:
        deck = createDeck()
        
        # Send 4 cards to each player
        for player in range(1, size):
            print(f"Dealer sent cards to Player {player}")
            comm.send(deck[(player-1)*4 : player*4], dest=player, tag=TAG_HAND)
            time.sleep(1) # Simulate time for sending cards
        
        # Start the game by sending the first card
        deck_index = 4*(size-1) # Index to keep track of the next card to draw
        current_card = deck[deck_index]
        game_over = False
        
        while not game_over:
            pass_count = 0
            turn_signal = "turn"
            end_game_signal = "win"
            
            for player in range(1, size): # Loop through all players start with player one
                print(f"Current card: {current_card}")
                
                comm.send((current_card, turn_signal), dest=player, tag=TAG_TURN)
                updated_board_card, status = comm.recv(source=player, tag=TAG_RESULT) # Wait for player's response
                time.sleep(1) # Simulate time for player to respond
  
                if status == "win":
                    current_card = updated_board_card
                    # Send win signal to all players
                    for p in range(1, size):
                        comm.send((current_card, end_game_signal), dest=p, tag=TAG_END)
                    game_over = True
                    break
                
                elif status == "pass":
                    pass_count +=1
                    if pass_count == size - 1: # If all players have passed
                        if deck_index + 1 < len(deck):
                            deck_index += 1
                        else:
                            # If no more cards in deck, end the game
                            for p in range(1, size):
                                comm.send((current_card, end_game_signal), dest=p, tag=TAG_END)
                            game_over = True
                            break
                        current_card = deck[deck_index]
                        pass_count = 0 # Reset pass count for the next card
                    continue 
                   
                else:
                    current_card = updated_board_card # Update the current card with player's response

    # Player Logic
    elif rank > 0:
        hand = comm.recv(source=0, tag=TAG_HAND) # Receive initial hand of cards
        print(f"Player {rank} received hand: {hand}")
      
        while True:
            status_obj = MPI.Status()
            msg = comm.recv(source=0, tag=MPI.ANY_TAG, status=status_obj) # Wait for the current card and turn signal
            if status_obj.Get_tag() == TAG_TURN:
                current_card, signal = msg
                if signal == "turn":
                    print(f"Player {rank} turn. Board card: {current_card}")
                    print(f"Player {rank} hand before: {hand}")
                    board_rank = current_card.split(" of ")[0]
                    played_card = None
                    for i, card in enumerate(hand):
                        if card.split(" of ")[0] == board_rank:
                            played_card = hand.pop(i)   # remove ONE matching card
                            break
                    if played_card is not None:
                        print(f"Player {rank} played: {played_card}")
                        if len(hand) == 0:
                            # Empty hand => send "win" signal to dealer
                            comm.send((played_card, "win"), dest=0, tag=TAG_RESULT)
                            print(f"Player {rank} has no cards left -> WIN!")
                        else:
                            # Normal play: played card becomes new board card
                            comm.send((played_card, "play"), dest=0, tag=TAG_RESULT)
                            print(f"Player {rank} hand after: {hand}")
                    else:
                        # No match => send "pass" signal to dealer
                        comm.send((current_card, "pass"), dest=0, tag=TAG_RESULT)
                        print(f"Player {rank} passed (no match).")
            elif status_obj.Get_tag() == TAG_END:
                current_card, signal = msg
                if signal == "win": # Win signal indicates the game has ended
                    print(f"Player {rank} exits the game.")
                break

if __name__ == "__main__":
    main()