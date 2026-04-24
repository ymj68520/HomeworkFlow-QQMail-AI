# Data Flow Redesign - Email-Centric Architecture with Version History

**Date:** 2025-04-21
**Status:** Approved
**Author:** Claude Sonnet 4.6

## Executive Summary

Redesign the QQ邮箱作业收发 system's data flow to fix critical issues: data inconsistency, performance problems, duplicate handling, and sync conflicts. The new architecture establishes **email as the single source of truth** with database as a read-through cache and versioned local storage.

**Key Improvements:**
- ✅ Fast startup with cached data (<100ms)
- ✅ Background sync from TARGET_FOLDER (2-5s)
- ✅ Version history for all submissions (v1/, v2/, v3/...)
- ✅ Network failure recovery with retry logic
- ✅ No data loss - immutable email records

---

## Architecture Overview

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Layer (GUI)                          │
│  - Shows cached data instantly                              │
│  - Notified of updates via callback/events                  │
│  - Never blocks on network operations                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Service Layer (New)                        │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ DataSyncService │  │ VersionManager  │                   │
│  │ - Background sync│  │ - Track versions│                   │
│  │ - Cache invalid. │  │ - Resolve dups  │                   │
│  └─────────────────┘  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────┬────────────────┬─────────────────────────┐
│   Email Layer    │  Database Layer│  Storage Layer          │
│  (Source of Truth│  (Read-through │  (Versioned Files)      │
│   - TARGET_FOLDER│   Cache/Index) │  - v1/, v2/, v3/...     │
│   - INBOX)       │                │                         │
└──────────────────┴────────────────┴─────────────────────────┘
```

### Key Principles

1. **Unidirectional flow**: Email → DB → UI (never reverse)
2. **Immutability**: Never modify emails, only add new ones
3. **Version folders**: Each submission gets `v1/`, `v2/`, etc.
4. **Reactive updates**: UI subscribes to data changes, doesn't poll

---

## Components

### New Components

#### 1. DataSyncService (`core/data_sync_service.py`)

Manages synchronization between email and local cache.

```python
class DataSyncService:
    """Manages synchronization between email and local cache"""

    async def initial_sync(self) -> SyncResult:
        """Startup: Full sync from TARGET_FOLDER to DB"""

    async def incremental_sync(self) -> SyncResult:
        """Background: Sync only changes since last sync"""

    async def sync_single_email(self, uid: str) -> SyncResult:
        """On-demand: Sync specific email (for new arrivals)"""

    def get_cached_data(self) -> List[Submission]:
        """Instant: Return cached DB data for UI"""
```

**Responsibilities:**
- Orchestrate email → DB synchronization
- Maintain sync state (last_sync_time, cached_email_index)
- Emit events when data changes
- Handle retry logic for failed operations

#### 2. VersionManager (`core/version_manager.py`)

Manages submission versioning.

```python
class VersionManager:
    """Manages submission versioning"""

    def get_next_version(self, student_id: str, assignment: str) -> int:
        """Determine next version number (v1, v2, v3...)"""

    def create_version_folder(self, student_id: str, assignment: str,
                              version: int) -> Path:
        """Create versioned folder: submissions/作业1/2021001张三/v2/"""

    def get_all_versions(self, student_id: str, assignment: str) -> List[VersionInfo]:
        """Get all versions for a student+assignment"""

    def get_latest_version(self, student_id: str, assignment: str) -> VersionInfo:
        """Get the latest version only"""
```

**Responsibilities:**
- Track version numbers per student+assignment
- Create isolated version folders
- Provide version queries (all, latest, specific)
- Manage version metadata (_metadata.json in each folder)

#### 3. EmailIndexer (`mail/email_indexer.py`)

Fast email scanning without full parsing.

```python
class EmailIndexer:
    """Fast email scanning without full parsing"""

    def scan_target_folder(self) -> EmailIndex:
        """Quick scan: uid, subject, from, date (no body/attachments)"""

    def detect_changes(self, old_index: EmailIndex,
                      new_index: EmailIndex) -> ChangeSet:
        """Detect new, updated, deleted emails"""
