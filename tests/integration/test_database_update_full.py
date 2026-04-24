import pytest
from datetime import datetime
from database.operations import DatabaseOperations
from database.models import Submission, Student, Assignment, SubmissionStatus

@pytest.fixture
def db():
    ops = DatabaseOperations()
    yield ops
    ops.close()

def test_update_submission_full(db):
    # 1. Create a dummy submission
    email_uid = f"test_uid_{int(datetime.now().timestamp())}"
    submission = db.create_submission(
        email_uid=email_uid,
        email_subject="Test Assignment",
        sender_email="old@student.com",
        sender_name="Old Name",
        submission_time=datetime(2023, 10, 1),
        student_id="temp_student",
        assignment_name="temp_assignment",
        status='pending'
    )
    assert submission is not None
    submission_id = submission.id

    # 2. Set up assignment deadline for late calculation
    assignment_name = "Assignment 1"
    db.create_assignment(assignment_name, deadline=datetime(2023, 9, 30)) # Already late

    # 3. Call update_submission_full
    new_student_id = "2023001"
    new_name = "New Student Name"
    new_email = "new@student.com"
    new_status = "completed"

    success = db.update_submission_full(
        submission_id=submission_id,
        student_id=new_student_id,
        name=new_name,
        assignment_name=assignment_name,
        status=new_status,
        email=new_email
    )

    assert success is True

    # 4. Verify updates
    updated_submission = db.session.query(Submission).filter_by(id=submission_id).first()
    assert updated_submission.status == new_status
    assert updated_submission.is_late is True
    assert updated_submission.is_replied is True
    assert updated_submission.is_downloaded is True

    student = db.get_student(new_student_id)
    assert student is not None
    assert student.name == new_name
    assert student.email == new_email

    assignment = db.get_assignment(assignment_name)
    assert assignment is not None
    assert updated_submission.assignment_id == assignment.id

    # 5. Test student update if already exists
    newer_name = "Newer Student Name"
    success = db.update_submission_full(
        submission_id=submission_id,
        student_id=new_student_id,
        name=newer_name,
        assignment_name=assignment_name,
        status="unreplied",
        email=new_email
    )
    assert success is True
    
    student = db.get_student(new_student_id)
    assert student.name == newer_name
    
    updated_submission = db.session.query(Submission).filter_by(id=submission_id).first()
    assert updated_submission.status == "unreplied"
    assert updated_submission.is_replied is True # Should stay True if already True? 
    # Actually my logic only sets to True, doesn't set to False if it's already True.
    assert updated_submission.is_downloaded is True

    # Clean up
    db.session.delete(updated_submission)
    db.session.commit()
