from datetime import datetime, timedelta, timezone
import unittest
from services.matchmaker import MatchmakerService


class TestMatchmakerService(unittest.TestCase):
    def setUp(self):
        self.service = MatchmakerService()
        self.now = datetime.now(timezone.utc)

    def test_empty_list(self):
        users = []
        history = {}

        pairs, unmatched = self.service.create_pairs(users, history)

        self.assertEqual(pairs, [])
        self.assertEqual(unmatched, [])

    def test_single_user(self):
        users = [101]
        history = {}

        pairs, unmatched = self.service.create_pairs(users, history)

        self.assertEqual(pairs, [])
        self.assertEqual(unmatched, [101])

    def test_simple_pairing_no_history(self):
        users = [1, 2, 3, 4]
        history = {}

        pairs, unmatched = self.service.create_pairs(users, history)

        self.assertEqual(len(pairs), 2)
        self.assertEqual(len(unmatched), 0)
        flattened_users = [u for pair in pairs for u in pair]
        self.assertCountEqual(flattened_users, users)

    def test_avoid_past_pairs(self):
        users = [1, 2, 3, 4]
        history = {(1, 2): self.now - timedelta(hours=1), (3, 4): self.now - timedelta(hours=1)}

        pairs, _ = self.service.create_pairs(users, history)

        self.assertEqual(len(pairs), 2)
        forbidden_pair_1 = (1, 2)
        forbidden_pair_2 = (3, 4)
        self.assertNotIn(forbidden_pair_1, pairs, "Repeated meeting (1, 2)")
        self.assertNotIn(forbidden_pair_2, pairs, "Repeated meeting (3, 4)")

    def test_odd_number_of_users(self):
        users = [1, 2, 3, 4, 5]
        history = {}

        pairs, unmatched = self.service.create_pairs(users, history)

        self.assertEqual(len(pairs), 2)
        self.assertEqual(len(unmatched), 1)

    def test_prefer_older_meeting_when_forced(self):
        users = [1, 2, 3, 4]
        history = {
            (1, 2): self.now - timedelta(hours=1),  # Recent
            (3, 4): self.now - timedelta(days=3650),  # 10 Years ago (Oldest)
            # Cross pairs met very recently
            (1, 3): self.now - timedelta(minutes=1),
            (1, 4): self.now - timedelta(minutes=1),
            (2, 3): self.now - timedelta(minutes=1),
            (2, 4): self.now - timedelta(minutes=1),
        }

        pairs, _ = self.service.create_pairs(users, history)

        self.assertIn((3, 4), pairs, "Should pick the oldest pair (3, 4)")
        self.assertIn((1, 2), pairs, "Should pick (1, 2) as the best remaining option")


if __name__ == "__main__":
    unittest.main()
