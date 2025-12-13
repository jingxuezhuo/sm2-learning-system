from datetime import datetime, timedelta

class SM2Card:
    """
    Represents a single spaced-repetition memory card.
    Each card corresponds to one LeetCode problem.
    Stores key scheduling attributes used by the SM-2 spaced repetition algorithm.
    """
    
    def __init__(self, card_id, first_date):
        """
        Initialize all card properties.
        Parameters:
            card_id(str): problem ID
            first_date(str): The date when the card was solved for the first time
        """
        # User-defined fields
        self.card_id = card_id
        self.first_date = first_date
        
        # Fields initialized with default SM-2 values
        self.ef = 2.5
        self.n = 0
        self.interval = 0
        self.next_review = None
        self.review_count = 0
        
        # 新增字段
        self.name = ''  # 题目名称
        self.tags = []  # 标签列表
        self.note = ''  # 备注内容
        self.images = []  # 图片文件名列表

    def review(self, q, review_date):
        """
        Perform one review cycle using SM-2 scheduling rules.
        Parameters
            q: Performance rating (0-5 integer)
            review_date(datetime): Date when this review occurs
        """
        # Update EF
        self.ef = max(1.3, self.ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
        # Adjust review interval based on score
        if q < 3:
            self.n = 0
            self.interval = 1
        else:
            self.n += 1
            if self.n == 1:
                self.interval = 1
            elif self.n == 2:
                self.interval = 6
            else:
                self.interval = round(self.interval * self.ef)

        # Compute next review date
        self.next_review = review_date + timedelta(days=self.interval)

        # Count total review attempts
        self.review_count += 1