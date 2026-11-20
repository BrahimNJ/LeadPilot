"""Score leads through the Claude Code CLI in headless mode, for people without an API key.

It reuses everything the production copilot sends: the same system prompt, the same
`<crm_record>` user message and the same JSON schema, and validates the answer with the
same Pydantic model. It is still an approximation of the production path, because the
request goes through Claude Code rather than straight to the Messages API (see
docs/evaluation.md).
"""

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from anthropic import transform_schema
from pydantic import ValidationError

from app.ai.claude import SCORING_TASK, SYSTEM_PROMPT, build_prompt
from app.ai.context import ContactContext
from app.ai.copilot import CopilotRefused, CopilotUnavailable
from app.ai.schemas import LeadScore, ScoreResult

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

# The schema the SDK sends to the Messages API for LeadScore, so both paths ask for the same.
LEAD_SCORE_SCHEMA = json.dumps(transform_schema(LeadScore))


def find_cli() -> str | None:
    return shutil.which("claude")


class ClaudeCodeCopilot:
    def __init__(
        self,
        executable: str,
        model: str,
        effort: str,
        timeout_s: float = 300,
        run: Runner = subprocess.run,
    ) -> None:
        self._executable = executable
        self._model = model
        self._effort = effort
        self._timeout_s = timeout_s
        self._run = run
        self.last_usage: tuple[int, int] | None = None

    def command(self) -> list[str]:
        return [
            self._executable,
            "--print",
            "--output-format",
            "json",
            "--json-schema",
            LEAD_SCORE_SCHEMA,
            "--system-prompt",
            SYSTEM_PROMPT,
            "--model",
            self._model,
            "--effort",
            self._effort,
            # A scoring call needs no tools, no saved session and none of your customizations.
            "--tools",
            "",
            "--no-session-persistence",
            "--safe-mode",
        ]

    def version(self) -> str:
        done = self._call([self._executable, "--version"], stdin="")
        return done.stdout.strip() or "unknown version"

    def score_lead(self, ctx: ContactContext) -> ScoreResult:
        done = self._call(self.command(), stdin=build_prompt(SCORING_TASK, ctx))
        data = _parse_output(done)

        usage = data.get("usage") or {}
        self.last_usage = (
            int(usage.get("input_tokens", 0))
            + int(usage.get("cache_creation_input_tokens", 0))
            + int(usage.get("cache_read_input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
        )
        if data.get("stop_reason") == "refusal":
            raise CopilotRefused("the model declined to answer for this record")
        try:
            lead = LeadScore.model_validate(data.get("structured_output"))
        except ValidationError as exc:
            raise CopilotUnavailable(f"the answer did not match the schema: {exc}") from exc
        return ScoreResult(lead=lead, model=f"{self._model} via claude-code")

    def _call(self, args: Sequence[str], stdin: str) -> "subprocess.CompletedProcess[str]":
        try:
            return self._run(
                list(args),
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout_s,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CopilotUnavailable(f"Claude Code CLI not found: {self._executable}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CopilotUnavailable(f"Claude Code did not answer in {self._timeout_s}s") from exc


def _parse_output(done: "subprocess.CompletedProcess[str]") -> dict[str, Any]:
    try:
        data = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        detail = (done.stderr or done.stdout).strip()[-300:]
        raise CopilotUnavailable(
            f"Claude Code exited with {done.returncode} and no JSON: {detail}"
        ) from exc
    if not isinstance(data, dict):
        raise CopilotUnavailable("Claude Code returned JSON that is not an object")
    if data.get("is_error") or data.get("subtype") != "success":
        raise CopilotUnavailable(
            f"Claude Code reported an error ({data.get('subtype')}): "
            f"{str(data.get('result', ''))[:300]}"
        )
    return data
