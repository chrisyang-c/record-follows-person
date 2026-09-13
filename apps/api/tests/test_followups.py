from datetime import UTC, datetime, timedelta

from record_schema import FollowUp

from record.followups import acknowledge, close, dispatch_due, list_tasks, outbox, schedule


def test_follow_up_schedule_is_idempotent_and_dispatches_once(records_root):
    due = datetime.now(UTC) - timedelta(minutes=1)
    follow_up = FollowUp(due_at=due, question="現在比較好了嗎？", set_by="N001")
    first = schedule("P001", follow_up, source_thread="thread-1")
    second = schedule("P001", follow_up, source_thread="thread-1")
    assert first.id == second.id
    queued = dispatch_due(datetime.now(UTC))
    assert [task.id for task in queued] == [first.id]
    assert dispatch_due(datetime.now(UTC)) == []
    assert len(outbox("P001")) == 1
    assert list_tasks("P001", status="queued")[0].attempts == 1


def test_follow_up_can_be_acknowledged_without_timeline_write(records_root):
    task = schedule(
        "P002",
        FollowUp(
            due_at=datetime.now(UTC) + timedelta(hours=1),
            question="有發燒嗎？",
            set_by="N001",
        ),
        source_thread="thread-ack",
    )
    acknowledged = acknowledge(task.id, answer="沒有，精神正常")
    assert acknowledged.status == "acknowledged"
    assert acknowledged.answer == "沒有，精神正常"
    assert list_tasks("P002")[0].answered_at is not None
    assert close(task.id).status == "closed"
