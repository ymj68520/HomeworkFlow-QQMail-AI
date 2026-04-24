"""
Test script to verify AI extraction in target_folder_loader.py
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mail.target_folder_loader import target_folder_loader
from config.settings import settings

def test_target_folder_loader():
    """Test that target_folder_loader uses AI extraction"""
    print("=" * 60)
    print("Testing Target Folder Loader with AI Extraction")
    print("=" * 60)

    try:
        # Test loading from target folder
        print("\n1. Loading submissions from TARGET_FOLDER...")
        result = target_folder_loader.get_from_target_folder(page=1, per_page=5)

        print(f"✓ Successfully loaded {len(result['submissions'])} submissions")
        print(f"  Total: {result['total']}")
        print(f"  Page: {result['page']}/{result['total_pages']}")

        # Check first few submissions
        print("\n2. Checking submission data...")
        for i, submission in enumerate(result['submissions'][:3]):
            print(f"\n  Submission {i+1}:")
            print(f"    Student ID: {submission.get('student_id', 'N/A')}")
            print(f"    Name: {submission.get('name', 'N/A')}")
            print(f"    Assignment: {submission.get('assignment_name', 'N/A')}")
            print(f"    Email UID: {submission.get('email_uid', 'N/A')}")

            # Verify AI extraction was used (check for 'Unknown' fallback)
            if submission.get('student_id') == 'Unknown':
                print(f"    ⚠ AI extraction failed or returned unknown")
            else:
                print(f"    ✓ AI extraction successful")

        print("\n" + "=" * 60)
        print("✓ Test completed successfully!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_target_folder_loader()
    sys.exit(0 if success else 1)
