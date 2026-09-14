import unittest

from app.retrieval_evaluation import RetrievalEvaluationCase, evaluate_retrieval
from app.vector_store import SearchResult


class RetrievalEvaluationTests(unittest.TestCase):
    def test_calculates_recall_and_mrr_at_k(self) -> None:
        cases = [
            RetrievalEvaluationCase("问题一", "guide.md"),
            RetrievalEvaluationCase("问题二", "network.md"),
            RetrievalEvaluationCase("问题三", "scholarship.md"),
        ]
        results = {
            "问题一": [SearchResult("guide.md", 0, "内容", 0.9)],
            "问题二": [
                SearchResult("guide.md", 0, "内容", 0.9),
                SearchResult("network.md", 0, "内容", 0.8),
            ],
            "问题三": [SearchResult("guide.md", 0, "内容", 0.9)],
        }

        report = evaluate_retrieval(cases, results, limit=3)

        self.assertEqual(report.total_cases, 3)
        self.assertEqual(report.hit_count, 2)
        self.assertAlmostEqual(report.recall_at_k, 2 / 3)
        self.assertAlmostEqual(report.mrr_at_k, 0.5)
        self.assertEqual(report.details[0].matched_rank, 1)
        self.assertEqual(report.details[1].matched_rank, 2)
        self.assertIsNone(report.details[2].matched_rank)
