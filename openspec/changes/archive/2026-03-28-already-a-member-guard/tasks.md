## 1. Backend — courses.py

- [x] 1.1 In `Course.add_member()`, capture `cursor.rowcount` after the INSERT and return `False` when it is 0 (row already existed), `True` when it is 1 (new row inserted)
- [x] 1.2 Skip the `Course.add_co_creator()` call when `add_member` detects a duplicate (return early)

## 2. Backend — sharing.py

- [x] 2.1 In `do_POST`, check the return value of `Course.add_member()` and return `409 {"error": "User is already a collaborator on this course"}` when it returns `False`

## 3. Verify

- [ ] 3.1 Invite a new collaborator — confirm 200 and member appears in the list
- [ ] 3.2 Invite the same collaborator again — confirm 409 and error message surfaces in the UI

