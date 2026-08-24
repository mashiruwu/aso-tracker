import unittest
from difficulty import (
    calculate_rating_strength,
    calculate_large_competitors,
    calculate_title_competition,
    calculate_difficulty
)

class TestDifficulty(unittest.TestCase):

    def test_rating_strength(self):
        # Test basic progression
        self.assertLess(
            calculate_rating_strength([{"rating_count": 10}]),
            calculate_rating_strength([{"rating_count": 100}])
        )
        self.assertLess(
            calculate_rating_strength([{"rating_count": 1000}]),
            calculate_rating_strength([{"rating_count": 100000}])
        )
        
        # 10 -> log10(11) = ~1.04 -> (1.04-1)/5 = ~0.8%
        score_10 = calculate_rating_strength([{"rating_count": 10}])
        self.assertTrue(0 <= score_10 <= 2)
        
        # 1M -> log10(1M+1) = ~6 -> (6-1)/5 = 100%
        score_1m = calculate_rating_strength([{"rating_count": 1000000}])
        self.assertEqual(score_1m, 100)

    def test_large_competitors(self):
        apps_0 = [{"rating_count": 10} for _ in range(10)]
        self.assertEqual(calculate_large_competitors(apps_0), 0)
        
        apps_5 = [{"rating_count": 100000} for _ in range(5)] + [{"rating_count": 10} for _ in range(5)]
        self.assertEqual(calculate_large_competitors(apps_5), 50)
        
        apps_10 = [{"rating_count": 100000} for _ in range(10)]
        self.assertEqual(calculate_large_competitors(apps_10), 100)

    def test_title_competition(self):
        # Strong match
        apps = [{"name": "AI Flashcards Maker"}]
        self.assertEqual(calculate_title_competition("ai flashcards", apps), 100)
        
        # Partial match
        apps = [{"name": "Flashcards & Quiz"}]
        self.assertEqual(calculate_title_competition("ai flashcards", apps), 50)
        
        # No match
        apps = [{"name": "Study Smarter"}]
        self.assertEqual(calculate_title_competition("ai flashcards", apps), 0)

    def test_calculate_difficulty(self):
        apps = [
            {"name": "AI Flashcards Maker", "rating_count": 100000},
            {"name": "Flashcards & Quiz", "rating_count": 1000},
            {"name": "Study Smarter", "rating_count": 10}
        ]
        diff = calculate_difficulty("ai flashcards", apps)
        self.assertIn("score", diff)
        self.assertIn("label", diff)
        self.assertIn("rating_strength", diff)
        self.assertIn("large_competitors", diff)
        self.assertIn("title_competition", diff)

if __name__ == "__main__":
    unittest.main()
