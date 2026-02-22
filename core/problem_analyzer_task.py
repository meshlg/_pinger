"""Problem analysis background task."""

from __future__ import annotations

from config import ENABLE_PROBLEM_ANALYSIS, PROBLEM_ANALYSIS_INTERVAL
from core.background_task import BackgroundTask
from problem_analyzer import ProblemAnalyzer


class ProblemAnalyzerTask(BackgroundTask):
    """Periodically analyze network problems and patterns."""

    def __init__(self, *, problem_analyzer: ProblemAnalyzer, **kw) -> None:
        super().__init__(
            name="ProblemAnalyzer",
            interval=PROBLEM_ANALYSIS_INTERVAL,
            enabled=ENABLE_PROBLEM_ANALYSIS,
            **kw,
        )
        self.problem_analyzer = problem_analyzer

    async def execute(self) -> None:
        problem_type = self.problem_analyzer.analyze_current_problem()
        prediction = self.problem_analyzer.predict_problems(problem_type)
        pattern = self.problem_analyzer.identify_pattern()

        self.stats_repo.update_problem_analysis(problem_type, prediction, pattern)
