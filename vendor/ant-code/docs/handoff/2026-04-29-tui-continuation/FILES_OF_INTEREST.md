# Files Of Interest

## TUI Runtime

- `src/cli/tui.js`
  - Main Ink TUI app.
  - Handles input, session turns, queue, `/guide`, model picker, popovers, scrolling, and layout.

- `src/cli/tui/components.js`
  - Status bar, log pane, side panel, prompt box, command panel, startup UI, footer.
  - Contains `scrollbackMode` rendering behavior in `LogPane`.

- `src/cli/tui/format.js`
  - Formatting helpers for transcript rows, streaming rows, prompt lines, permission text, and detail mode labels.

- `src/cli/tui/interaction.js`
  - Raw terminal input helpers: wheel parsing, PageUp/PageDown parsing, Ctrl+C confirmation semantics, popover priority.

- `src/cli/tui/workflows.js`
  - Queue helpers and immediate TUI command detection.
  - Contains `prependQueuedPrompt` and `buildGuidePrompt`.

## Commands

- `src/commands/registry.js`
  - Slash command registry. `/guide` is now listed as a session command.

- `src/commands/runtime.js`
  - Non-interactive slash command behavior.
  - `/guide` is reserved outside interactive TUI.
  - `/keybindings` text was updated.

## Tests

- `tests/unit/tui-workflows.test.js`
  - Queue helper and guide prompt tests.

- `tests/unit/commands.test.js`
  - `/keybindings`, reserved interactive commands, model command tests.

- `tests/unit/tui-format.test.js`
  - Transcript and stream viewport formatting.

- `tests/unit/tui-interaction.test.js`
  - Raw input parsing and Ctrl+C confirmation helper tests.
