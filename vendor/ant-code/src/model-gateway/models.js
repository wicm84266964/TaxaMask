export const DEFAULT_MODEL_OPTIONS = Object.freeze([
  {
    id: "claude-sonnet-4-5-20250929",
    label: "Sonnet 4.5",
    description: "Balanced coding model exposed by the local lab adapter.",
    thinking: false,
    contextTokens: 200000
  },
  {
    id: "claude-sonnet-4-5-20250929-thinking",
    label: "Sonnet 4.5 Thinking",
    description: "Adapter model with provider-exposed reasoning deltas when available.",
    thinking: true,
    contextTokens: 200000
  },
  {
    id: "claude-haiku-4-5-20251001",
    label: "Haiku 4.5",
    description: "Lower-latency local adapter model for lighter work.",
    thinking: false,
    contextTokens: 200000
  }
]);

/**
 * @param {Record<string, any>} config
 */
export function listConfiguredModels(config) {
  const configured = Array.isArray(config.models) && config.models.length > 0
    ? config.models
    : DEFAULT_MODEL_OPTIONS;
  const models = configured.map(normalizeModel).filter(Boolean);
  const current = String(config.modelAlias ?? "").trim();
  if (current && !models.some((model) => model.id === current)) {
    models.unshift({
      id: current,
      label: current,
      description: "Current model alias from environment or config.",
      thinking: /thinking|reason/i.test(current)
    });
  }
  return dedupeModels(models);
}

/**
 * @param {Record<string, any>} config
 * @param {string} modelId
 */
export function resolveModelSelection(config, modelId) {
  const requested = String(modelId ?? "").trim();
  const models = listConfiguredModels(config);
  const exact = models.find((model) => model.id === requested);
  if (exact) {
    return { ok: true, model: exact, models };
  }
  const byLabel = models.find((model) => model.label.toLowerCase() === requested.toLowerCase());
  if (byLabel) {
    return { ok: true, model: byLabel, models };
  }
  return {
    ok: false,
    error: {
      code: "MODEL_NOT_CONFIGURED",
      message: requested ? `Model is not configured: ${requested}` : "No model id supplied."
    },
    models
  };
}

/**
 * @param {Record<string, any>} config
 */
export function formatModelOptions(config) {
  const current = config.modelAlias;
  return listConfiguredModels(config).map((model, index) => {
    const marker = model.id === current ? "*" : " ";
    const thinking = model.thinking ? " thinking" : "";
    const context = Number.isFinite(model.contextTokens) ? ` context=${formatTokenCount(model.contextTokens)}` : "";
    return `${marker} ${index + 1}. ${model.id}${thinking}${context} - ${model.description}`;
  }).join("\n");
}

/**
 * @param {string} value
 */
export function parseModelList(value) {
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((id) => ({
      id,
      label: id,
      description: "Model alias supplied by LAB_AGENT_MODELS.",
      thinking: /thinking|reason/i.test(id),
      contextTokens: null,
      reasoningContentMode: null
    }));
}

/**
 * @param {unknown} item
 */
function normalizeModel(item) {
  if (typeof item === "string") {
    return {
      id: item,
      label: item,
      description: "Configured model alias.",
      thinking: /thinking|reason/i.test(item),
      contextTokens: null,
      reasoningContentMode: null
    };
  }
  if (!item || typeof item !== "object" || !item.id) {
    return null;
  }
  const id = String(item.id);
  return {
    id,
    label: String(item.label ?? id),
    description: String(item.description ?? "Configured model alias."),
    thinking: Boolean(item.thinking ?? /thinking|reason/i.test(id)),
    contextTokens: positiveIntegerOrNull(item.contextTokens ?? item.maxContextTokens ?? item.contextWindowTokens),
    reasoningContentMode: normalizeReasoningContentMode(item.reasoningContentMode)
  };
}

/**
 * @param {Record<string, any>} config
 */
export function resolveModelContextTokens(config) {
  const current = String(config?.modelAlias ?? "").trim();
  const model = listConfiguredModels(config ?? {}).find((item) => item.id === current);
  return Number.isFinite(model?.contextTokens) ? model.contextTokens : null;
}

/**
 * @param {Array<Record<string, any>>} models
 */
function dedupeModels(models) {
  const seen = new Set();
  const result = [];
  for (const model of models) {
    if (seen.has(model.id)) {
      continue;
    }
    seen.add(model.id);
    result.push(model);
  }
  return result;
}

function positiveIntegerOrNull(value) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
}

function normalizeReasoningContentMode(value) {
  return value === "visible-when-no-content" || value === "hidden" ? value : null;
}

function formatTokenCount(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "?";
  }
  if (number >= 1000000) {
    return `${Math.round(number / 100000) / 10}M`;
  }
  if (number >= 1000) {
    return `${Math.round(number / 1000)}k`;
  }
  return String(number);
}
