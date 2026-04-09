# Issue: Add Safe Rollback Mechanism for `retrofit` Command

## Description
The `agent-gen retrofit` command currently performs in-place migrations of directories and files using `shutil.move`. 

## Gap Analysis
If an error occurs midway through the migration (e.g., file permission denied, disk full, unexpected file lock), the user's original agent directory is left in a broken, partially migrated state with no automated way to recover it.

## Proposed Solution
- Modify the `migrate()` method in `librarian.py` to work safely.
- **Approach**: Copy the source directory to a temporary staging area, perform the structural migration there, and only swap/overwrite the original directory if the entire process succeeds.

## Acceptance Criteria
- [ ] `retrofit` operates on a staging directory.
- [ ] Failed migrations leave the original directory untouched.
- [ ] Temporary directories are cleaned up after success or failure.