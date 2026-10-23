"""The corpus scorer, its command, and its git and runs_path helpers (§8.7, §11; L211, L237, L241).

No network: every call goes to a KeyedFakeLLMClient. No git of the real tree: score_corpus's
tests replace both git reads, and the helpers' tests run git in a repository under tmp_path,
with the user's and the system's git config shut out.
"""

import logging
import os
import subprocess
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Final

import httpx2
import pytest
from anthropic import APIConnectionError
from anthropic.types import Message
from pydantic import BaseModel, SecretStr

import backend.corpus as corpus
from backend.config import Settings
from backend.corpus import (
    append_jsonl,
    current_git_sha,
    git_is_dirty,
    plan_run,
    score_corpus,
)
from backend.evals.judge import Judge
from backend.evals.loader import corpus_version
from backend.evals.runner import CHECKS_VERSION
from backend.evals.runner import case_result as real_case_result
from backend.orchestrator import PROMPT_VERSION, LLMClient
from backend.schemas import (
    CaseResult,
    CorpusRunRecord,
    EvalCase,
    EvalReport,
    SOAPNoteDraft,
    SummarizationResult,
    TokenUsage,
)
from tests.fakes import FakeJudge, KeyedFakeLLMClient, entail_all, text_message, tool_use_message

MESSAGE_SENTINEL: Final = "sentinel-msg-3c9e"
CAUSE_SENTINEL: Final = "sentinel-cause-81d4"
SHA: Final = "sha-under-test"

# One control note for every case: both quotes are in every case's raw text, verbatim, and
# no check fires on it (measured), so each scored row passes.
VALID_INPUT: Final[dict[str, object]] = {
    "claims": [
        {
            "text": "Mild cough for two days",
            "section": "S",
            "source_quote": "mild cough for two days",
        },
        {"text": "Lungs clear", "section": "O", "source_quote": "Lungs clear on exam"},
    ]
}
INVALID_INPUT: Final[dict[str, object]] = {
    "claims": [{"text": "Lungs clear", "section": "Q", "source_quote": "Lungs clear on exam"}]
}
DRAFT: Final = SOAPNoteDraft.model_validate(VALID_INPUT)


class _Crash(Exception):
    """A local type: a hard-coded exc_type literal can't match a builtin's name."""


def _raw(case_id: str) -> str:
    return f"Case {case_id}. Patient reports mild cough for two days. Lungs clear on exam."


def _case(case_id: str) -> EvalCase:
    return EvalCase(id=case_id, species="control", raw_text=_raw(case_id), trap=None)


def _injected(case_id: str) -> EvalCase:
    """An injected case: pytest's, never the scorer's (§8.5). No script answers it."""
    return EvalCase(id=case_id, species="control", raw_text=_raw(case_id), draft=DRAFT, trap=None)


def _ok(input_tokens: int = 10, output_tokens: int = 20) -> Message:
    return tool_use_message(VALID_INPUT, input_tokens=input_tokens, output_tokens=output_tokens)


