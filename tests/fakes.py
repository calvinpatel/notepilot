"""The test side of the LLMClient seam (spec §5.5; L19, L74).

FakeLLMClient satisfies LLMClient with a scripted sequence of real anthropic.types.Message
objects, so the fake cannot drift from the wire format. Every create call is recorded as a
RecordedCall, deep-copied at call time. Nothing here reaches the network.

mypy checks a Protocol only where something is bound to it. In backend/, get_client's return
annotation is the only binding of the real client, and nothing binds the fake. _sdk_binds and
_fake_binds, never called, bind each side here so `mypy backend/ tests/` checks the whole seam.
"""

import copy
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from anthropic.types import (
    Message,
    MessageParam,
    ModelParam,
    StopReason,
    TextBlockParam,
    ToolChoiceParam,
    ToolUnionParam,
    ToolUseBlock,
    Usage,
)

from backend.orchestrator import SUMMARY_TOOL, LLMClient


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
    extra_body: object


class FakeMessages:
    """Records every call first, then returns the next scripted Message; never a default."""

    def __init__(self, script: Sequence[Message]) -> None:
        self._script = list(script)
        self.calls: list[RecordedCall] = []

    # Seven keyword-only parameters, all required, types identical to _AsyncMessages.create:
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
        extra_body: object,
    ) -> Message:
        self.calls.append(
            RecordedCall(
                model=copy.deepcopy(model),
                system=copy.deepcopy(system),
                tools=copy.deepcopy(list(tools)),
                messages=copy.deepcopy(list(messages)),
                tool_choice=copy.deepcopy(tool_choice),
                max_tokens=copy.deepcopy(max_tokens),
                extra_body=copy.deepcopy(extra_body),
            )
        )
        n = len(self.calls)
        if n > len(self._script):
            raise AssertionError(f"unscripted create call #{n}")
        return self._script[n - 1]


class FakeLLMClient:
    """Satisfies LLMClient; `messages` is a property so tests can reach `.calls` on it."""

    def __init__(self, script: Sequence[Message]) -> None:
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


# mypy checks a Protocol only where something is bound to it, and get_client's return
# annotation is otherwise the only binding of the real client. Never called.
def _sdk_binds(client: AsyncAnthropic) -> LLMClient:
    return client


def _fake_binds(client: FakeLLMClient) -> LLMClient:
    return client