```

**Responsibilities:**
- Perform fast IMAP scans (FETCH headers only)
- Detect changes vs previous scan
- Return lightweight index for comparison
- Cache index to avoid re-scanning

### Modified Components

#### 4. TargetFolderLoader (`mail/target_folder_loader.py`)

**Before:**
- Blocking call on `get_from_target_folder()`
- Merges data from email, DB, files on every load
- Slow pagination

**After:**
- Returns cached DB data instantly via `DataSyncService.get_cached_data()`
- Triggers background sync if data is stale
- Emits update events when sync completes

#### 5. DeduplicationHandler (`core/deduplication.py`)

**Before:**
- Deletes old files
- Replaces with new version
- Data loss if replacement fails

**After:**
- Creates new version folder (v2/, v3/, etc.)
- Updates `latest_version` pointer in DB
- Preserves all previous versions
- Never deletes data

#### 6. MainWindow (`gui/main_window.py`)

**Before:**
- Blocks on `target_folder_loader.get_from_target_folder()`
- Full UI refresh on every update
- No background sync

**After:**
- Instant load from cache
- Subscribes to data change events
- Incremental UI updates (only changed rows)
- Shows sync status indicator

---

## Data Flows

### Flow 1: Application Startup

**Problem Fixed:** A - Startup shows stale/wrong data

```
1. UI Launch
   ↓
2. Load cached DB data (instant, <100ms)
   ↓
3. Display UI with cached data
   ↓
4. Trigger background sync (non-blocking)
   ↓
