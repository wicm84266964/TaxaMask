from __future__ import annotations

import json


PROMPT_VERSION = "paper_distill/conversation_distill/v6"
KNOWLEDGE_MAP_VERSION = "paper_distill/knowledge_map/v1"
CONVERSATION_PLAN_VERSION = "paper_distill/conversation_plan/v1"
SOURCE_MARKDOWN_MARKER = "[[SOURCE_MARKDOWN]]"
KNOWLEDGE_MAP_MARKER = "[[KNOWLEDGE_MAP]]"


def build_stable_prefix(*, title: str, normalized_source: str) -> str:
    lines = [
        "You distill a single paper into context-rich training conversations and QA pairs.",
        f"Prompt-Version: {PROMPT_VERSION}",
        "The primary goal is knowledge distillation, not trivia extraction.",
        "Write knowledge-oriented training data, not article-oriented commentary about 'this paper' or 'this study'.",
        "Generate grounded multi-turn user/assistant exchanges only from the provided source.",
        "Do not invent claims, citations, or details not supported by the source.",
        "Prefer evidence from methods, results, discussion, tables, and figures when available.",
        "Use abstract-only evidence only when the body does not provide the needed detail.",
        "Each turn should remain understandable from the current thread history without hidden context.",
        "Questions should carry enough local study context near the beginning to avoid feeling fragmented.",
        "Answers should restate the relevant study object, treatment, comparison, or metric before the finding.",
        "Even in a continuous thread, write each question and answer so the subject is explicit near the beginning instead of relying on deictic continuity alone.",
        "Prefer direct subject openings such as '在红火蚁...' over meta-study phrasing such as '这项研究', '这项试验', '该研究', or '该试验'.",
        "Avoid unresolved article-internal references such as 本文, 该文, 这篇文章, 图1, 图2, 表1, 表2, 前者, 后者, 上述, 以下.",
        "Avoid opening with continuity-only phrasing such as 前面已经说到, 继续, 最后, 进一步, 这种, 这样, 它, 它们 unless the same sentence immediately names the concrete study subject or condition.",
        "If a figure or table supports the evidence, put that reference in evidence_locator, and restate the concrete comparison or finding in the question and answer.",
        "Write the question and answer in Chinese even when the source paper is in English.",
        "Translate grounded source content into natural Chinese instead of preserving English sentence structure.",
        "Each item must include question, answer, evidence_text, and evidence_locator.",
        SOURCE_MARKDOWN_MARKER,
        f"Title: {title}",
        normalized_source.rstrip("\n"),
    ]
    return "\n\n".join(lines).strip() + "\n"


def build_knowledge_map_prefix(*, title: str, normalized_source: str) -> str:
    lines = [
        "You extract a reusable knowledge map from a single paper.",
        f"Knowledge-Map-Version: {KNOWLEDGE_MAP_VERSION}",
        "Return grounded structured data only from the provided source.",
        "Capture the study goal, object, design, treatments, metrics, findings, limitations, and recommendations.",
        "Prefer the paper body over the abstract when both are available.",
        "Write all extracted schema string fields in Chinese even when the source paper is in English.",
        SOURCE_MARKDOWN_MARKER,
        f"Title: {title}",
        normalized_source.rstrip("\n"),
    ]
    return "\n\n".join(lines).strip() + "\n"


