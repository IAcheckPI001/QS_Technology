from app.modules.chatbot.analysis.analyzer import QueryAnalyzer
from app.modules.chatbot.schemas.system import Analysis
from app.modules.chatbot.extraction.validate_registry import plan_turn, resolve


def test_analysis_plan_accepts_sub_query_clarification_without_duplicate_id():
    plan = plan_turn(resolve({
        "sub_queries": [{
            "standalone_query": "Hướng dẫn đấu nguồn cho Astro 6A",
            "intent": "guide.installation",
            "product_models": [],
            "unresolved_mentions": ["Astro 6A"],
            "control_interface": [],
            "spec_attribute": [],
            "handoff_reason": None,
            "history_conflict": False,
        }],
    }))

    analysis = Analysis.from_plan(plan)

    assert analysis.sub_queries[0].clarification is not None
    assert analysis.sub_queries[0].clarification.reason == "ambiguous_product_model"
    assert analysis.clarification is not None
    assert analysis.clarification.sub_query_id == "q1"


def test_analysis_plan_without_clarification_remains_valid():
    plan = plan_turn(resolve({
        "sub_queries": [{
            "standalone_query": "F86 có cổng USB không?",
            "intent": "lookup.product_info",
            "product_models": ["F86"],
            "unresolved_mentions": [],
            "control_interface": [],
            "spec_attribute": ["ports"],
            "handoff_reason": None,
            "history_conflict": False,
        }],
    }))

    analysis = Analysis.from_plan(plan)

    assert analysis.sub_queries[0].clarification is None
    assert analysis.clarification is None
