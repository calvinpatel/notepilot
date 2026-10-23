"""The test sides of the domain's seams: the LLMClient (spec §5.5; L19, L74) and the Judge
(§8.2; L17).

FakeLLMClient satisfies LLMClient with a script. Each item is a real anthropic.types.Message
to return, so the fake cannot drift from the wire format, or an exception to raise, so tests
can drive the client's failure paths. Every create call is recorded as a RecordedCall,
deep-copied at call time. Nothing here reaches the network.

KeyedFakeLLMClient serves a corpus run, where gather decides the order of calls. Its scripts
are keyed by the raw text in the call's first message and consumed one item per call. Each
call suspends once before answering, so concurrent calls interleave: a fake that never
suspends runs each gathered task to completion, and a semaphore or a clock started outside
it is invisible (measured). It counts the calls in flight and the calls answered.

A call past the end of a script fails through pytest.fail, never a plain exception: its
Failed is a BaseException, so no `except Exception` in the code under test can turn a
forgotten script into a response a test could pass on.

mypy checks a Protocol only where something is bound to it. In backend/, get_client's return
annotation is the only binding of the real client, and nothing binds the fakes. _sdk_binds,
_fake_binds, and _keyed_fake_binds, never called, bind each side here so
`mypy backend/ tests/` checks the whole seam.

FakeJudgeClient satisfies judge_client's JudgeLLMClient, the judge's own seam (L314). Each
call's answer is keyed by its user message, since a note's pair calls run concurrently, and
each call suspends once before answering, as KeyedFakeMessages' do, so a test can read the
peak of its calls in flight. A call whose message is in hang waits until it's cancelled, and
the fake records every call cancelled in flight. _judge_sdk_binds, _fake_judge_client_binds, and
_anthropic_judge_binds bind AsyncAnthropic and the fake to the seam, and AnthropicJudge to
Judge.

FakeJudge satisfies Judge with a fixed usage. Its entailment records each call's pairs and
answers through its script, a function of the pairs: entail_all entails every pair,
entail_all_but every pair but those whose text it names, and time_out raises JudgeTimedOut, a
test-local stand-in for a call that timed out. With no script, a call fails the test through
pytest.fail, for the same reason as a call past FakeLLMClient's script. _fake_judge_binds
binds it.

CHECKS_CONFIG is the config the domain's tests pass to grounding and the checks (L187),
built from Settings' declared defaults rather than the process's settings, so an exported
FUZZY_SCORE_CUTOFF can't change what a test asserts. checks_config_with replaces knobs and
validates the result: model_copy(update=...) would skip ChecksConfig's bounds.
"""

import asyncio
import copy
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, NoReturn

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
from backend.judge_client import AnthropicJudge, JudgeLLMClient
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


class KeyedFakeMessages:
    """Answers each call from the script keyed by its raw text, after suspending once."""

    def __init__(self, scripts: Mapping[str, Sequence[Message | Exception]]) -> None:
        self._scripts = {raw_text: list(script) for raw_text, script in scripts.items()}
        self.calls: list[str] = []  # each call's raw text, in the order the calls began
        self.in_flight = 0
        self.peak_in_flight = 0
        self.answered = 0  # moves only when a call ends, so a test can read it as a clock

    # The same eight keyword-only parameters as FakeMessages.create, for the same reason.
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
        raw_text = next(iter(messages))["content"]  # summarize's first message (L83)
        if not isinstance(raw_text, str):
            pytest.fail("the first message's content is not the raw text")
        self.calls.append(raw_text)
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)  # the one suspension: other gathered calls run here
        finally:
            self.in_flight -= 1
        self.answered += 1
        script = self._scripts.get(raw_text, [])
        if not script:
            pytest.fail(f"unscripted create call for raw text {raw_text!r}")
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class KeyedFakeLLMClient:
    """Satisfies LLMClient; `messages` is a property so tests can reach its counters."""

    def __init__(self, scripts: Mapping[str, Sequence[Message | Exception]]) -> None:
        self._messages = KeyedFakeMessages(scripts)

    @property
    def messages(self) -> KeyedFakeMessages:
        return self._messages


