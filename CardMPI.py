from mpi4py import MPI
import random
import time

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
            comm.send(deck[(player-1)*4 : player*4], dest=player)
            print(f"Dealer sent cards to Player {player}")
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
                
                comm.send((current_card, turn_signal), dest=player)
                updated_board_card, status = comm.recv(source=player) # Wait for player's response
                time.sleep(1) # Simulate time for player to respond
                
                if status == "win":
                    # Send win signal to all players
                    for p in range(1, size):
                        comm.send((current_card, end_game_signal), dest=p)
                    game_over = True
                    break
                
                elif status == "pass":
                    pass_count +=1
                    if pass_count == size - 2: # If all players have passed
                        if deck_index + 1 < len(deck):
                            deck_index += 1
                        else:
                            # If no more cards in deck, end the game
                            for p in range(1, size):
                                comm.send((current_card, end_game_signal), dest=p)
                            game_over = True
                            break
                        current_card = deck[deck_index]
                        pass_count = 0 # Reset pass count for the next card
                    continue 
                   
                else:
                    current_card = updated_board_card # Update the current card with player's response

    # Player Logic
    else:
        hand = comm.recv(source=0) # Receive initial hand of cards
        
        while True:
            current_card, signal = comm.recv(source=0) # Wait for the current card and turn signal
            if signal == "turn":
                print(f"Player {rank} received card: {current_card}")
                # Do stuff...
            elif signal == "win": # Win signal indicates the game has ended
                print(f"Player {rank} exits the game.")
                break
            