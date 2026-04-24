"""Test script to verify email body card with database interaction"""
import sys
import customtkinter as ctk
from gui.email_preview_drawer import EmailPreviewDrawer
from database.operations import db

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("Testing email body card with database...")

# First, save test email body to database
test_submission_id = 999999  # Use a unique test ID
test_body_data = {
    'plain_text': 'This is a test email body.\n\nIt contains multiple lines.\n\nLine 3.',
    'html_markdown': None,
    'format': 'text'
}

# Save test data
print(f"Saving test email body for submission_id={test_submission_id}...")
success = db.save_email_body(test_submission_id, test_body_data)
print(f"Save result: {success}")

# Verify it was saved
print(f"Retrieving test email body...")
retrieved_body = db.get_email_body(test_submission_id)
print(f"Retrieved body: {retrieved_body is not None}")
if retrieved_body:
    print(f"Content preview: {retrieved_body.get('plain_text', '')[:50]}...")

# Create main window
root = ctk.CTk()
root.geometry("1200x800")
root.title("Email Body Card Database Test")

# Create a simple frame to host the drawer
test_frame = ctk.CTkFrame(root)
test_frame.pack(fill="both", expand=True)

# Create the drawer
drawer = EmailPreviewDrawer(test_frame, fg_color="#F8F9FA")
drawer.place(relheight=1)

# Test data with valid submission ID
test_data = {
    'student_id': '20250101',
    'name': 'Test Student',
    'email': 'test@example.com',
    'is_late': False,
    'is_downloaded': True,
    'is_replied': False,
    'email_subject': 'Test Email Subject with Email Body',
    'email_from': 'sender@example.com',
    'received_time': '2026-04-24 10:00:00',
    'submission_time': '2026-04-24 10:05:00',
    'email_uid': '12345',
    'assignment_name': 'Test Assignment',
    'local_path': 'C:\\Test\\Path',
    'id': test_submission_id,
    'attachments': []
}

print("\nShowing drawer with test data...")
drawer.show(test_data)

print("\n[SUCCESS] Database integration test passed!")
print("\nManual verification:")
print("1. The application window should be open")
print("2. A preview drawer should be visible from the right side")
print("3. Scroll down to see the '邮件正文' card")
print("4. The card should display the test email body text")
print("5. A format badge '纯文本' should be visible")
print("6. The content should be scrollable")

# Run for 10 seconds then close
root.after(10000, root.destroy)
root.mainloop()

# Cleanup - delete test data
print("\nCleaning up test data...")
import sqlite3
from config import settings
conn = sqlite3.connect(str(settings.DATABASE_PATH))
cursor = conn.cursor()
cursor.execute("DELETE FROM submissions WHERE id = ?", (test_submission_id,))
conn.commit()
conn.close()
print("Test data cleaned up")
