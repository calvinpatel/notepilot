"""The test sides of the domain's seams: the LLMClient (spec §5.5; L19, L74) and the Judge
(§8.2; L17).

FakeLLMClient satisfies LLMClient with a script. Each item is a real anthropic.types.Message
to return, so the fake cannot drift from the wire format, or an exception to raise, so tests
can drive the client's failure paths. Every create call is recorded as a RecordedCall,
deep-copied at call time. Nothing here reaches the network.

A call past the end of the script fails through pytest.fail, never a plain exception: its
Failed is a BaseException, so no `except Exception` in the code under test can turn a
forgotten script into a response a test could pass on.

mypy checks a Protocol only where something is bound to it. In backend/, get_client's return
annotation is the only binding of the real client, and nothing binds the fake. _sdk_binds and
_fake_binds, never called, bind each side here so `mypy backend/ tests/` checks the whole seam.

FakeJudge satisfies Judge with a fixed usage. Its entailment is unscripted: a call fails the
test through pytest.fail, for the same reason as a call past FakeLLMClient's script.
_fake_judge_binds binds it.

CHECKS_CONFIG is the config the domain's tests pass to grounding and the checks (L187),
built from Settings' declared defaults rather than the process's settings, so an exported
FUZZY_SCORE_CUTOFF can't change what a test asserts. checks_config_with replaces knobs and
validates the result: model_copy(update=...) would skip ChecksConfig's bounds.
"""

import copy
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import (
    Message,
    MessageParam,
    ModelParam,
    OutputConfigParam,
    StopReason,
    TextBlock,
    TextBlockParam,
    ThinkingConfigParam,
    ToolChoiceParam,
    ToolUnionParam,
    ToolUseBlock,
    Usage,
)

from backend.config import Settings
from backend.evals.judge import Judge
from backend.orchestrator import SUMMARY_TOOL, LLMClient
from backend.schemas import ChecksConfig, TokenUsage

CHECKS_CONFIG: Final = ChecksConfig.model_validate(
    {name: Settings.model_fields[name].default for name in ChecksConfig.model_fields}
)


def checks_config_with(**knobs: object) -> ChecksConfig:
    """CHECKS_CONFIG with the given knobs replaced, through ChecksConfig's validation.

    An unknown name raises: validation ignores extra keys, so a misspelled knob would leave
    the default in place and the test would pass on it.
    """
    unknown = knobs.keys() - ChecksConfig.model_fields.keys()
    if unknown:
        raise TypeError(f"not a ChecksConfig knob: {sorted(unknown)}")
    return ChecksConfig.model_validate(CHECKS_CONFIG.model_dump() | knobs)


@dataclass(frozen=True)
class RecordedCall:
    """One create call's kwargs, deep-copied at call time.

    §5.4's validation retry extends the messages list in place, so a stored reference would
    make attempt 1 report attempt 2's messages. tools and messages are materialized to lists
    so tests can take len() and index them; the other fields keep the Protocol's types.
    """

    model: ModelParam
    system: str | Iterable[TextBlockParam]
    tools: list[ToolUnionParam]
    messages: list[MessageParam]
    tool_choice: ToolChoiceParam
    max_tokens: int
    thinking: ThinkingConfigParam
    output_config: OutputConfigParam


class FakeMessages:
    """Records every call first, then returns or raises the next scripted item; never a default."""

    def __init__(self, script: Sequence[Message | Exception]) -> None:
        self._script = list(script)
        self.calls: list[RecordedCall] = []

    # Eight keyword-only parameters, all required, types identical to _AsyncMessages.create:
    # a required parameter here is what lets mypy catch a Protocol that drops one.
    async def create(
        self,
        *,
        model: ModelParam,
        system: str | Iterable[TextBlockParam],
        tools: Iterable[ToolUnionParam],
        messages: Iterable[MessageParam],
        tool_choice: ToolChoiceParam,
        max_tokens: int,
        thinking: ThinkingConfigParam,
        output_config: OutputConfigParam,
    ) -> Message:
        self.calls.append(
            RecordedCall(
                model=copy.deepcopy(model),
                system=copy.deepcopy(system),
                tools=copy.deepcopy(list(tools)),
                messages=copy.deepcopy(list(messages)),
                tool_choice=copy.deepcopy(tool_choice),
                max_tokens=copy.deepcopy(max_tokens),
                thinking=copy.deepcopy(thinking),
                output_config=copy.deepcopy(output_config),
            )
        )
        n = len(self.calls)
        if n > len(self._script):
            pytest.fail(f"unscripted create call #{n}")
        item = self._script[n - 1]
        if isinstance(item, Exception):
            raise item
        return item


class FakeLLMClient:
    """Satisfies LLMClient; `messages` is a property so tests can reach `.calls` on it."""

    def __init__(self, script: Sequence[Message | Exception]) -> None:
        self._messages = FakeMessages(script)

    @property
    def messages(self) -> FakeMessages:
        return self._messages


def tool_use_message(
    tool_input: dict[str, object],
    *,
    stop_reason: StopReason = "tool_use",
    input_tokens: int = 10,
    output_tokens: int = 20,
    tool_use_id: str = "toolu_fake_1",
) -> Message:
    """A canned tool-use response, built with the SDK's typed constructors.

    Never from dicts or model_validate: SDK models accept unknown keys silently, so a typo'd
    key would vanish without error; the typed __init__ makes it a mypy error. stop_reason is
    passed explicitly because the SDK defaults it to None, which a non-streaming response
    never has.
    """
    return Message(
        id="msg_fake_1",
        content=[
            ToolUseBlock(
                id=tool_use_id, input=tool_input, name=SUMMARY_TOOL["name"], type="tool_use"
            )
        ],
        model="fake-model",
        role="assistant",
        stop_reason=stop_reason,
        type="message",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def text_message(
    text: str,
    *,
    stop_reason: StopReason = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> Message:
    """A canned response with no tool_use block."""
    return Message(
        id="msg_fake_1",
        content=[TextBlock(text=text, type="text")],
        model="fake-model",
        role="assistant",
        stop_reason=stop_reason,
        type="message",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


# mypy checks a Protocol only where something is bound to it, and get_client's return
# annotation is otherwise the only binding of the real client. Never called.
def _sdk_binds(client: AsyncAnthropic) -> LLMClient:
    return client


def _fake_binds(client: FakeLLMClient) -> LLMClient:
    return client


@dataclass
class FakeJudge:
    usage: TokenUsage = field(default_factory=TokenUsage)

    async def entailment(self, pairs: Sequence[tuple[str, str]]) -> list[bool]:
        pytest.fail("FakeJudge.entailment is unscripted")


def _fake_judge_binds(judge: FakeJudge) -> Judge:
    return judge
