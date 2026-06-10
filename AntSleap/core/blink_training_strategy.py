BLINK_STRATEGY_TRIVIEW_RANDOM = "triview_random"
BLINK_STRATEGY_FULL_INSIDE_RANDOM = "full_inside_random"
BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE = "two_stage_full_then_inside"

BLINK_TRAINING_STRATEGIES = {
    BLINK_STRATEGY_TRIVIEW_RANDOM,
    BLINK_STRATEGY_FULL_INSIDE_RANDOM,
    BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
}

DEFAULT_BLINK_TRAINING_STRATEGY = BLINK_STRATEGY_TRIVIEW_RANDOM


def sanitize_blink_training_strategy(value, fallback=DEFAULT_BLINK_TRAINING_STRATEGY):
    text = str(value or "").strip()
    if text in BLINK_TRAINING_STRATEGIES:
        return text
    clean_fallback = str(fallback or "").strip()
    return clean_fallback if clean_fallback in BLINK_TRAINING_STRATEGIES else DEFAULT_BLINK_TRAINING_STRATEGY


def blink_training_strategy_label(strategy, lang="en"):
    clean = sanitize_blink_training_strategy(strategy)
    if lang == "zh":
        return {
            BLINK_STRATEGY_TRIVIEW_RANDOM: "方案一：全图/内视角/外视角随机",
            BLINK_STRATEGY_FULL_INSIDE_RANDOM: "方案二：全图/内视角随机",
            BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE: "方案三：先全图后内视角",
        }.get(clean, clean)
    return {
        BLINK_STRATEGY_TRIVIEW_RANDOM: "Plan 1: full/inside/outside random",
        BLINK_STRATEGY_FULL_INSIDE_RANDOM: "Plan 2: full/inside random",
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE: "Plan 3: full first, inside second",
    }.get(clean, clean)


def blink_training_strategy_note(strategy, lang="en"):
    clean = sanitize_blink_training_strategy(strategy)
    if lang == "zh":
        return {
            BLINK_STRATEGY_TRIVIEW_RANDOM: "保留当前原方案：从收缩轨迹抽取当前帧，随机使用全图/内视角/外视角，并带下一步与最终框监督。",
            BLINK_STRATEGY_FULL_INSIDE_RANDOM: "去掉目标被遮掉的外视角，只在父框全图和当前框内视角之间随机训练。",
            BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE: "先用父框全图学习粗定位，再用当前框内视角学习继续收紧。",
        }.get(clean, "")
    return {
        BLINK_STRATEGY_TRIVIEW_RANDOM: "Current baseline: sample a shrink trajectory frame, randomly use full/inside/outside views, and supervise next-step plus final boxes.",
        BLINK_STRATEGY_FULL_INSIDE_RANDOM: "Drops the target-missing outside view; trains with parent full view and current inside view only.",
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE: "Trains coarse localization on the parent full view first, then refines on the current inside view.",
    }.get(clean, "")