def tool_use_message(
    tool_input: dict[str, object],
    *,
    stop_reason: StopReason = "tool_use",
    input_tokens: int = 10,
    output_tokens: int = 20,
    tool_use_id: str = "toolu_fake_1",
    name: str = SUMMARY_TOOL["name"],
) -> Message:
    """A canned tool-use response, built with the SDK's typed constructors.

    Never from dicts or model_validate: SDK models accept unknown keys silently, so a typo'd
    key would vanish without error; the typed __init__ makes it a mypy error. stop_reason is
    passed explicitly because the SDK defaults it to None, which a non-streaming response
    never has.
    """
    return Message(
        id="msg_fake_1",
        content=[ToolUseBlock(id=tool_use_id, input=tool_input, name=name, type="tool_use")],
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


def _keyed_fake_binds(client: KeyedFakeLLMClient) -> LLMClient:
    return client


@dataclass(frozen=True)
class RecordedJudgeCall:
    """One judge create call's kwargs, deep-copied at call time, as RecordedCall's are."""

    model: ModelParam
    system: str | Iterable[TextBlockParam]
    tools: list[ToolUnionParam]
    messages: list[MessageParam]
    tool_choice: ToolChoiceParam
    max_tokens: int
    thinking: ThinkingConfigParam
    output_config: OutputConfigParam
    timeout: float


class FakeJudgeMessages:
    """Records each call, suspends once, then answers from the script keyed by its message."""

    def __init__(
        self, scripts: Mapping[str, Message | Exception], *, hang: Iterable[str] = ()
    ) -> None:
        self._scripts = dict(scripts)
        self._hang = frozenset(hang)
        self.calls: list[RecordedJudgeCall] = []
        self.cancelled: list[str] = []  # the messages of the calls cancelled while in flight
        self.in_flight = 0
        self.peak_in_flight = 0

    # Nine keyword-only parameters, all required, types identical to _JudgeMessages.create,
    # for the reason FakeMessages.create gives.
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
        timeout: float,
    ) -> Message:
        recorded = RecordedJudgeCall(
            model=copy.deepcopy(model),
            system=copy.deepcopy(system),
            tools=copy.deepcopy(list(tools)),
            messages=copy.deepcopy(list(messages)),
            tool_choice=copy.deepcopy(tool_choice),
            max_tokens=copy.deepcopy(max_tokens),
            thinking=copy.deepcopy(thinking),
            output_config=copy.deepcopy(output_config),
            timeout=copy.deepcopy(timeout),
        )
        self.calls.append(recorded)
        content = recorded.messages[0]["content"]
        if not isinstance(content, str):
            pytest.fail("the judge's user message is not a string")
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)  # the one suspension: the note's other calls run here
            if content in self._hang:
                await asyncio.Event().wait()  # never set: only a cancellation ends it
        except asyncio.CancelledError:
            self.cancelled.append(content)
            raise
        finally:
            self.in_flight -= 1
        if content not in self._scripts:
            pytest.fail(f"unscripted judge call for message {content!r}")
        item = self._scripts[content]
        if isinstance(item, Exception):
            raise item
        return item


class FakeJudgeClient:
    """Satisfies JudgeLLMClient; `messages` is a property so tests can reach its records."""

    def __init__(
        self, scripts: Mapping[str, Message | Exception], *, hang: Iterable[str] = ()
    ) -> None:
        self._messages = FakeJudgeMessages(scripts, hang=hang)

    @property
    def messages(self) -> FakeJudgeMessages:
        return self._messages


def _judge_sdk_binds(client: AsyncAnthropic) -> JudgeLLMClient:
    return client


def _fake_judge_client_binds(client: FakeJudgeClient) -> JudgeLLMClient:
    return client


def _anthropic_judge_binds(judge: AnthropicJudge) -> Judge:
    return judge


# what a FakeJudge answers its pairs with
type JudgeScript = Callable[[Sequence[tuple[str, str]]], list[bool]]


@dataclass
class FakeJudge:
    usage: TokenUsage = field(default_factory=TokenUsage)
    script: JudgeScript | None = None
    calls: list[list[tuple[str, str]]] = field(default_factory=list)

    async def entailment(self, pairs: Sequence[tuple[str, str]]) -> list[bool]:
        self.calls.append(list(pairs))
        if self.script is None:
            pytest.fail("FakeJudge.entailment is unscripted")
        return self.script(pairs)


def entail_all(pairs: Sequence[tuple[str, str]]) -> list[bool]:
    """A FakeJudge script that entails every pair."""
    return [True] * len(pairs)


def entail_all_but(*texts: str) -> JudgeScript:
    """A FakeJudge script that entails every pair but those whose text is one of texts."""
    return lambda pairs: [text not in texts for text, _ in pairs]


class JudgeTimedOut(Exception):
    """A judge call that timed out, as a test-local exception."""


def time_out(pairs: Sequence[tuple[str, str]]) -> NoReturn:
    """A FakeJudge script whose call times out."""
    raise JudgeTimedOut


def _fake_judge_binds(judge: FakeJudge) -> Judge:
    return judge
