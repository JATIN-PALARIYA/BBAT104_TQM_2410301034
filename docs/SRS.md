# Software Requirements Specification (SRS)
## Restaurant Billing System — [Q04: Improve Security]
**Course:** BBAT104 — Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026–27  
**Student Name:** Jatin Palariya (`2410301034`)  
**Assigned Topic:** Restaurant Billing System (Digit 4) | **Quality Goal:** Q04 — Improve Security  
**Institution:** Amrapali Institute of Technology & Sciences, Haldwani  
**Standard:** IEEE-830 Recommended Practice for Software Requirements Specifications  

---

## 1. Scope & System Boundaries

```mermaid
graph TD
    classDef inScope fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef outScope fill:#991b1b,stroke:#f87171,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef root fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:13px;

    Scope["<b>SYSTEM BOUNDARY ANALYSIS (IEEE-830)</b>"]:::root

    subgraph IN ["<b>IN-SCOPE CAPABILITIES (Active Development)</b>"]
        IN1["<b>Core POS Billing</b><br/>• Menu catalog CRUD & category search<br/>• Dynamic cart & live tax calculation<br/>• Atomic invoice generation & receipt text"]:::inScope
        IN2["<b>5 Assigned Q04 Security Modules</b><br/>• Role-Based Access Control (Admin/Cashier)<br/>• Master Key & Staff Password Reset<br/>• Poka-Yoke error-proofing boundary guards<br/>• Tamper-evident SHA-256 audit hash chain<br/>• Salted PBKDF2 & AES phone encryption"]:::inScope
        IN3["<b>TQM Analytics & Local DB</b><br/>• Standalone SQLite persistence (WAL mode)<br/>• Automated Pareto (80/20) & Fishbone diagrams"]:::inScope
    end

    subgraph OUT ["<b>OUT-OF-SCOPE EXCLUSIONS (Scope Control)</b>"]
        OUT1["<b>Enterprise Infrastructure Excluded</b><br/>• Multi-branch cloud WAN synchronization<br/>• Kitchen Display System (KDS) routing<br/>• Raw inventory & supply chain tracking<br/>• Hardware EDC swipers & biometric readers<br/>• External SMS/Email OTP internet APIs"]:::outScope
    end

    Scope --> IN
    Scope --> OUT
```

---

## 2. Product Architecture & Layered Design

```mermaid
graph TD
    classDef uiStyle fill:#0284c7,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef secStyle fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef appStyle fill:#b45309,stroke:#fbbf24,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef dbStyle fill:#0f172a,stroke:#64748b,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;

    UI["<b>1. Presentation Layer (Desktop GUI)</b><br/>CustomTkinter / Tkinter Responsive Viewports"]:::uiStyle
    SEC["<b>2. Security & Poka-Yoke Layer (Q04 Middleware)</b><br/>RBAC Session Guard • Input Validator • PBKDF2/AES Crypto Engine"]:::secStyle
    APP["<b>3. Business Logic Layer (POS Engine)</b><br/>Menu CRUD • Dynamic Cart • 5% GST Math • Audit Event Dispatcher"]:::appStyle
    DB[("<b>4. Persistence Layer (SQLite Relational DB)</b><br/>ACID Transactions • Foreign Keys • Hash-Chained Audit Logs")]:::dbStyle

    UI <--> SEC
    SEC <--> APP
    APP <--> DB
```

---

## 3. Order Processing & Billing Computation Pipeline

```mermaid
flowchart LR
    classDef step fill:#0284c7,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef math fill:#b45309,stroke:#fbbf24,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef secure fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;

    S1["<b>1. Cart Entry</b><br/>Select Item & Quantity"]:::step
    S2["<b>2. Poka-Yoke Guard</b><br/>Qty > 0 & Price > 0"]:::secure
    S3["<b>3. Math Pipeline</b><br/>Subtotal = Σ(Qty × Price)<br/>Taxable = Subtotal - Disc (≤20%)<br/>GST = Taxable × 5%<br/>Total = Taxable + GST"]:::math
    S4["<b>4. Finalization</b><br/>Atomic SQLite Commit<br/>BILL-YYYYMMDD-XXXX<br/>Receipt HMAC Checksum"]:::secure

    S1 --> S2 --> S3 --> S4
```

---

## 4. Security Architecture & 5 Assigned Q04 Features

