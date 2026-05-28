from xdrs_compiler.workflows.compile.routes import route_after_judge, route_after_verification


class TestRouteAfterJudge:
    def test_routes_to_generate_policies_when_approved(self) -> None:
        state = {"judge_approved": True, "analysis_iteration": 0}
        assert route_after_judge(state) == "generate_policies"  # type: ignore[arg-type]

    def test_routes_to_generate_policies_at_iteration_limit(self) -> None:
        state = {"judge_approved": False, "analysis_iteration": 2}
        assert route_after_judge(state) == "generate_policies"  # type: ignore[arg-type]

    def test_routes_back_to_analyze_docs_when_not_approved(self) -> None:
        state = {"judge_approved": False, "analysis_iteration": 1}
        assert route_after_judge(state) == "analyze_docs"  # type: ignore[arg-type]

    def test_routes_back_at_iteration_zero_not_approved(self) -> None:
        state = {"judge_approved": False, "analysis_iteration": 0}
        assert route_after_judge(state) == "analyze_docs"  # type: ignore[arg-type]


class TestRouteAfterVerification:
    def test_routes_to_write_output_when_verified(self) -> None:
        state = {"verification_passed": True, "verification_iteration": 1}
        assert route_after_verification(state) == "write_output"  # type: ignore[arg-type]

    def test_routes_back_to_generation_before_retry_limit(self) -> None:
        state = {"verification_passed": False, "verification_iteration": 1}
        assert route_after_verification(state) == "generate_policies"  # type: ignore[arg-type]

    def test_routes_to_report_at_retry_limit(self) -> None:
        state = {"verification_passed": False, "verification_iteration": 2}
        assert route_after_verification(state) == "report"  # type: ignore[arg-type]