5. DataSyncService.initial_sync():
   a. EmailIndexer.scan_target_folder() - Fast scan (headers only)
   b. Detect changes vs last sync
   c. For new/changed emails:
      - Parse full email
      - Create version folders
      - Update DB cache
   d. For deleted emails:
      - Mark as deleted in DB (don't remove, preserve history)
   ↓
6. Emit UI update event with changes
   ↓
7. UI refreshes affected rows only (not full reload)
```

**Timeline:**
- 0ms: UI launches
- 50ms: Cached data displayed
- 100ms: Background sync starts
- 2-5s: Sync completes, UI updates

### Flow 2: New Email Arrives

**Problem Fixed:** B - Background listener doesn't process correctly

```
1. Background workflow detects new email in INBOX
   ↓
2. Process email:
   a. Parse with AI extractor
   b. Determine if it's a duplicate (check DB for student+assignment)
   c. If duplicate:
      - VersionManager.create_version_folder(v2/)
      - Save attachments to v2/
      - Update DB: set latest_version=v2, keep v1 record
   d. If new:
      - VersionManager.create_version_folder(v1/)
      - Save attachments to v1/
      - Create DB record with latest_version=v1
   ↓
3. Move email to TARGET_FOLDER
   ↓
4. Send confirmation email
   ↓
5. Emit UI update event
   ↓
6. UI updates (if visible)
```

### Flow 3: Manual Refresh

**Problem Fixed:** C - Manual refresh doesn't show latest changes

```
1. User clicks "刷新数据"
   ↓
2. Show loading indicator (don't block UI)
   ↓
3. DataSyncService.incremental_sync():
   a. Fast scan TARGET_FOLDER
   b. Compare with cached index
   c. Fetch only changed emails
   ↓
4. Update DB cache
   ↓
5. Emit UI update event
   ↓
6. UI refreshes changed rows
```

### Flow 4: Duplicate Submission

**Problem Fixed:** C/E - Duplicate submissions mishandled

**Scenario:** Student submits assignment, then submits corrected version

```
Email 1 arrives (UID 101):
  → Create submissions/作业1/2021001张三/v1/
  → DB: {student: "2021001张三", assignment: "作业1",
         latest_version: 1, email_uid: "101"}

Email 2 arrives (UID 102):
  → Detect duplicate (same student+assignment)
  → Create submissions/作业1/2021001张三/v2/
  → DB: Update latest_version: 2, email_uid: "102"
  → Keep v1 record in DB (is_latest: false)
```

**File Structure:**
```
submissions/
  └── 作业1/
      └── 2021001张三/
          ├── v1/
          │   ├── homework.docx
          │   └── _metadata.json
          ├── v2/
          │   ├── homework_revised.docx
          │   └── _metadata.json
          └── _latest -> v2/  (symlink or marker file)
```

**DB Schema Update:**
```sql
ALTER TABLE submissions ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE submissions ADD COLUMN is_latest BOOLEAN DEFAULT TRUE;
```

### Flow 5: Batch Operations

**Problem Fixed:** D - Batch operations create inconsistencies

**Solution:** All operations work on version folders, not flat paths

```
1. User selects rows and clicks "批量下载"
   ↓
2. UI shows confirmation dialog
   ↓
3. On confirm:
   a. Lock UI (disable buttons)
   b. For each submission:
      - Check if version folder exists
      - If missing: fetch from email, create folder
      - If exists: skip (or force-redownload if user confirmed)
   c. Update DB cache
   d. Unlock UI
   ↓
4. Background sync detects changes and updates UI
```

**Key improvement:** No conflicts because each version is isolated.

### Flow 6: Network Failure Recovery

**Problem Fixed:** F - Network failures leave partial state

**Solution:** Transactional operations with retry logic

```
1. All operations are transactional:
   a. Create version folder (temp name: .v2_temp/)
   b. Download attachments
   c. On success: rename .v2_temp/ → v2/
   d. On failure: delete .v2_temp/, log error
   ↓
2. DB operations wrapped in try/except:
   a. Begin transaction
   b. Update records
   c. Commit on success, rollback on error
   ↓
3. Retry logic:
   a. Failed operations logged to email_action_log table
   b. Background sync retries failed operations every 5min
   c. After 3 failures: mark as "manual review required"
```

---

## Error Handling

### Network Errors

**Connection timeout/failure:**
- Show toast: "网络连接失败，将在后台重试"
- Queue operation for retry
- Exponential backoff (30s, 2min, 5min, 10min)
- After 3 failures: Mark as "需要手动处理"

**Partial download (attachment corrupted):**
- Delete incomplete files
- Retry full download
- Log: "附件下载不完整: {filename}, 已重试"

### Email Parsing Errors

**AI extraction fails:**
- Fallback to regex extraction
- If still fails: Mark as "需要人工审核"
- Move to "待处理" folder in TARGET_FOLDER
- Log: "AI提取失败，已使用备用方法"

**Duplicate detection ambiguous:**
- Similar but not exact match (e.g., "2021001张三" vs "2021001 张三")
- Create folder with both: "2021001张三_疑重复/"
- Flag for manual review
- Don't auto-send confirmation email

### File System Errors

**Disk full:**
- Stop processing
- Show critical error: "磁盘空间不足，无法保存附件"
- Don't move email (stays in INBOX)
- Log to error table

**Permission denied:**
- Check if folder is read-only
- Show error: "无权限写入文件夹: {path}"
- Retry with elevated permissions or different location

### Database Errors

**Connection lost:**
- Use in-memory cache (DB is cache anyway)
- Queue writes for when DB reconnects
- Log: "数据库连接失败，使用内存缓存"

**Constraint violation (duplicate UID):**
- Should be impossible (UID is unique)
- If happens: Log critical error, investigate schema

### Edge Cases

**Same email UID but different content:**
- Detect: Content hash differs
- Create new version anyway (treat as new submission)
- Log: "检测到邮件内容变化，创建新版本"

**Student name in email differs from DB:**
- Use email's name (more recent)
- Update DB name field
- Log: "学生姓名已更新: {old} → {new}"

**Assignment name normalization:**
- Normalizer maps all variants to "作业1"
- Store original name in email_subject field
- Use normalized for grouping

**Empty attachments (0 bytes):**
- Save file anyway (preserves submission intent)
- Mark with flag: has_empty_attachments=true
- Show warning in UI

---

## Testing Strategy

### Unit Tests (pytest)

**DataSyncService:**
- `test_initial_sync_creates_db_records()` - Mock email server, verify DB populated
- `test_incremental_sync_only_fetches_changes()` - Verify only new/changed emails fetched
- `test_sync_handles_network_failure()` - Mock timeout, verify retry logic

**VersionManager:**
- `test_create_first_version_returns_v1()` - First submission gets version 1
- `test_duplicate_submission_gets_v2()` - Second submission increments version
- `test_get_latest_version_skips_old_ones()` - Verify only latest returned

**EmailIndexer:**
- `test_scan_returns_fast_index()` - Verify scan doesn't fetch bodies/attachments
- `test_detect_new_emails()` - Compare indexes, find new UIDs
- `test_detect_deleted_emails()` - Email removed from server, detect change

### Integration Tests

**End-to-end email processing:**
- Mock email in INBOX → Run workflow → Verify v1 folder, DB record, email moved
- Duplicate submission → Verify v2 created, DB updated, v1 preserved
- Network failure → Verify temp folder cleaned, error logged, retry scheduled

### Manual Testing Scenarios

**Fresh Startup:**
1. Clear DB cache
2. Launch application
3. Verify: UI shows empty state immediately
4. Wait 2-3s
5. Verify: UI populates with TARGET_FOLDER data

**Offline Mode:**
1. Load application with cached data
2. Disconnect network
3. Click "刷新数据"
4. Verify: Shows error toast, cached data still visible
5. Reconnect network
6. Verify: Background sync resumes, UI updates

**Concurrent Updates:**
1. Open two application instances (same DB)
2. Instance A: Process new email
3. Instance B: Click refresh
4. Verify: Both show consistent data, no race conditions

### Performance Tests

**Startup time:**
- Target: UI visible in <100ms with cached data
- Test: Launch app 100 times, measure time to first render

**Sync performance:**
- Target: 100 emails synced in <5s
- Test: Mock 100 emails, measure sync duration

**Memory usage:**
- Target: <500MB for 10,000 submissions
- Test: Load large dataset, monitor memory

---

## Migration Strategy

### Existing Data Migration

**Steps:**

1. Create new DB schema:
```sql
ALTER TABLE submissions ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE submissions ADD COLUMN is_latest BOOLEAN DEFAULT TRUE;
CREATE INDEX idx_submissions_version ON submissions(version);
CREATE INDEX idx_submissions_latest ON submissions(is_latest);
```

2. Run migration script:
```python
def migrate_existing_submissions():
    """Migrate flat folder structure to versioned structure"""
    for assignment_dir in submissions_root.iterdir():
        for student_dir in assignment_dir.iterdir():
            # Rename: submissions/作业1/2021001张三/
            #      → submissions/作业1/2021001张三/v1/
            old_path = student_dir
            new_path = student_dir / "v1"
            old_path.rename(new_path)

            # Update DB: set version=1, is_latest=True
            db.update_submission_version(
                student_id, assignment_name,
                version=1, is_latest=True
            )
```

3. Verify all files migrated
4. Backup old data (keep `_old/` folder, don't delete)

**Rollback Plan:**
```
If new version has critical bugs:
1. Restore _old/ folders
2. Revert DB schema (remove version, is_latest columns)
3. Deploy previous version
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- Create DataSyncService skeleton
- Create VersionManager
- Create EmailIndexer
- Add DB schema changes (version, is_latest columns)

### Phase 2: Core Functionality (Week 2)
- Implement version folder creation
- Implement duplicate detection with versioning
- Implement background sync (initial + incremental)
- Add retry logic for failed operations

### Phase 3: UI Integration (Week 3)
- Refactor MainWindow to use DataSyncService
- Add event-driven UI updates
- Add sync status indicator
- Add version history viewer (optional)

### Phase 4: Testing & Migration (Week 4)
- Write unit tests
- Write integration tests
- Create migration script
- Test migration on staging data
- Performance testing

### Phase 5: Deployment (Week 5)
- Deploy to production
- Monitor for issues
- Rollback plan if needed

---

## Success Criteria

**Functional:**
- ✅ All 6 failure scenarios fixed (A, B, C, D, E, F)
- ✅ No data loss (all versions preserved)
- ✅ No duplicate records in UI
- ✅ Network failures handled gracefully

**Performance:**
- ✅ UI startup <100ms (cached data)
- ✅ Background sync completes in 2-5s for 100 emails
- ✅ Manual refresh returns immediately, updates asynchronously

**Reliability:**
- ✅ Failed operations auto-retry with exponential backoff
- ✅ Concurrent access doesn't corrupt data
- ✅ Can recover from partial state (transactional operations)

**Maintainability:**
- ✅ Clear separation of concerns (3-layer architecture)
- ✅ Email is single source of truth
- ✅ Easy to test in isolation (mock email server)

---

## Open Questions

None at this time. Design approved and ready for implementation planning.
