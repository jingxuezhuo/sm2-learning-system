# Final Project
# Name: Jingxue Zhuo
# Date: 12/01/2025
# Class: CS 5001
# The SM2System class manages all review cards in the SM-2 spaced repetition system. It stores, updates, and retrieves cards based on when they are due for review. It also loads and saves all card data to a JSON file so progress is preserved across sessions


import json
from datetime import datetime
from sm2_card import SM2Card


class SM2System:
    """SM-2 Memory System - Manages all SM-2 spaced repetition cards"""
    
    def __init__(self, file_name='sm2_data.json'):
        """
        Initialize the SM-2 review system.
        Parameters :
            file_name(str): Path to the JSON save file, default is 'sm2_data.json'
        """
        self.cards = {}  # Dictionary storing all cards: key = card ID, value = SM2Card object
        self.file = file_name  # Data file path
        self._load()  # Load data at startup
    

    def add_card(self, card_id, first_date, score, review_date):
        """
        Add a new card to the system.
         Parameters:
            card_id (str): ID of a LeetCode problem.
            first_date (str): First day the card was solved, formatted as 'YYYY-MM-DD'.
            score (int): Rating for this attempt (0–5).
            review_date (datetime): Timestamp of this review (even the first attempt counts as a review).
        """
        c = SM2Card(card_id, first_date)  # Create the card object
        c.review(score, review_date)  # Perform the first review immediately
        self.cards[card_id] = c  # Save card into the system
        self._save()  # Persist changes
    

    def get_due_cards(self, today):
        """
        Get cards that are due for review on the given date.
        Parameters:
            today(datetime): The date to check due cards for
        """
        result = []
        for c in self.cards.values():
            # A card is due if the next review date is today or earlier
            if c.next_review and c.next_review <= today:
                result.append(c)
        result.sort(key=lambda x: x.card_id)
        return result
    

    def review_card(self, card_id, score, review_date):
        """
        Review an existing card.
        Parameters:
            card_id (str): ID of the card to review.
            score (int): Rating after reviewing the card (0–5).
            review_date (datetime): Timestamp for this review attempt.
        Notes:
            If the card does not exist, simply return.
        """
        card = self.cards.get(card_id)
        if not card:  # Not found in system
            return
        
        card.review(score, review_date)
        self._save()  # Save updated card stats
    

    def _save(self):
        """
        Save all card data to the JSON file.
        JSON does not support partial updates, so rewrite all data when saving.
        """
        out = {}
        for cid, c in self.cards.items():
            out[cid] = {
            'first_date': c.first_date,
            'ef': c.ef,
            'n': c.n,
            'interval': c.interval,
            'next_review': c.next_review.strftime('%Y-%m-%d') if c.next_review else None,
            'review_count': c.review_count,
            'name': c.name,
            'tags': c.tags,
            'note': c.note,
            'images': c.images
}
            
        # Write updated data into JSON, auto-closing with `with` statement
        with open(self.file, 'w', encoding='utf-8') as f:
            # ensure_ascii=False allows non-ASCII characters
            json.dump(out, f, ensure_ascii=False, indent=2) # use dump to write data into json. reference：https://docs.python.org/3/library/json.html
    

    def _load(self):
        """
        Load card data from the JSON file when system starts.
        Ensure previous data persists across sessions.
        """
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)  # Load data from  files into the program memory. https://docs.python.org/3/library/json.html
        except FileNotFoundError:
            return  # No file yet → first run, so just return

        # Rebuild SM2Card objects from saved data
        for cid, info in data.items():
            card = SM2Card(cid, info['first_date'])
            card.ef = info.get('ef', 2.5)
            card.n = info.get('n', 0)
            card.interval = info.get('interval', 0)
            nr = info.get('next_review')
            card.next_review = datetime.strptime(nr, '%Y-%m-%d') if nr else None
            card.review_count = info.get('review_count', 0)
            card.name = info.get('name', '')
            card.tags = info.get('tags', [])
            card.note = info.get('note', '')
            card.images = info.get('images', [])

            # Store card back into the system so reviews can continue
            self.cards[cid] = card
