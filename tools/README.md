# Tools

Put deterministic execution scripts here: API calls, data transforms, exports, validations, and file operations.

Guidelines:

- Prefer small scripts with clear inputs and outputs.
- Load local configuration from `.env` only.
- Write disposable intermediates to `.tmp/`.
- Print useful status and fail with actionable error messages.
- Keep paid or rate-limited API calls explicit in workflow instructions.

Shared path helpers live in `_common.py`.

