"""Compiles the two graphs the API actually invokes.

There's no long-lived graph process or checkpointer spanning HTTP requests — each request
re-hydrates an InterviewState from Supabase (see pipeline.py) and runs one of these graphs to
completion, synchronously, within that single request. Supabase is the durable state; these
graphs are the branching logic on top of it, matching the plan's section 4 node design:

    0. analyze_profile        (start_graph)
    1. generate_question   ⇄  (turn_graph, via route_after_eval)
    2. evaluate_answer
    3. route_after_eval        — the real conditional branch
    4. summarize_session       — runs once, when route_after_eval picks "end"
"""

from langgraph.graph import END, StateGraph

from app.graph import nodes
from app.graph.state import InterviewState


def build_start_graph():
    """analyze_profile -> generate_question (first, fresh) -> END. Used by POST /sessions."""
    graph = StateGraph(InterviewState)
    graph.add_node("analyze_profile", nodes.analyze_profile_node)
    graph.add_node("generate_question", nodes.generate_question_node)

    graph.set_entry_point("analyze_profile")
    graph.add_edge("analyze_profile", "generate_question")
    graph.add_edge("generate_question", END)
    return graph.compile()


def build_turn_graph():
    """evaluate_answer -> route_after_eval -> {followup|next_question -> generate_question,
    end -> summarize_session}. Used by POST /sessions/{id}/answer — this is the genuine
    branching logic from the plan: a real decision based on the evaluator's actual output,
    not a scripted turn count. Ending the session automatically runs the summarizer, so
    scores/feedback are ready the moment the interview naturally concludes."""
    graph = StateGraph(InterviewState)
    graph.add_node("evaluate_answer", nodes.evaluate_answer_node)
    graph.add_node("prepare_followup", nodes.prepare_followup)
    graph.add_node("prepare_next_question", nodes.prepare_next_question)
    graph.add_node("generate_question", nodes.generate_question_node)
    graph.add_node("mark_has_next", nodes.mark_has_next_question)
    graph.add_node("summarize_session", nodes.summarize_session_node)
    graph.add_node("mark_complete", nodes.mark_interview_complete)

    graph.set_entry_point("evaluate_answer")
    graph.add_conditional_edges(
        "evaluate_answer",
        nodes.route_after_eval,
        {
            "followup": "prepare_followup",
            "next_question": "prepare_next_question",
            "end": "summarize_session",
        },
    )
    graph.add_edge("prepare_followup", "generate_question")
    graph.add_edge("prepare_next_question", "generate_question")
    graph.add_edge("generate_question", "mark_has_next")
    graph.add_edge("mark_has_next", END)
    graph.add_edge("summarize_session", "mark_complete")
    graph.add_edge("mark_complete", END)
    return graph.compile()


start_graph = build_start_graph()
turn_graph = build_turn_graph()
