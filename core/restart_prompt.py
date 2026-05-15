"""
core/restart_prompt.py — Restart prompt generator.

Generates a compact, copy-pasteable prompt block from the user's active
project memories. The output can be pasted into any AI tool (Claude Code,
Cursor, ChatGPT) to transfer project context when starting a new session.

Two output formats:
  "veritas"  — formatted for pasting back into AUA-Veritas
  "ide"      — formatted for Claude Code / Cursor system prompt (plainer)

Layered structure (from roadmap):
  1. Global user preferences
  2. Project decisions
  3. Active constraints (persistent instructions)
  4. Known failure patterns (things to avoid)
  5. Recent corrections (factual fixes)
  6. Open tasks (not yet implemented — placeholder)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import VeritasState

log = logging.getLogger(__name__)

# ── Layer configuration ───────────────────────────────────────────────────────

LAYER_ORDER = [
    "preference",             # Layer 1 — global preferences
    "project_decision",       # Layer 2 — project decisions
    "persistent_instruction", # Layer 3 — active constraints
    "failure_pattern",        # Layer 4 — things to avoid
    "factual_correction",     # Layer 5 — recent factual fixes
]

LAYER_LABELS = {
    "preference":             "User preferences",
    "project_decision":       "Project decisions",
    "persistent_instruction": "Active instructions",
    "failure_pattern":        "Known failure patterns (avoid these)",
    "factual_correction":     "Factual corrections",
}

# Maximum corrections per layer in the restart prompt
MAX_PER_LAYER = 5
# Maximum total items in any restart prompt
MAX_TOTAL_ITEMS = 20


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class RestartPrompt:
    """Generated restart prompt."""
    project:        str | None
    veritas_format: str          # for pasting back into AUA-Veritas
    ide_format:     str          # for Claude Code / Cursor system prompt
    item_count:     int
    layer_counts:   dict[str, int] = field(default_factory=dict)
    generated_at:   float = field(default_factory=time.time)


# ── Generator ────────────────────────────────────────────────────────────────

class RestartPromptBuilder:
    """
    Builds a layered restart prompt from the user's active corrections.

    Usage:
        builder = RestartPromptBuilder(state)
        prompt = builder.build(
            active_project="My App",
            user_id="local",
            include_global=True,
        )
        print(prompt.ide_format)   # paste into Cursor
        print(prompt.veritas_format)  # paste back into Veritas
    """

    def __init__(self, state: "VeritasState"):
        self._state = state

    def build(
        self,
        active_project: str | None = None,
        user_id: str = "local",
        include_global: bool = True,
        max_items: int = MAX_TOTAL_ITEMS,
    ) -> RestartPrompt:
        """
        Build a restart prompt from active corrections.

        Args:
            active_project:  Project name to pull project-scoped corrections for.
            user_id:         User identifier (default "local").
            include_global:  Whether to include global-scope corrections.
            max_items:       Cap on total items in the prompt.

        Returns:
            RestartPrompt with veritas_format and ide_format strings.
        """
        corrections = self._fetch_corrections(
            active_project=active_project,
            user_id=user_id,
            include_global=include_global,
        )

        if not corrections:
            return RestartPrompt(
                project=active_project,
                veritas_format=self._empty_message(active_project, "veritas"),
                ide_format=self._empty_message(active_project, "ide"),
                item_count=0,
            )

        # Group by type/layer
        layers: dict[str, list[dict]] = {layer: [] for layer in LAYER_ORDER}
        for c in corrections:
            corr_type = c.get("type", "factual_correction")
            if corr_type in layers and len(layers[corr_type]) < MAX_PER_LAYER:
                layers[corr_type].append(c)

        # Count items per layer
        layer_counts = {layer: len(items) for layer, items in layers.items() if items}
        total = sum(layer_counts.values())

        veritas_format = self._render_veritas(layers, active_project, total)
        ide_format     = self._render_ide(layers, active_project, total)

        return RestartPrompt(
            project=active_project,
            veritas_format=veritas_format,
            ide_format=ide_format,
            item_count=min(total, max_items),
            layer_counts=layer_counts,
        )

    # ── Fetch ────────────────────────────────────────────────────────────────

    def _fetch_corrections(
        self,
        active_project: str | None,
        user_id: str,
        include_global: bool,
    ) -> list[dict]:
        """Fetch and merge global + project corrections, deduplicating by canonical_query."""
        corrections = []
        seen_keys: set[str] = set()

        def add(items: list[dict]) -> None:
            for c in items:
                if c.get("scope") == "superseded":
                    continue
                key = c.get("canonical_query", c.get("correction_id", ""))
                if key not in seen_keys:
                    seen_keys.add(key)
                    corrections.append(c)

        # Project-scoped corrections first (higher priority)
        if active_project:
            project_corr = self._state.query(
                "corrections",
                filters={"user_id": user_id, "scope": "project"},
                limit=100,
            )
            add(project_corr)

        # Global corrections
        if include_global:
            global_corr = self._state.query(
                "corrections",
                filters={"user_id": user_id, "scope": "global"},
                limit=100,
            )
            add(global_corr)

        return corrections

    # ── Renderers ────────────────────────────────────────────────────────────

    def _render_veritas(
        self,
        layers: dict[str, list[dict]],
        project: str | None,
        total: int,
    ) -> str:
        """Render the Veritas-format prompt (richer, with layer headers)."""
        lines = []
        header = f"Project memory: {project}" if project else "Global memory"
        lines.append(f"=== {header} ({total} items) ===")
        lines.append("")

        item_num = 1
        for layer_type in LAYER_ORDER:
            items = layers.get(layer_type, [])
            if not items:
                continue
            lines.append(f"[{LAYER_LABELS[layer_type].upper()}]")
            for c in items:
                instr = c.get("corrective_instruction", "").strip()
                if instr:
                    lines.append(f"  {item_num}. {instr}")
                    item_num += 1
            lines.append("")

        lines.append("=== End of project memory ===")
        return "\n".join(lines)

    def _render_ide(
        self,
        layers: dict[str, list[dict]],
        project: str | None,
        total: int,
    ) -> str:
        """
        Render the IDE-format prompt (plain, no special formatting).
        Designed for Claude Code, Cursor, ChatGPT system prompt boxes.
        """
        lines = []
        project_line = f'project "{project}"' if project else "this conversation"
        lines.append(
            f"Before answering, apply these {total} project memories for {project_line}:"
        )
        lines.append("")

        item_num = 1
        for layer_type in LAYER_ORDER:
            items = layers.get(layer_type, [])
            for c in items:
                instr = c.get("corrective_instruction", "").strip()
                if instr:
                    lines.append(f"{item_num}. {instr}")
                    item_num += 1

        if not any(layers.values()):
            lines.append("(No project memories stored yet.)")

        return "\n".join(lines)

    def _empty_message(self, project: str | None, fmt: str) -> str:
        project_str = f'"{project}"' if project else "this project"
        if fmt == "veritas":
            return (
                f"=== No memories stored for {project_str} yet ===\n\n"
                "Start chatting — corrections and project decisions will be\n"
                "captured automatically as you work.\n\n"
                "=== End ==="
            )
        return (
            f"No project memories stored for {project_str} yet. "
            "Corrections will be captured automatically as you work."
        )
