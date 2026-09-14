"""用于回归检查的检索评估：运行时使用真实向量服务，测试时不调用云端。"""

import json
import sys
from dataclasses import asdict, dataclass

from app.embedding_client import embed_texts
from app.settings import load_embedding_settings
from app.text_chunker import DocumentChunk
from app.vector_store import SearchResult, VectorStore


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    question: str
    expected_source: str


@dataclass(frozen=True)
class EvaluationDetail:
    question: str
    expected_source: str
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


EVALUATION_CHUNKS = [
    DocumentChunk("library_guide.md", 0, "图书馆每天开放至晚上十点，借阅图书需携带校园卡。"),
    DocumentChunk("network_service.md", 0, "校园网络无法连接时，请联系信息中心提交报修申请。"),
    DocumentChunk("scholarship_policy.md", 0, "奖学金申请需要在规定时间提交成绩单和申请表。"),
    DocumentChunk("course_selection.md", 0, "选课系统开放期间可以查询课程容量并提交退选申请。"),
]

EVALUATION_CASES = [
    RetrievalEvaluationCase("图书馆几点关门？", "library_guide.md"),
    RetrievalEvaluationCase("校园网络坏了怎么报修？", "network_service.md"),
    RetrievalEvaluationCase("申请奖学金要准备什么？", "scholarship_policy.md"),
    RetrievalEvaluationCase("怎样查看课程还有没有名额？", "course_selection.md"),
]


def evaluate_retrieval(
    cases: list[RetrievalEvaluationCase],
    results_by_question: dict[str, list[SearchResult]],
    limit: int = 3,
) -> RetrievalEvaluationReport:
    """计算预期来源是否出现在 Top-K 中，并计算平均倒数排名。"""
    if not cases:
        raise ValueError("评测问题不能为空")
    if limit <= 0:
        raise ValueError("Top-K 必须大于 0")

    details: list[EvaluationDetail] = []
    hit_count = 0
    reciprocal_rank_sum = 0.0

    for case in cases:
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

    total_cases = len(cases)
    return RetrievalEvaluationReport(
        total_cases=total_cases,
        hit_count=hit_count,
        recall_at_k=hit_count / total_cases,
        mrr_at_k=reciprocal_rank_sum / total_cases,
        details=details,
    )


def run_cloud_evaluation(limit: int = 3) -> RetrievalEvaluationReport:
    """调用真实向量服务执行固定评测集，不写入用户的本地知识库。"""
    settings = load_embedding_settings()
    document_vectors = embed_texts([chunk.content for chunk in EVALUATION_CHUNKS], settings)
    store = VectorStore(dimension=len(document_vectors[0]))
    store.add(EVALUATION_CHUNKS, document_vectors)

    query_vectors = embed_texts([case.question for case in EVALUATION_CASES], settings)
    results_by_question = {
        case.question: store.search(query_vector, limit)
        for case, query_vector in zip(EVALUATION_CASES, query_vectors)
    }
    return evaluate_retrieval(EVALUATION_CASES, results_by_question, limit)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    report = run_cloud_evaluation()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
