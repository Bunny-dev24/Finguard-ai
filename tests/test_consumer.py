"""process_record() should isolate failures per-message and route them
to the DLQ instead of raising."""
from unittest.mock import MagicMock, patch

from src.core.config import settings
from src.streaming.consumer import process_record


@patch("src.streaming.consumer.ScoringService")
@patch("src.streaming.consumer.SessionLocal")
def test_bad_message_goes_to_dlq_and_does_not_raise(mock_session, mock_scoring_cls):
    mock_scoring_cls.return_value.score_and_persist.side_effect = KeyError("user_id")
    producer = MagicMock()

    process_record({"transaction_id": "bad-1"}, producer)

    dlq_calls = [c for c in producer.send.call_args_list
                 if c.args[0] == settings.kafka_dlq_topic]
    assert len(dlq_calls) == 1
    assert dlq_calls[0].args[1]["record"]["transaction_id"] == "bad-1"


@patch("src.streaming.consumer.ScoringService")
@patch("src.streaming.consumer.SessionLocal")
def test_good_message_after_bad_one_still_processes(mock_session, mock_scoring_cls):
    mock_scoring_cls.return_value.score_and_persist.side_effect = [
        KeyError("boom"),
        {"transaction_id": "ok-1", "is_fraud": False, "fraud_probability": 0.1,
         "model": "lightgbm"},
    ]
    producer = MagicMock()

    process_record({"transaction_id": "bad-1"}, producer)
    process_record({"transaction_id": "ok-1"}, producer)

    assert mock_scoring_cls.return_value.score_and_persist.call_count == 2