def build_knowledge_map_suffix() -> str:
    payload = {
        "task": "build_knowledge_map",
        "response_schema": {
            "content_profile": "abstract_only|body_available|mixed_or_unclear",
            "primary_language": "zh|en|mixed",
            "study_goal": "string",
            "study_object": "string",
            "experimental_design": "string",
            "sections_present": ["string"],
            "treatments_or_conditions": ["string"],
            "core_metrics": ["string"],
            "key_findings": ["string"],
            "limitations": ["string"],
            "recommendations": ["string"],
        },
        "requirements": [
            "Return ONLY valid JSON.",
            "Each field must be grounded in the source.",
            "Use concise phrases rather than long paragraphs.",
            "Include 2 to 8 items for list fields when the source supports them.",
            "Use content_profile=abstract_only when the source is mostly abstract metadata without a real body.",
            "Prefer methods, results, discussion, tables, and figures over abstract-only restatements when available.",
            "Write all non-enum schema values in Chinese.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_conversation_plan_prefix(*, title: str, knowledge_map_outline: dict[str, object]) -> str:
    lines = [
        "You plan one paper-distillation conversation set from a reusable knowledge map.",
        f"Conversation-Plan-Version: {CONVERSATION_PLAN_VERSION}",
        "Design 1 to 3 coherent conversation threads that together cover the paper's most valuable knowledge.",
        "Prefer a small number of dense, context-preserving threads over many shallow threads.",
        "Size each thread around distinct knowledge coverage rather than filling a large turn budget with near-repeated questions.",
        "Plan threads around transferable knowledge clusters, not around article navigation phrases such as 'the paper says' or 'Figure 1/Table 1'.",
        "Write topic, rationale, must_cover, and start_context in Chinese even when the source paper is in English.",
        "If the paper has body results, do not let the whole plan collapse into repeated setup-only turns.",
        KNOWLEDGE_MAP_MARKER,
        f"Title: {title}",
        _format_outline_json(knowledge_map_outline),
    ]
    return "\n\n".join(lines).strip() + "\n"


def build_conversation_plan_suffix(*, target_turn_count: int) -> str:
    payload = {
        "task": "build_conversation_plan",
        "response_schema": {
            "threads": [
                {
                    "topic": "string",
                    "rationale": "string",
                    "turn_budget": "integer",
                    "must_cover": ["string"],
                    "start_context": "string",
                }
            ]
        },
        "requirements": [
            "Return ONLY valid JSON.",
            "Return 1 to 3 threads.",
            "The sum of thread turn_budget values should match the requested target_turn_count.",
            "Each thread should cover a distinct knowledge cluster rather than lightly rephrasing another thread.",
            "If the paper is abstract-only or highly compressed, prefer a single thread.",
            "Each start_context must be a concise standalone setup for that thread.",
            "Each must_cover list should contain 2 to 5 grounded coverage points.",
            "For body-rich papers, a thread normally needs about one turn per must_cover point, with at most one extra synthesis turn.",
            "Do not inflate a thread budget by repeating the same result cluster with slightly different wording.",
            "If target_turn_count is 4 or less and the paper body has results, spend at most 1 turn on setup or design before moving to results, comparisons, limitations, or recommendations.",
            "Do not assign every turn to methods or setup if the knowledge map contains quantitative findings or comparisons.",
            "Write every thread field in Chinese.",
        ],
        "target_turn_count": target_turn_count,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_generation_suffix(
    *,
    next_ordinal: int,
    batch_size: int,
    target_count: int,
    existing_questions: tuple[str, ...],
    knowledge_map_outline: dict[str, object] | None = None,
) -> str:
    payload = {
        "task": "continue_paper_distillation",
        "response_schema": {
            "items": [
                {
                    "question": "string",
                    "answer": "string",
                    "evidence_text": "string",
                    "evidence_locator": "string",
                }
            ]
        },
        "requirements": [
            "Return ONLY valid JSON.",
            "Return exactly the requested number of items.",
            "Each question must be self-contained and understandable without previous turns.",
            "Each question should include enough local context to stand alone.",
            "Include the study object, treatment or condition, time point or setting, and metric or comparison whenever the source supports them.",
            "Make the subject explicit near the beginning of the question instead of relying on continuity-only phrasing.",
            "Prefer direct subject openings instead of starting the question with 这项研究, 这项试验, 该研究, 该试验, 本研究, or 本试验 when the concrete subject can be named directly.",
            "Do not ask context-poor questions such as 'What happened next?', 'Why?', or 'What was the result?' without naming the study context.",
            "Each answer must start by restating the relevant study context before giving the finding.",
            "Make the subject explicit near the beginning of the answer instead of relying on phrases like 这种, 这样, 它, or 它们 alone.",
            "Prefer direct subject openings instead of starting the answer with 这项研究, 这项试验, 该研究, 该试验, 本研究, or 本试验 when the concrete subject can be named directly.",
            "Continuity phrases such as 前面已经说到, 继续, 最后, 进一步, 这种, 这样, 它, and 它们 are allowed only when the same sentence also names the concrete study object, treatment, condition, metric, or application scene.",
            "Keep answers concise but faithful to the source, and include key numbers when present.",
            "Prefer methods, results, discussion, tables, and figures over abstract-only restatements when the body contains the needed evidence.",
            "Write both questions and answers in Chinese even when the source paper is in English.",
            "Diversify coverage across study goal, design, methods, results, comparison, interpretation, limitations, and recommendation when supported by the source.",
            "Avoid repeating or lightly rephrasing any existing question.",
            "Evidence text should be a short source-grounded excerpt or paraphrase anchor.",
            "Evidence locator should name the section, table, or figure when possible.",
        ],
        "coverage_phase": _coverage_phase(next_ordinal=next_ordinal, target_count=target_count),
        "next_ordinal": next_ordinal,
        "batch_size": batch_size,
        "target_count": target_count,
        "existing_questions": list(existing_questions),
    }
    if knowledge_map_outline is not None:
        payload["knowledge_map"] = knowledge_map_outline
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_conversation_generation_suffix(
    *,
    conversation_id: str,
    thread_plan: dict[str, object],
    batch_size: int,
    remaining_turns_in_thread: int,
    existing_thread_turns: tuple[dict[str, str], ...],
    existing_questions: tuple[str, ...],
    knowledge_map_outline: dict[str, object],
) -> str:
    payload = {
        "task": "generate_conversation_turns",
        "response_schema": {
            "items": [
                {
                    "question": "string",
                    "answer": "string",
                    "evidence_text": "string",
                    "evidence_locator": "string",
                }
            ]
        },
        "requirements": [
            "Return ONLY valid JSON.",
            "Return exactly the requested number of items.",
            "Preserve continuity with the existing thread turns without relying on hidden context outside the thread.",
            "The first newly generated turn in a thread should re-establish the study object and setting if the thread is still early.",
            "Questions must not be fragmentary. Name the study object, treatment, comparison, condition, metric, or time point whenever the source supports them.",
            "Questions should make the subject explicit near the beginning, even when the thread is continuous.",
            "Prefer direct subject openings instead of opening the question with 这项研究, 这项试验, 该研究, 该试验, 本研究, or 本试验 when the concrete subject can be named directly.",
            "Answers must begin with the relevant study context before giving the result or interpretation.",
            "Answers should make the subject explicit near the beginning, even when the thread is continuous.",
            "Prefer direct subject openings instead of opening the answer with 这项研究, 这项试验, 该研究, 该试验, 本研究, or 本试验 when the concrete subject can be named directly.",
            "Avoid article-internal shorthand such as 本文, 该文, 这篇文章, 图1, 图2, 表1, 表2, 前者, 后者, 上述, 以下 in the question or answer.",
            "If you use a phrase like 这项研究 or 该试验, immediately ground it in the same sentence with the study object, treatment, metric, or condition.",
            "Continuity phrases such as 前面已经说到, 继续, 最后, 进一步, 这种, 这样, 它, and 它们 are allowed only when the same sentence also names the concrete study object, treatment, condition, metric, or application scene.",
            "Do not use figure or table numbers as the substance of the question or answer; convert them into the actual experimental comparison or finding.",
            "Do not ask for a treatment, dose, time point, or metric combination unless that exact combination is explicitly supported by the source.",
            "If one evidence cluster has already been covered in the thread, do not ask another turn that only rephrases the same metric series or setup details.",
            "Do not merge values from different experimental branches, such as dose tests and repeat-application tests, into one answer unless the source directly compares them together.",
            "Prefer quantitative findings, design details, comparison logic, limitations, and practical implications over vague summaries.",
            "If the thread already established the setup, the next turn must advance to a new result, comparison, trend, limitation, or implication rather than restating the same setup.",
            "Do not restate the same finding cluster from an earlier turn with only minor wording changes.",
            "Do not ask two adjacent turns that both mainly request experimental setup, site, or control-group restatement when the source contains results.",
            "When a question asks for multiple numeric results, enumerate each requested value explicitly, preserve the source order, and copy the numeric values exactly from the grounded evidence.",
            "If the source only provides exact numbers for part of a requested multi-condition comparison, narrow the question instead of answering the missing part vaguely.",
            "Answers should be knowledge-rich rather than terse: when the source supports it, include study context, the key result, and one comparison, interpretation, limitation, or implication sentence.",
            "For multi-part, comparative, trend, recovery, mechanism, or limitation questions, prefer 2 to 4 sentences rather than a single short sentence.",
            "Keep both questions and answers in Chinese even when the source paper is in English.",
            "Avoid repeating or lightly rephrasing any existing question across the paper.",
            "Evidence text should be a short grounded excerpt or paraphrase anchor.",
            "Evidence locator should name the section, table, or figure when possible.",
        ],
        "conversation_id": conversation_id,
        "thread_plan": thread_plan,
        "batch_size": batch_size,
        "remaining_turns_in_thread": remaining_turns_in_thread,
        "existing_thread_turns": list(existing_thread_turns),
        "existing_questions": list(existing_questions),
        "knowledge_map": knowledge_map_outline,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def normalize_question_text(question: str) -> str:
    normalized = " ".join(question.casefold().split())
    return normalized.strip(" ?!。！？；;：:")


def _coverage_phase(*, next_ordinal: int, target_count: int) -> str:
    completed = max(next_ordinal - 1, 0)
    if target_count <= 0:
        return "focus on the most important grounded findings."

    progress = completed / target_count
    if progress < 0.34:
        return (
            "Prefer research goal, study object, experimental design, treatments, "
            "settings, and core evaluation metrics."
        )
    if progress < 0.67:
        return (
            "Prefer the main methods, quantitative results, comparisons, "
            "time-course findings, and table or figure backed observations."
        )
    return (
        "Prefer interpretation, limitations, mechanism, practical implications, "
        "recommendations, and remaining high-value body findings."
    )


def _format_outline_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