def _upstream() -> APIConnectionError:
    """An upstream failure inside summarize: no RunMetadata and no OrchestratorError."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return APIConnectionError(message="connection failed", request=request)


@pytest.fixture
def run_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[..., Settings]:
    """Installs a Settings for backend.corpus to read, every knob it reads stated here.

    Non-default counts, retries, and cutoff, so a run that read the defaults instead fails
    (§11's wiring rule). An exported CORPUS_REPEATS can't reach a test: each knob is passed
    explicitly. model_validate, not the constructor: pyright reads every field as a required
    parameter.
    """

    def install(
        *,
        corpus_repeats: int = 2,
        corpus_concurrency: int = 1,
        max_validation_retries: int = 1,
        runs_path: Path | None = None,
    ) -> Settings:
        installed = Settings.model_validate(
            {
                "anthropic_api_key": SecretStr("test-dummy-key"),
                "model": "model-under-test",
                "fuzzy_score_cutoff": 85.0,
                "min_quote_content_tokens": 2,
                "corpus_repeats": corpus_repeats,
                "corpus_concurrency": corpus_concurrency,
                "max_validation_retries": max_validation_retries,
                "runs_path": runs_path or tmp_path / "runs" / "corpus_runs.jsonl",
            }
        )
        monkeypatch.setattr(corpus, "settings", installed)
        return installed

    return install


@pytest.fixture
def lineage(monkeypatch: pytest.MonkeyPatch) -> Callable[[KeyedFakeLLMClient], list[str]]:
    """Replaces both git reads; each records its name and asserts nothing was spent yet."""

    def install(client: KeyedFakeLLMClient) -> list[str]:
        reads: list[str] = []

        def sha() -> str:
            assert client.messages.calls == []  # L207: before the first call
            reads.append("sha")
            return SHA

        def dirty() -> bool:
            assert client.messages.calls == []
            reads.append("dirty")
            return True

        monkeypatch.setattr(corpus, "current_git_sha", sha)
        monkeypatch.setattr(corpus, "git_is_dirty", dirty)
        return reads

    return install


def _lines(path: Path) -> list[CorpusRunRecord]:
    return [
        CorpusRunRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


# --- a run and its record (§8.7; L45, L46, L186, L202, L207) -------------------------


@pytest.mark.anyio
async def test_a_run_scores_each_model_case_k_times_in_id_order_and_appends_its_record(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
) -> None:
    installed = run_settings(corpus_repeats=2, corpus_concurrency=1)
    client = KeyedFakeLLMClient(
        {_raw("b"): [_ok(1, 2), _ok(3, 4)], _raw("a"): [_ok(5, 6), _ok(7, 8)]}
    )
    reads = lineage(client)
    cases = [_case("b"), _injected("injected"), _case("a")]
    record = await score_corpus(cases, client=client, judge_factory=None)

    assert reads == ["sha", "dirty"]
    assert [(r.case_id, r.repeat) for r in record.cases] == [("a", 0), ("a", 1), ("b", 0), ("b", 1)]
    assert [r.status for r in record.cases] == ["passed"] * 4
    assert all(r.draft == DRAFT and r.error is None for r in record.cases)
    assert (record.git_sha, record.git_dirty) == (SHA, True)
    assert (record.model, record.prompt_version) == ("model-under-test", PROMPT_VERSION)
    assert record.corpus_version == corpus_version([_case("a"), _case("b")])
    assert record.checks_version == CHECKS_VERSION
    assert record.checks_config == installed.checks_config()
    assert (record.repeats, record.concurrency, record.n_cases) == (2, 1, 2)
    assert record.judge_enabled is False
    assert record.ran_at.utcoffset() == timedelta(0)
    assert record.usage == TokenUsage(input_tokens=16, output_tokens=20)
    assert record.judge_usage == TokenUsage()
    assert (record.metrics.control_specificity, record.metrics.pass_rate) == (1.0, 1.0)
    assert _lines(installed.runs_path) == [record]


@pytest.mark.anyio
async def test_an_upstream_error_on_one_case_is_one_errored_row_and_the_others_score(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
) -> None:
    run_settings(corpus_repeats=1)
    client = KeyedFakeLLMClient({_raw("a"): [_upstream()], _raw("b"): [_ok()]})
    lineage(client)
    record = await score_corpus([_case("a"), _case("b")], client=client, judge_factory=None)
    failed, scored = record.cases
    assert (failed.case_id, failed.status, failed.error) == ("a", "failed", "APIConnectionError")
    assert (failed.usage, failed.validation_attempts, failed.draft) == (None, None, None)
    assert (scored.case_id, scored.status, scored.error) == ("b", "passed", None)


@pytest.mark.anyio
async def test_a_run_where_every_case_fails_still_writes_its_record(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
) -> None:
    installed = run_settings(corpus_repeats=1)
    client = KeyedFakeLLMClient(
        {_raw("a"): [_upstream()], _raw("b"): [text_message("no tool", input_tokens=4)]}
    )
    lineage(client)
    record = await score_corpus([_case("a"), _case("b")], client=client, judge_factory=None)
    assert [r.error for r in record.cases] == ["APIConnectionError", "model_output_invalid"]
    assert record.metrics.pass_rate == 0.0
    assert record.usage == TokenUsage(input_tokens=4, output_tokens=20)  # the known cost only
    assert _lines(installed.runs_path) == [record]


@pytest.mark.anyio
async def test_each_rows_cost_comes_from_its_own_path_and_the_record_sums_them(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_settings(corpus_repeats=1)

    def case_result(
        case: EvalCase,
        repeat: int,
        report: EvalReport,
        result: SummarizationResult,
        *,
        summarize_wall_s: float,
    ) -> CaseResult:
        if case.id == "d-crash-after":
            raise _Crash("building the row")
        return real_case_result(case, repeat, report, result, summarize_wall_s=summarize_wall_s)

    monkeypatch.setattr(corpus, "case_result", case_result)
    client = KeyedFakeLLMClient(
        {
            _raw("a-retried"): [
                tool_use_message(INVALID_INPUT, input_tokens=3, output_tokens=4),
                _ok(5, 6),
            ],
            _raw("b-truncated"): [
                tool_use_message(VALID_INPUT, stop_reason="max_tokens", input_tokens=7)
            ],
            _raw("c-upstream"): [_upstream()],
            _raw("d-crash-after"): [_ok(9, 10)],
        }
    )
    lineage(client)
    ids = ["a-retried", "b-truncated", "c-upstream", "d-crash-after"]
    record = await score_corpus([_case(i) for i in ids], client=client, judge_factory=None)
    rows = {r.case_id: r for r in record.cases}

    def cost(row: CaseResult) -> tuple[TokenUsage | None, int | None, str | None, bool]:
        return row.usage, row.validation_attempts, row.error, row.draft is not None

    # L186: success -> RunMetadata; pipeline failure -> the OrchestratorError; a crash after
    # summarize returned -> RunMetadata again; a crash inside it -> nothing survives.
    assert cost(rows["a-retried"]) == (TokenUsage(input_tokens=8, output_tokens=10), 2, None, True)
    assert cost(rows["b-truncated"]) == (
        TokenUsage(input_tokens=7, output_tokens=20),
        1,
        "output_truncated",
        False,
    )
    assert cost(rows["c-upstream"]) == (None, None, "APIConnectionError", False)
    assert cost(rows["d-crash-after"]) == (
        TokenUsage(input_tokens=9, output_tokens=10),
        1,
        "_Crash",
        True,
    )
    assert record.usage == TokenUsage(input_tokens=24, output_tokens=40)


@pytest.mark.anyio
async def test_the_judge_is_built_per_case_and_a_raise_building_it_loses_one_row(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
) -> None:
    run_settings(corpus_repeats=3, corpus_concurrency=1)
    client = KeyedFakeLLMClient({_raw("a"): [_ok(), _ok(), _ok()]})
    lineage(client)
    built: list[FakeJudge] = []

    def judge_factory() -> Judge:
        if len(built) == 1:
            built.append(FakeJudge())  # counted, never returned
            raise _Crash("building the judge")
        judge = FakeJudge(usage=TokenUsage(input_tokens=2, output_tokens=1), script=entail_all)
        built.append(judge)
        return judge

    record = await score_corpus([_case("a")], client=client, judge_factory=judge_factory)
    assert len(built) == 3
    crashed = [r for r in record.cases if r.error is not None]
    assert [(r.error, r.draft) for r in crashed] == [("_Crash", DRAFT)]  # L203: after summarize
    assert [r.status for r in record.cases].count("passed") == 2
    assert record.judge_enabled is True
    assert record.judge_usage == TokenUsage(input_tokens=4, output_tokens=2)


# --- what a run refuses before it spends (L207) --------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("cases", "runs_path", "raises", "match"),
    [
        ([_injected("injected")], None, ValueError, "no model cases"),
        ([_case("dup"), _case("ok"), _case("dup")], None, ValueError, r"\['dup'\]"),
        ([_case("a")], "is-a-directory.jsonl", ValueError, "is not a file"),
        ([_case("a")], "a-file/corpus_runs.jsonl", FileExistsError, "a-file"),
    ],
    ids=["no-model-cases", "duplicate-ids", "runs-path-is-a-directory", "parent-is-a-file"],
)
async def test_a_run_that_cannot_land_its_record_refuses_before_its_first_call(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    tmp_path: Path,
    cases: list[EvalCase],
    runs_path: str | None,
    raises: type[Exception],
    match: str,
) -> None:
    (tmp_path / "is-a-directory.jsonl").mkdir()
    (tmp_path / "a-file").write_text("")
    run_settings(runs_path=None if runs_path is None else tmp_path / runs_path)
    client = KeyedFakeLLMClient({})  # any call fails the test
    lineage(client)
    with pytest.raises(raises, match=match):
        await score_corpus(cases, client=client, judge_factory=None)
    assert client.messages.calls == []


@pytest.mark.anyio
async def test_a_tree_git_cannot_read_refuses_before_the_first_call(
    run_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = run_settings()

    def outside_a_checkout() -> str:
        raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])

    def unreached() -> bool:
        pytest.fail("git_is_dirty ran: the real tree is off limits (§11)")

    monkeypatch.setattr(corpus, "current_git_sha", outside_a_checkout)
    monkeypatch.setattr(corpus, "git_is_dirty", unreached)
    client = KeyedFakeLLMClient({})
    with pytest.raises(subprocess.CalledProcessError):
        await score_corpus([_case("a")], client=client, judge_factory=None)
    assert client.messages.calls == []
    assert not installed.runs_path.parent.exists()


def test_plan_run_makes_the_record_s_directory_but_never_the_record(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
) -> None:
    installed = run_settings()
    lineage(KeyedFakeLLMClient({}))
    plan = plan_run([_case("b"), _case("a")])
    assert [c.id for c in plan.model_cases] == ["a", "b"]
    assert plan.corpus_version == corpus_version([_case("a"), _case("b")])
    assert (plan.git_sha, plan.git_dirty) == (SHA, True)
    assert installed.runs_path.parent.is_dir()
    # an empty untracked file shows in git status: the run would dirty its own lineage
    assert not installed.runs_path.exists()


# --- concurrency and the wall clock (L201, L202) --------------------------------------


@pytest.mark.anyio
async def test_at_most_corpus_concurrency_calls_are_in_flight(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
) -> None:
    run_settings(corpus_repeats=1, corpus_concurrency=2)
    client = KeyedFakeLLMClient({_raw(i): [_ok()] for i in ("a", "b", "c")})
    lineage(client)
    record = await score_corpus(
        [_case(i) for i in ("a", "b", "c")], client=client, judge_factory=None
    )
    assert client.messages.peak_in_flight == 2
    assert record.concurrency == 2
    assert [r.status for r in record.cases] == ["passed"] * 3


@pytest.mark.anyio
async def test_the_wall_clock_starts_inside_the_semaphore_and_stops_with_summarize(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_settings(corpus_repeats=1, corpus_concurrency=1)
    ticks = [0]  # extra ticks, past the calls answered

    def case_result(
        case: EvalCase,
        repeat: int,
        report: EvalReport,
        result: SummarizationResult,
        *,
        summarize_wall_s: float,
    ) -> CaseResult:
        if case.id == "d-crash-after":
            ticks[0] += 5  # time passes after summarize returned, then the row crashes
            raise _Crash("building the row")
        return real_case_result(case, repeat, report, result, summarize_wall_s=summarize_wall_s)

    monkeypatch.setattr(corpus, "case_result", case_result)
    client = KeyedFakeLLMClient(
        {
            _raw("a-ok"): [_ok()],
            _raw("b-truncated"): [tool_use_message(VALID_INPUT, stop_reason="max_tokens")],
            _raw("c-upstream"): [_upstream()],
            _raw("d-crash-after"): [_ok()],
        }
    )
    lineage(client)
    # one tick per answered call: a clock started while queued counts the calls ahead of it
    clock = SimpleNamespace(perf_counter=lambda: float(client.messages.answered + ticks[0]))
    monkeypatch.setattr(corpus, "time", clock)
    ids = ["a-ok", "b-truncated", "c-upstream", "d-crash-after"]
    record = await score_corpus([_case(i) for i in ids], client=client, judge_factory=None)
    # every path: a success, a pipeline failure, a crash inside summarize, and one after it
    assert [r.summarize_wall_s for r in record.cases] == [1.0, 1.0, 1.0, 1.0]
    assert [r.error for r in record.cases] == [
        None,
        "output_truncated",
        "APIConnectionError",
        "_Crash",
    ]


# --- a crashed case's log line (L113) -------------------------------------------------


def _crash_inside_summarize() -> _Crash:
    exc = _Crash(MESSAGE_SENTINEL)
    exc.__cause__ = ValueError(CAUSE_SENTINEL)
    return exc


@pytest.mark.anyio
async def test_a_crashed_case_is_logged_by_structure_never_its_message(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    run_settings(corpus_repeats=1)
    client = KeyedFakeLLMClient({_raw("a"): [_crash_inside_summarize()]})
    lineage(client)
    await score_corpus([_case("a")], client=client, judge_factory=None)
    assert MESSAGE_SENTINEL not in caplog.text  # L113: no str(exc), no exc_info
    assert CAUSE_SENTINEL not in caplog.text  # nor the chained cause
    ours = [r for r in caplog.records if r.name == "backend.corpus"]
    assert len(ours) == 1
    assert (ours[0].levelno, ours[0].exc_info) == (logging.ERROR, None)
    fields = ours[0].getMessage().split(" ")
    assert fields[:4] == ["case_crashed", "code=case_errored", "case=a", "exc_type=_Crash"]
    assert len(fields) == 5 and fields[4].startswith("frames=")
    frames = fields[4].removeprefix("frames=").split(">")
    # L69's frames: the scorer outermost, the fake's raise innermost
    assert frames[0].startswith("backend/corpus.py:") and frames[0].endswith(":run_one")
    assert frames[-1].startswith("tests/fakes.py:") and frames[-1].endswith(":create")


# --- the record file ------------------------------------------------------------------


class _Line(BaseModel):
    text: str


def test_append_jsonl_appends_one_line_per_record(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    first, second = _Line(text="two\nlines"), _Line(text="caf" + chr(0xE9))
    append_jsonl(path, first)
    append_jsonl(path, second)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [_Line.model_validate_json(line) for line in lines] == [first, second]


# --- the git reads, on a repository under tmp_path (L207) -----------------------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A one-commit repository as the working directory, with no outside config or repo.

    GIT_DIR and its kin would point git at another repository (a hook sets them); the global
    and system configs could sign commits, run hooks, or hide untracked files.
    """
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    _git("init", "-q")
    (root / ".gitignore").write_text("ignored/\n")
    (root / "tracked.txt").write_text("v1\n")
    _git("add", ".")
    _git("commit", "-q", "-m", "init")
    yield root


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def test_current_git_sha_is_head(repo: Path) -> None:
    assert current_git_sha() == _git("rev-parse", "HEAD").strip()


def test_a_clean_tree_is_clean_even_with_an_empty_directory(repo: Path) -> None:
    (repo / "runs").mkdir()  # what prepare_runs_path leaves: git lists no empty directory
    (repo / "ignored").mkdir()
    (repo / "ignored" / "x.txt").write_text("ignored\n")
    assert git_is_dirty() is False


@pytest.mark.parametrize(
    "change",
    ["modified", "staged", "untracked", "untracked-under-showUntrackedFiles-no"],
)
def test_git_is_dirty_counts_tracked_changes_and_untracked_files(repo: Path, change: str) -> None:
    if change == "modified":
        (repo / "tracked.txt").write_text("v2\n")
    elif change == "staged":
        (repo / "new.txt").write_text("new\n")
        _git("add", "new.txt")
    else:
        (repo / "cases").mkdir()
        (repo / "cases" / "new_case.yaml").write_text("id: new_case\n")
        if change.endswith("-no"):
            _git("config", "status.showUntrackedFiles", "no")
    assert git_is_dirty() is True


def test_git_is_dirty_never_writes_the_index(repo: Path) -> None:
    tracked = repo / "tracked.txt"
    stat = tracked.stat()
    os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))  # same bytes, new stat
    index = (repo / ".git" / "index").read_bytes()
    assert git_is_dirty() is False
    assert (repo / ".git" / "index").read_bytes() == index  # no refresh, so no index.lock