```mermaid
graph TD
    classDef secCore fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:13px;
    classDef feature fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;

    SEC["<b>Q04: IMPROVE SECURITY — 5 CORE MODULES</b>"]:::secCore

    SEC --> F1["<b>Feature 1: Role-Based Access Control</b><br/>• Admin vs. Cashier session isolation<br/>• Controller-level privilege guards<br/>• 5-attempt brute-force lockout (60s)"]:::feature

    SEC --> F2["<b>Feature 2: Password Reset Protocol</b><br/>• Offline Master Recovery Key for Admin<br/>• Staff reset with forced change flag<br/>• 8+ chars complexity policy"]:::feature

    SEC --> F3["<b>Feature 3: Poka-Yoke Input Error Proofing</b><br/>• Rejection of negative price/quantity<br/>• Strict discount boundary (0% to 20%)<br/>• Parameterized SQL injection immunity"]:::feature

    SEC --> F4["<b>Feature 4: Tamper-Evident Audit Trail</b><br/>• Automatic logging of logins, bills, voids<br/>• Cryptographic SHA-256 hash chaining<br/>• Admin chain integrity verification tool"]:::feature

    SEC --> F5["<b>Feature 5: Cryptographic Data Protection</b><br/>• Salted PBKDF2-SHA256 password hashing<br/>• AES-256 encryption of customer phone<br/>• HMAC receipt digital verification checksum"]:::feature
```

---

## 5. Functional Requirements (IEEE-830 Specifications)

### 5.1 Baseline POS Modules
| Req ID | Module | Functional Description | Acceptance Rule |
| :--- | :--- | :--- | :--- |
| **FR-01** | **Menu Catalog CRUD** | Add, edit, search, and deactivate menu items across categories (Starters, Main, Beverages, Desserts). | Soft deactivation toggles `is_active=0`; hard delete is blocked if sales exist. |
| **FR-02** | **Dynamic Order Cart** | Add items, increment/decrement quantities, remove line items, and clear cart. | Cart quantity must be strictly positive; real-time recalculation of all figures. |
| **FR-03** | **Live Billing Math** | Compute Line Totals, Subtotal, Bounded Discounts (0–20%), 5% GST, and Grand Total. | Zero rounding discrepancies; calculations match unit benchmark values. |
| **FR-04** | **Invoicing & History** | Finalize bill with unique ID (`BILL-YYYYMMDD-XXXX`), print receipt text, and view sales history. | Atomic multi-table write (`bills` & `bill_items`) with rollback protection. |

### 5.2 Q04 Security Modules
| Req ID | Security Feature | Technical Specification | Security Rule |
| :--- | :--- | :--- | :--- |
| **SEC-01** | **Role-Based Login** | Authenticate users against salted hashes; assign `Admin` or `Cashier` session privileges. | 0% cashier access to menu edits, user resets, audit logs, or bill voids. |
| **SEC-02** | **Brute-Force Defense** | Track consecutive invalid attempts; trigger temporary account lock. | Account locks for 60 seconds upon exactly 5 consecutive failed logins. |
| **SEC-03** | **Password Reset** | Offline Master Recovery Key for Admin; Admin-managed staff reset. | Staff reset flags `must_change_password=1`, forcing immediate password change. |
| **SEC-04** | **Poka-Yoke Bounds** | Boundary validation intercepting illegal quantities, negative prices, and bad formats. | Reject $Qty \le 0$, $Price \le 0.00$, and discount $> 20\%$ with modal alert. |
| **SEC-05** | **Audit Hash Chain** | Append-only event capture linked via SHA-256: $H_n = \text{SHA256}(H_{n-1} \parallel R_n)$. | Any row tampering or out-of-band deletion breaks the cryptographic chain. |
| **SEC-06** | **Credential Storage** | Derived key storage using PBKDF2-HMAC-SHA256 with 16-byte random salt. | 100,000 iterations; zero plaintext passwords in database or memory dumps. |
| **SEC-07** | **Phone Data Encryption** | Optional customer phone numbers encrypted symmetrically at rest via AES (Fernet). | Ciphertext stored in SQLite; decrypted only upon authorized invoice view. |
| **SEC-08** | **Receipt Checksum** | Digital signature calculated over Bill ID, timestamp, and grand total. | HMAC-SHA256 signature guarantees receipt cannot be altered or falsified. |

---

## 6. Non-Functional Requirements (NFR)

```mermaid
graph LR
    classDef nfr fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;

    NFR["<b>NON-FUNCTIONAL REQUIREMENTS</b>"]:::nfr

    NFR --> N1["<b>NFR-01: Security</b><br/>• Zero plaintext secrets<br/>• 100% Parameterized queries<br/>• Role isolation at controller layer"]:::nfr
    NFR --> N2["<b>NFR-02: Performance</b><br/>• GUI launch time < 2.0s<br/>• Checkout latency < 300ms<br/>• DB query time < 50ms"]:::nfr
    NFR --> N3["<b>NFR-03: Reliability</b><br/>• ACID transaction safety<br/>• WAL SQLite journaling<br/>• Foreign key enforcement"]:::nfr
    NFR --> N4["<b>NFR-04: Usability</b><br/>• Modal confirmation dialogs<br/>• High-contrast accessible UI<br/>• Keyboard checkout shortcuts"]:::nfr
```

---

## 7. Review 1 Acceptance Baseline

This specification serves as the formal baseline submitted for academic evaluation under Review 1:
1. Complete alignment with BBAT104 course guidelines and project allotment (Digit 4 / Q04).
2. Full functional coverage of baseline Restaurant Billing System and all 5 Q04 Security Features.
3. Architecture, scope definitions, and database models fully synchronized with this requirements specification.
