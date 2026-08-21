from unittest.mock import MagicMock,patch
from models.llm_schemas import CodeResponse,CriticVerdict
from core.memory import InMemorySessionStore
import main


def make_fake_coder(code_responses):
    """
    Returns a fake CoderAgent whose .generate_code() gives back
    each CodeResponse in `code_responses`, in order, one per call.
    """
    fake = MagicMock()
    fake.generate_code.side_effect = code_responses
    return fake

def make_fake_critic(verdicts):
    fake = MagicMock()
    fake.evaluate_logic.side_effect = verdicts
    return fake


# ---------------------------------------------------------
# Test 1: Succeeds on the very first attempt
# ---------------------------------------------------------
@patch("main.SummarizerAgent")
@patch("main.CriticAgent")
@patch("main.CoderAgent")
def test_succeed_first_try(mock_coder_cls,mock_critic_cls,mock_summarizer_cls):
    # Wire the fakes: whenever main.py does CoderAgent(client=...), give it our fake
    mock_coder_cls.return_value = make_fake_coder([
        CodeResponse(info="computing total", code="print(2 + 2)")
    ])  
    mock_critic_cls.return_value = make_fake_critic([
        CriticVerdict(is_correct=True, critique="")
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "Computed 2+2"

    memory = InMemorySessionStore()

    result=main.run_self_healing_pipeline(
        df=None,csv_schema="cols",user_query="add 2+2",
        critic_ground_truth="add 2+2",memory=memory,session_id="s1"
    )

    assert result == "4"
    # coder should have only been called ONCE — no retries needed
    assert mock_coder_cls.return_value.generate_code.call_count == 1


# ---------------------------------------------------------
# Test 2: Crashes once (execution error), then succeeds
# ---------------------------------------------------------
@patch("main.SummarizerAgent")
@patch("main.CriticAgent")
@patch("main.CoderAgent")
def test_recovers_from_execution_error(mock_coder_cls,mock_critic_cls,mock_summarizer_cls):

    mock_coder_cls.return_value=make_fake_coder([
        CodeResponse(info="attempt 1",code="print(undefined_variable)"),
        CodeResponse(info="attempt 2",code="print(5)")
    ])

    mock_critic_cls.return_value=make_fake_critic([
        CriticVerdict(is_correct=True,critique="")
    ])

    mock_summarizer_cls.return_value.summarize.return_value="summary"

    memory = InMemorySessionStore()
    
    result = main.run_self_healing_pipeline(
        df=None, csv_schema="cols", user_query="print 5",
        critic_ground_truth="print 5", memory=memory, session_id="s2"
    )

    assert result == "5"
    # coder called TWICE (crashed once, fixed on retry)
    assert mock_coder_cls.return_value.generate_code.call_count == 2
    # critic only called ONCE — it never sees the crashed attempt at all
    assert mock_critic_cls.return_value.evaluate_logic.call_count == 1


# ---------------------------------------------------------
# Test 3: Runs fine but critic rejects it once, then approves
# ---------------------------------------------------------
@patch("main.SummarizerAgent")
@patch("main.CriticAgent")
@patch("main.CoderAgent")
def test_recovers_from_logic_rejection(mock_coder_cls, mock_critic_cls, mock_summarizer_cls):
    mock_coder_cls.return_value = make_fake_coder([
        CodeResponse(info="wrong logic", code="print(1)"),
        CodeResponse(info="fixed logic", code="print(2)")
    ])
    mock_critic_cls.return_value = make_fake_critic([
        CriticVerdict(is_correct=False, critique="Wrong number entirely"),
        CriticVerdict(is_correct=True, critique="")
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "summary"

    memory = InMemorySessionStore()

    result = main.run_self_healing_pipeline(
        df=None, csv_schema="cols", user_query="print 2",
        critic_ground_truth="print 2", memory=memory, session_id="s3"
    )

    assert result == "2"
    assert mock_coder_cls.return_value.generate_code.call_count == 2
    assert mock_critic_cls.return_value.evaluate_logic.call_count == 2


# ---------------------------------------------------------
# Test 4: Never succeeds — exhausts retries, returns None
# ---------------------------------------------------------
@patch("main.SummarizerAgent")
@patch("main.CriticAgent")
@patch("main.CoderAgent")
def test_gives_up_after_max_retries(mock_coder_cls, mock_critic_cls, mock_summarizer_cls):
    # Always the same rejected response, repeated enough times to exhaust retries
    mock_coder_cls.return_value = make_fake_coder([
        CodeResponse(info="always wrong", code="print(999)") for _ in range(4)
    ])
    mock_critic_cls.return_value = make_fake_critic([
        CriticVerdict(is_correct=False, critique="never right") for _ in range(4)
    ])

    memory = InMemorySessionStore()

    result = main.run_self_healing_pipeline(
        df=None, csv_schema="cols", user_query="impossible task",
        critic_ground_truth="impossible task", memory=memory,
        session_id="s4", max_retries=4
    )

    assert result is None
    assert mock_coder_cls.return_value.generate_code.call_count == 4
    # summarizer should NEVER be called — nothing succeeded
    mock_summarizer_cls.return_value.summarize.assert_not_called()

# ---------------------------------------------------------
# Test 5: Memory only stores the SUCCESSFUL final code, not failed attempts
# ---------------------------------------------------------
@patch("main.SummarizerAgent")
@patch("main.CriticAgent")
@patch("main.CoderAgent")
def test_only_successful_code_saved_to_memory(mock_coder_cls, mock_critic_cls, mock_summarizer_cls):
    mock_coder_cls.return_value = make_fake_coder([
        CodeResponse(info="bad", code="print(bad_var)"),   # crashes
        CodeResponse(info="good", code="print(42)")         # succeeds
    ])
    mock_critic_cls.return_value = make_fake_critic([
        CriticVerdict(is_correct=True, critique="")
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "did the thing"

    memory = InMemorySessionStore()
    main.run_self_healing_pipeline(
        df=None, csv_schema="cols", user_query="print 42",
        critic_ground_truth="print 42", memory=memory, session_id="s5"
    )

    session = memory.get_session("s5")
    assert len(session.history) == 1                                # only ONE turn saved
    assert session.history[0].successful_code == "print(42)"         # the WINNING code
    assert "bad_var" not in session.history[0].successful_code        # NOT the crashed attempt