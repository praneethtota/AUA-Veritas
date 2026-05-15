"""
core/scope_resolver.py — Memory scope resolution and conflict handling.

Called after memory_extractor produces an ExtractionResult.
Decides the final scope of the memory and handles conflicts
with existing memories using the OOP inheritance model.

Scope hierarchy (highest → lowest priority):
  conversation > project > global

Conflict resolution rules (locked in roadmap):
  1. Project scope overrides global silently
     — child overrides parent, same as method override in Java/Python.
     Example: global "use SQLite" + project "use Postgres"
              → Postgres wins for this project, no conflict prompt.

  2. Same-scope conflict with different canonical_query
     — prompt user: "This contradicts an existing memory. Replace it?"
     Options: replace | keep_both | cancel

  3. Identical canonical_query → last correction wins, no prompt
     — user directly correcting something already corrected.

  4. Conversation scope never conflicts — always stored, discarded
     at end of conversation anyway.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory_extractor import ExtractionResult
    from core.state import VeritasState

log = logging.getLogger(__name__)


# ── Scope hierarchy ───────────────────────────────────────────────────────────

class Scope(str, Enum):
    GLOBAL       = "global"
    PROJECT      = "project"
    CONVERSATION = "conversation"

# Priority: higher number = higher priority
SCOPE_PRIORITY = {
    Scope.GLOBAL:       0,
    Scope.PROJECT:      1,
    Scope.CONVERSATION: 2,
}


# ── Resolution result ─────────────────────────────────────────────────────────

class ResolutionAction(str, Enum):
    STORE          = "store"           # store as-is, no conflict
    REPLACE        = "replace"         # replace existing (silent or user-confirmed)
    KEEP_BOTH      = "keep_both"       # store new, keep old (different scope)
    PROMPT_USER    = "prompt_user"     # same-scope conflict, needs user decision
    CANCEL         = "cancel"          # user cancelled or conflict unresolvable


@dataclass
class ResolutionResult:
    """
    Result of scope resolution.

    action:           what to do with the new memory
    final_scope:      the resolved scope to store under
    conflict:         the existing memory that was found (if any)
    conflict_reason:  plain-language explanation for the UI prompt (if needed)
    silent:           True if no user prompt needed
    """
    action:          ResolutionAction
    final_scope:     str
    conflict:        dict | None = None
    conflict_reason: str | None = None
    silent:          bool = True

    @property
    def needs_user_input(self) -> bool:
        return self.action == ResolutionAction.PROMPT_USER


# ── Scope resolver ────────────────────────────────────────────────────────────

class ScopeResolver:
    """
    Resolves the final scope of a memory and detects conflicts.

    Uses the OOP inheritance model:
      - project scope silently overrides global (child overrides parent)
      - same-scope conflict on same canonical_query → last wins silently
      - same-scope conflict on related topic → prompt user
    """

    def __init__(self, state: "VeritasState"):
        self._state = state

    def resolve(
        self,
        extraction: "ExtractionResult",
        active_project: str | None = None,
        user_id: str = "local",
    ) -> ResolutionResult:
        """
        Resolve scope and detect conflicts for a new memory.

        Args:
            extraction:      The ExtractionResult from memory_extractor.
            active_project:  Name of the active project (if any).
            user_id:         User identifier (default "local" for single-user).

        Returns:
            ResolutionResult describing what action to take.
        """
        proposed_scope = Scope(extraction.scope)

        # ── Conversation scope: always store, no conflict check ───────────────
        if proposed_scope == Scope.CONVERSATION:
            return ResolutionResult(
                action=ResolutionAction.STORE,
                final_scope=Scope.CONVERSATION.value,
                silent=True,
            )

        # ── Look for existing memories on the same canonical topic ────────────
        existing = self._find_existing(
            canonical_query=extraction.canonical_query,
            domain=extraction.domain,
            user_id=user_id,
        )

        if not existing:
            # No conflict — store directly
            return ResolutionResult(
                action=ResolutionAction.STORE,
                final_scope=proposed_scope.value,
                silent=True,
            )

        existing_scope = Scope(existing.get("scope", "global"))

        # ── Rule 3: Identical canonical_query → last correction wins silently ─
        if existing.get("canonical_query") == extraction.canonical_query:
            log.debug(
                "Same canonical_query '%s' — replacing silently",
                extraction.canonical_query,
            )
            return ResolutionResult(
                action=ResolutionAction.REPLACE,
                final_scope=proposed_scope.value,
                conflict=existing,
                conflict_reason=None,
                silent=True,
            )

        # ── Rule 1: Project overrides global silently (OOP inheritance) ───────
        if (proposed_scope == Scope.PROJECT and existing_scope == Scope.GLOBAL):
            log.debug(
                "Project memory overrides global silently: '%s'",
                extraction.canonical_query,
            )
            return ResolutionResult(
                action=ResolutionAction.KEEP_BOTH,
                final_scope=Scope.PROJECT.value,
                conflict=existing,
                conflict_reason=None,
                silent=True,
            )

        # Global overriding project would be unusual — flag but allow
        if (proposed_scope == Scope.GLOBAL and existing_scope == Scope.PROJECT):
            return ResolutionResult(
                action=ResolutionAction.PROMPT_USER,
                final_scope=proposed_scope.value,
                conflict=existing,
                conflict_reason=(
                    f"A project-level memory already exists on this topic: "
                    f"\"{existing.get('corrective_instruction', '')[:100]}\" — "
                    f"do you want to set a global default that overrides it?"
                ),
                silent=False,
            )

        # ── Rule 2: Same-scope conflict on related topic → prompt user ────────
        if proposed_scope == existing_scope:
            return ResolutionResult(
                action=ResolutionAction.PROMPT_USER,
                final_scope=proposed_scope.value,
                conflict=existing,
                conflict_reason=self._build_conflict_reason(extraction, existing),
                silent=False,
            )

        # Different scopes, different canonical queries — keep both
        return ResolutionResult(
            action=ResolutionAction.KEEP_BOTH,
            final_scope=proposed_scope.value,
            conflict=existing,
            silent=True,
        )

    def apply(
        self,
        resolution: ResolutionResult,
        extraction: "ExtractionResult",
        active_project: str | None = None,
        user_id: str = "local",
    ) -> bool:
        """
        Apply a resolution decision to the state store.

        Should be called after the user has responded to any PROMPT_USER result.
        Pass the user's chosen action via resolution.action
        (REPLACE, KEEP_BOTH, or CANCEL).

        Returns True if the new memory was stored, False if cancelled.
        """
        if resolution.action == ResolutionAction.CANCEL:
            log.info("Memory storage cancelled by user")
            return False

        if resolution.action == ResolutionAction.REPLACE and resolution.conflict:
            # Delete the old memory
            self._delete_correction(resolution.conflict.get("correction_id"))
            log.info(
                "Replaced correction %s with new memory",
                resolution.conflict.get("correction_id"),
            )

        if resolution.action in (
            ResolutionAction.STORE,
            ResolutionAction.REPLACE,
            ResolutionAction.KEEP_BOTH,
        ):
            record = extraction.to_correction_record(active_project=active_project)
            record["scope"] = resolution.final_scope
            self._state.append("corrections", record)
            log.info(
                "Stored correction [%s/%s]: %s",
                resolution.final_scope,
                extraction.canonical_query,
                extraction.corrective_instruction[:60],
            )
            return True

        return False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _find_existing(
        self,
        canonical_query: str,
        domain: str,
        user_id: str,
    ) -> dict | None:
        """
        Find an existing correction that might conflict.
        Matches on canonical_query exact match first,
        then falls back to domain + partial match.
        """
        # Exact canonical_query match
        corrections = self._state.query(
            "corrections",
            filters={"user_id": user_id, "canonical_query": canonical_query},
            limit=1,
        )
        if corrections:
            return corrections[0]

        # Domain match — look for corrections that might be related
        # Uses simple prefix match on canonical_query (first token)
        all_domain = self._state.query(
            "corrections",
            filters={"user_id": user_id, "domain": domain},
            limit=50,
        )
        prefix = canonical_query.split("_")[0]  # first word of canonical key
        for c in all_domain:
            if c.get("canonical_query", "").startswith(prefix):
                return c

        return None

    def _delete_correction(self, correction_id: str | None) -> None:
        """Mark a correction as superseded (soft delete via scope change)."""
        if not correction_id:
            return
        try:
            # SQLite soft delete — mark as conversation scope so it's ignored
            # in future prompt injections
            with self._state._conn() as conn:
                conn.execute(
                    "UPDATE corrections SET scope='superseded' WHERE correction_id=?",
                    (correction_id,)
                )
        except Exception as e:
            log.warning("Could not soft-delete correction %s: %s", correction_id, e)

    def _build_conflict_reason(
        self,
        extraction: "ExtractionResult",
        existing: dict,
    ) -> str:
        """Build a plain-language conflict explanation for the UI prompt."""
        existing_instr = existing.get("corrective_instruction", "")[:100]
        new_instr = extraction.corrective_instruction[:100]
        return (
            f"This contradicts an existing {existing.get('scope', 'project')} memory:\n"
            f"  Existing: \"{existing_instr}\"\n"
            f"  New:      \"{new_instr}\"\n"
            f"Replace the existing memory?"
        )
