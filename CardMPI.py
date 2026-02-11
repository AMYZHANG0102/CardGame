from mpi4py import MPI
import random

def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    deck = []
    
    def createDeck():
        # Define suits and ranks
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        
        # Create the deck using a list comprehension
        deck = [f"{rank} of {suit}" for suit in suits for rank in ranks]
        
        # Shuffle the deck
        random.shuffle(deck)
        
        # Send 4 cards to each player
        for player in range(size):
            hand = deck[player*4 : (player+1)*4]
            if rank == 0:
                comm.send(hand, dest=player)
            if rank == player:
                hand = comm.recv(source=0)
                print(f"Player {rank} received hand: {hand}")
                
    if rank == 0:
        createDeck()
                    
        current_card = deck[4*size:]
        