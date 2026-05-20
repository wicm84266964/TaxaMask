const running = new Map();

export function registerBackgroundAgentTask(task) {
  const id = String(task?.taskId ?? "").trim();
  if (!id) {
    return () => {};
  }
  running.set(id, {
    taskId: id,
    groupId: task.groupId ? String(task.groupId) : null,
    parentSessionId: task.parentSessionId ? String(task.parentSessionId) : null,
    profile: task.profile ? String(task.profile) : null,
    controller: task.controller,
    startedAt: new Date().toISOString()
  });
  return () => {
    running.delete(id);
  };
}

export function listBackgroundAgentTasks(options = {}) {
  const parentSessionId = options.parentSessionId ? String(options.parentSessionId) : null;
  const groupId = options.groupId ? String(options.groupId) : null;
  return [...running.values()]
    .filter((task) => !parentSessionId || task.parentSessionId === parentSessionId)
    .filter((task) => !groupId || task.groupId === groupId)
    .map(({ controller, ...task }) => ({
      ...task,
      aborted: controller?.signal?.aborted === true
    }));
}

export function cancelBackgroundAgentTasks(options = {}) {
  const parentSessionId = options.parentSessionId ? String(options.parentSessionId) : null;
  const groupId = options.groupId ? String(options.groupId) : null;
  const tasks = [...running.values()]
    .filter((task) => !parentSessionId || task.parentSessionId === parentSessionId)
    .filter((task) => !groupId || task.groupId === groupId);
  for (const task of tasks) {
    if (task.controller && task.controller.signal?.aborted !== true) {
      task.controller.abort();
    }
  }
  return tasks.map(({ controller, ...task }) => ({
    ...task,
    aborted: controller?.signal?.aborted === true
  }));
}

export function hasRunningBackgroundAgentTasks(options = {}) {
  return listBackgroundAgentTasks(options).some((task) => task.aborted !== true);
}