def test_current_git_sha_raises_outside_a_checkout(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    with pytest.raises(subprocess.CalledProcessError) as raised:
        current_git_sha()
    assert raised.value.returncode == 128


# --- the command line (L210, L240-L242) ----------------------------------------------


def _write_cases(directory: Path, model: list[str], injected: list[str]) -> Path:
    """Case files for main to load: |- keeps raw_text free of a trailing newline."""
    directory.mkdir()
    for case_id in model + injected:
        text = f"id: {case_id}\nspecies: control\nraw_text: |-\n  {_raw(case_id)}\ntrap: null\n"
        if case_id in injected:
            text += (
                "draft:\n  claims:\n    - text: Lungs clear\n      section: O\n"
                "      source_quote: Lungs clear on exam\n"
            )
        (directory / f"{case_id}.yaml").write_text(text, encoding="utf-8")
    return directory


@pytest.fixture
def no_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dry run that builds a client or calls score_corpus fails the test."""

    def no_client() -> LLMClient:
        pytest.fail("the dry run built a client")

    def no_score(*args: object, **kwargs: object) -> object:
        pytest.fail("the dry run called score_corpus")

    monkeypatch.setattr(corpus, "get_client", no_client)
    monkeypatch.setattr(corpus, "score_corpus", no_score)


@pytest.mark.usefixtures("no_spend")
def test_the_dry_run_prints_the_plan_and_spends_nothing(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installed = run_settings(corpus_repeats=2, max_validation_retries=1)
    cases = _write_cases(tmp_path / "cases", model=["b", "a", "c"], injected=["injected"])
    monkeypatch.setattr(corpus, "CASES_DIR", cases)
    lineage(KeyedFakeLLMClient({}))
    version = corpus_version([_case(i) for i in "abc"])
    assert corpus.main([]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "model cases: 3 (1 injected, not run)",
        "calls: 6 (n=3 x k=2), at most 12 with validation retries",
        f"git_sha={SHA} git_dirty=True",
        f"model=model-under-test prompt_version={PROMPT_VERSION}",
        f"corpus_version={version} checks_version={CHECKS_VERSION}",
        f"record: {installed.runs_path}",
        "dry run: nothing spent; --spend makes these calls",
    ]
    assert not installed.runs_path.exists()


@pytest.mark.parametrize("argv", [[], ["--spend"]], ids=["dry-run", "spend"])
def test_both_paths_refuse_a_run_with_no_model_case(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
) -> None:
    run_settings()
    client = KeyedFakeLLMClient({})  # any call fails the test
    lineage(client)
    monkeypatch.setattr(corpus, "CASES_DIR", _write_cases(tmp_path / "cases", [], ["injected"]))
    monkeypatch.setattr(corpus, "get_client", lambda: client)
    with pytest.raises(ValueError, match="no model cases"):
        corpus.main(argv)
    assert client.messages.calls == []


def test_the_spend_appends_the_record_the_dry_run_described(
    run_settings: Callable[..., Settings],
    lineage: Callable[[KeyedFakeLLMClient], list[str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installed = run_settings(corpus_repeats=1)
    cases = _write_cases(tmp_path / "cases", model=["a", "b"], injected=["injected"])
    monkeypatch.setattr(corpus, "CASES_DIR", cases)
    client = KeyedFakeLLMClient({_raw("a"): [_ok(1, 2)], _raw("b"): [_ok(3, 4)]})
    lineage(client)
    monkeypatch.setattr(corpus, "get_client", lambda: client)
    assert corpus.main([]) == 0
    planned = capsys.readouterr().out.splitlines()
    assert corpus.main(["--spend"]) == 0
    spent = capsys.readouterr().out.splitlines()
    (record,) = _lines(installed.runs_path)
    assert spent == [
        f"metrics: {record.metrics.model_dump_json()}",
        "usage: input_tokens=4 output_tokens=6",
        f"record appended to {installed.runs_path}",
    ]
    assert [r.case_id for r in record.cases] == ["a", "b"]
    assert record.judge_enabled is False
    # the lineage the dry run printed is the lineage the record carries
    assert planned[2:5] == [
        f"git_sha={record.git_sha} git_dirty={record.git_dirty}",
        f"model={record.model} prompt_version={record.prompt_version}",
        f"corpus_version={record.corpus_version} checks_version={record.checks_version}",
    ]
