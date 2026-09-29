# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
-   User-specific project isolation via `user_id` cookies when `HOSTING=true`.
-   100MB file size limit enforcement for video uploads in hosting mode.
-   Automatic deletion of projects older than 30 days via background cleanup task.
-   `HOSTING` environment variable to toggle multi-tenant features.
-   Added `run.bat` for easy Windows execution with auto-setup and pause on exit.
-   Added `README.md` with project setup instructions.
