# Database Persistence Directory (`db/`)

This directory houses the localized SQLite relational database file for the **Restaurant Billing System [Q04: Improve Security]**.

---

## 🗄️ Database File Details
- **Primary Database File:** `restaurant_pos.db` (created automatically upon application launch or migration)
- **WAL Journaling Files:**
  - `restaurant_pos.db-wal` (Write-Ahead Log for high-concurrency ACID transactions)
  - `restaurant_pos.db-shm` (Shared-memory index for WAL mode)

---

## 🔒 Security & Git Hygiene
- Binary SQLite database files (`*.db`, `*.db-wal`, `*.db-shm`) contain operational runtime state and encrypted customer data; therefore, they are **strictly excluded from Git tracking** via `.gitignore`.
- DDL schema definitions and initial seed scripts are version-controlled inside the [`schema/`](file:///d:/COURSES/TQM-project/schema/) directory.

---

## 🔄 Backup & Recovery
- The database uses standard SQLite file-level durability.
- To take a manual backup, ensure the application is closed or execute SQLite's online backup API to copy `restaurant_pos.db` to a secure archival location.
