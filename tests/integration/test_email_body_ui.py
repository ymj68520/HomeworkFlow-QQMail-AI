"""Test script to verify email body card UI loads"""
import sys
import customtkinter as ctk
from gui.email_preview_drawer import EmailPreviewDrawer

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Create main window
root = ctk.CTk()
root.geometry("1200x800")
root.title("Email Body Card Test")

# Create a simple frame to host the drawer
test_frame = ctk.CTkFrame(root)
test_frame.pack(fill="both", expand=True)

# Create the drawer
drawer = EmailPreviewDrawer(test_frame, fg_color="#F8F9FA")
drawer.place(relheight=1)

# Test data
test_data = {
    'student_id': '20250101',
    'name': 'Test Student',
    'email': 'test@example.com',
    'is_late': False,
    'is_downloaded': True,
    'is_replied': False,
    'email_subject': 'Test Email Subject with Email Body Card',
    'email_from': 'sender@example.com',
    'received_time': '2026-04-24 10:00:00',
    'submission_time': '2026-04-24 10:05:00',
    'email_uid': '12345',
    'assignment_name': 'Test Assignment',
    'local_path': 'C:\\Test\\Path',
    'id': 1,
    'attachments': []
}

# Show the drawer with test data
drawer.show(test_data)

print("✓ UI initialized successfully")
print("✓ Email preview drawer created")
print("✓ Test data loaded")
print("\nPlease check if the '邮件正文' card is visible in the drawer.")
print("The card should show loading state or email body content.")

# Run for 10 seconds then close
root.after(10000, root.destroy)
root.mainloop()

print("\n✓ Test completed successfully")
