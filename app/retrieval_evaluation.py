"""用于回归检查的检索评估：运行时使用真实向量服务，测试时不调用云端。"""

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from app.embedding_client import embed_texts
from app.rerank_client import rerank_results
from app.settings import load_embedding_settings, load_rerank_settings
from app.text_chunker import DocumentChunk
from app.vector_store import SearchResult, VectorStore


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    question: str
    expected_source: str | None


@dataclass(frozen=True)
class EvaluationDetail:
    question: str
    expected_source: str | None
    matched_rank: int | None


@dataclass(frozen=True)
class RetrievalEvaluationReport:
    total_cases: int
    hit_count: int
    recall_at_k: float
    mrr_at_k: float
    details: list[EvaluationDetail]

    def to_dict(self) -> dict:
        return {
            "评测问题数": self.total_cases,
            "命中问题数": self.hit_count,
            "Recall@3": round(self.recall_at_k, 4),
            "MRR@3": round(self.mrr_at_k, 4),
            "明细": [asdict(detail) for detail in self.details],
        }


@dataclass(frozen=True)
class RetrievalComparisonReport:
    answerable_case_count: int
    unanswerable_cases: list[RetrievalEvaluationCase]
    faiss: RetrievalEvaluationReport
    rerank: RetrievalEvaluationReport

    def to_dict(self) -> dict:
        return {
            "有答案问题数": self.answerable_case_count,
            "无答案问题": [case.question for case in self.unanswerable_cases],
            "仅 FAISS": self.faiss.to_dict(),
            "FAISS + Rerank": self.rerank.to_dict(),
        }


EVALUATION_DATA_PATH = Path(__file__).parent.parent / "evals" / "retrieval-cases.json"
FAISS_CANDIDATE_LIMIT = 10
RERANK_RESULT_LIMIT = 3


def load_evaluation_dataset(
    path: Path = EVALUATION_DATA_PATH,
) -> tuple[list[DocumentChunk], list[RetrievalEvaluationCase]]:
    """读取提交到仓库的公开评测数据，不访问用户知识库。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks = [
            DocumentChunk(str(item["source_file"]), 0, str(item["content"]))
            for item in data["documents"]
        ]
        cases = [
            RetrievalEvaluationCase(str(item["question"]), item.get("expected_source"))
            for item in data["cases"]
        ]
    except (KeyError, TypeError, json.JSONDecodeError, OSError) as error:
        raise ValueError("评测数据文件格式错误") from error
    if not chunks or not cases:
        raise ValueError("评测数据不能为空")
    return chunks, cases


def evaluate_retrieval(
    cases: list[RetrievalEvaluationCase],
    results_by_question: dict[str, list[SearchResult]],
    limit: int = 3,
) -> RetrievalEvaluationReport:
    """计算预期来源是否出现在 Top-K 中，并计算平均倒数排名。"""
    answerable_cases = [case for case in cases if case.expected_source]
    if not answerable_cases:
        raise ValueError("评测数据中没有有答案问题")
    if limit <= 0:
        raise ValueError("Top-K 必须大于 0")

    details: list[EvaluationDetail] = []
    hit_count = 0
    reciprocal_rank_sum = 0.0

    for case in answerable_cases:
        results = results_by_question.get(case.question, [])[:limit]
        matched_rank = next(
            (
                index
                for index, result in enumerate(results, start=1)
                if result.source_file == case.expected_source
            ),
            None,
        )
        if matched_rank is not None:
            hit_count += 1
            reciprocal_rank_sum += 1 / matched_rank
        details.append(
            EvaluationDetail(
                question=case.question,
                expected_source=case.expected_source,
                matched_rank=matched_rank,
            )
        )

    total_cases = len(answerable_cases)
    return RetrievalEvaluationReport(
        total_cases=total_cases,
        hit_count=hit_count,
        recall_at_k=hit_count / total_cases,
        mrr_at_k=reciprocal_rank_sum / total_cases,
        details=details,
    )


def run_cloud_evaluation(limit: int = RERANK_RESULT_LIMIT) -> RetrievalComparisonReport:
    """比较 FAISS 与 Rerank，不写入本地或 Supabase 知识库。"""
    chunks, cases = load_evaluation_dataset()
    settings = load_embedding_settings()
    document_vectors = embed_texts([chunk.content for chunk in chunks], settings)
    store = VectorStore(dimension=len(document_vectors[0]))
    store.add(chunks, document_vectors)

    query_vectors = embed_texts([case.question for case in cases], settings)
    faiss_results = {
        case.question: store.search(query_vector, min(FAISS_CANDIDATE_LIMIT, store.count))
        for case, query_vector in zip(cases, query_vectors)
    }
    rerank_settings = load_rerank_settings()
    reranked_results = {
        question: rerank_results(question, results, rerank_settings, min(limit, len(results)))
        for question, results in faiss_results.items()
    }
    return RetrievalComparisonReport(
        answerable_case_count=len([case for case in cases if case.expected_source]),
        unanswerable_cases=[case for case in cases if not case.expected_source],
        faiss=evaluate_retrieval(cases, faiss_results, limit),
        rerank=evaluate_retrieval(cases, reranked_results, limit),
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    report = run_cloud_evaluation()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
