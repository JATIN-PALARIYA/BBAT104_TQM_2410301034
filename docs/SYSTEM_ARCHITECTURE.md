# System Architecture & Flowchart
## Restaurant Billing System — [Q04: Improve Security]
**Course:** BBAT104 — Fundamentals of TQM | **Session:** 2026–27  
**Student Name:** Jatin Palariya (`2410301034`)  
**Assigned Topic:** Restaurant Billing System (Digit 4) | **Quality Goal:** Q04 — Improve Security  
**Institution:** Amrapali Institute of Technology & Sciences, Haldwani  

---

## 1. Professional 3-Tier System Architecture

The software architecture follows an industry-standard 3-Tier model ensuring loose coupling, high cohesion, and strict privilege isolation:

```mermaid
graph TB
    classDef presTier fill:#1e3a8a,stroke:#60a5fa,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef logicTier fill:#065f46,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef dbTier fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef comp fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc,font-size:11px;

    subgraph T1 ["<b>TIER 1: PRESENTATION LAYER (USER INTERFACE)</b>"]
        C1["<b>Cashier POS Terminal</b><br/>Item Search & Live Cart"]:::comp
        C2["<b>Admin Control Dashboard</b><br/>Menu Catalog & Staff Resets"]:::comp
        C3["<b>Security Views</b><br/>Login, Audit & Receipts"]:::comp
    end

    subgraph T2 ["<b>TIER 2: APPLICATION & Q04 SECURITY ENGINE</b>"]
        L1["<b>Access Control Guard</b><br/>RBAC Session & Lockout"]:::comp
        L2["<b>Poka-Yoke Validator</b><br/>Bounds Check & Sanitizer"]:::comp
        L3["<b>POS Billing Pipeline</b><br/>Cart Math & 5% GST Engine"]:::comp
        L4["<b>Cryptographic Services</b><br/>PBKDF2, AES-256 & HMAC"]:::comp
        L5["<b>Audit Event Dispatcher</b><br/>SHA-256 Hash Chainer"]:::comp
    end

    subgraph T3 ["<b>TIER 3: PERSISTENCE LAYER (SQLITE RELATIONAL DB)</b>"]
        D1["<b>users</b><br/>Salted Credentials & Roles"]:::comp
        D2["<b>menu_items</b><br/>Catalog & Categories"]:::comp
        D3["<b>bills & bill_items</b><br/>Invoices & Tax Breakdown"]:::comp
        D4["<b>audit_logs</b><br/>Cryptographic Hash Chain"]:::comp
    end

    C1 --> L2
    C1 --> L3
    C2 --> L1
    C2 --> L2
    C3 --> L1
    C3 --> L5

    L1 --> L4
    L2 --> L3
    L3 --> L5

    L1 --> D1
    L2 --> D2
    L3 --> D3
    L5 --> D4
```

---

## 2. High-Level Process Flowchart

```mermaid
flowchart TD
    classDef startStyle fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef procStyle fill:#0284c7,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef condStyle fill:#b45309,stroke:#fbbf24,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:11px;
    classDef secStyle fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;

    Start(["<b>Start Application</b>"]):::startStyle --> Login["<b>User Login View</b>"]:::procStyle
    Login --> AuthCheck{"<b>PBKDF2 Auth & Role?</b>"}:::condStyle

    AuthCheck -- Failed / 5 Tries --> Lockout["<b>Account Lockout Alert (60s)</b>"]:::condStyle --> Login

    AuthCheck -- Cashier Role --> CashierFlow["<b>Cashier POS Counter</b>"]:::procStyle
    CashierFlow --> OrderItem["<b>Select Items & Add to Cart</b>"]:::procStyle
    OrderItem --> PokaYoke{"<b>Poka-Yoke Valid? (Qty &gt; 0, Price &gt; 0)</b>"}:::condStyle
    PokaYoke -- Invalid --> BoundsAlert["<b>Input Error Dialog</b>"]:::condStyle --> OrderItem
    PokaYoke -- Valid --> CalcTotal["<b>Compute Subtotal, 5% GST & Total</b>"]:::procStyle
    CalcTotal --> ConfirmBill["<b>Confirm Checkout & Print Receipt</b>"]:::secStyle
    ConfirmBill --> LogBill["<b>Atomic DB Commit & SHA-256 Audit Log</b>"]:::secStyle --> EndLoop(["<b>Ready for Next Order</b>"]):::startStyle

    AuthCheck -- Admin Role --> AdminFlow["<b>Admin Management Panel</b>"]:::procStyle
    AdminFlow --> AdminAction{"<b>Select Administrative Action</b>"}:::condStyle
    AdminAction -- Menu CRUD --> MenuUpdate["<b>Add / Edit / Deactivate Menu Items</b>"]:::procStyle
    AdminAction -- Password Reset --> StaffReset["<b>Reset Staff Password (Forced Change)</b>"]:::procStyle
    AdminAction -- Bill Voiding --> VoidBill["<b>Void Bill (Mandatory Reason)</b>"]:::procStyle
    AdminAction -- Audit Review --> VerifyAudit["<b>Walk & Verify SHA-256 Hash Chain</b>"]:::secStyle

    MenuUpdate --> LogAdminAction["<b>Append Event to Audit Hash Chain</b>"]:::secStyle
    StaffReset --> LogAdminAction
    VoidBill --> LogAdminAction
    LogAdminAction --> AdminFlow
```

---

## 3. Data Flow Diagrams (DFD)

### 3.1 DFD Level 0: Context Diagram
```mermaid
flowchart LR
    classDef entity fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef system fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:13px;

    Customer["<b>Dining Customer</b>"]:::entity
    Cashier["<b>Cashier Staff</b>"]:::entity
    Admin["<b>Administrator</b>"]:::entity
    System["<b>Restaurant Billing System<br/>(Q04 Security POS)</b>"]:::system

    Cashier -->|Login, Orders, Payments| System
    System -->|Receipts, Shift Totals| Cashier
    System -->|Itemized Tax Invoice| Customer
    Customer -->|Food Order, Payment| Cashier
    Admin -->|Menu Edits, Staff Resets, Void Orders| System
    System -->|Audit Logs, Hash Integrity Status| Admin
```

### 3.2 DFD Level 1: Subsystem Processing
```mermaid
flowchart TD
    classDef user fill:#047857,stroke:#34d399,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef proc fill:#0284c7,stroke:#38bdf8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;
    classDef store fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#ffffff,font-weight:bold,font-size:12px;

    Staff["<b>Staff User (Admin / Cashier)</b>"]:::user

    P1["<b>1.0 Authentication & Session Control</b>"]:::proc
    P2["<b>2.0 Menu Catalog Management</b>"]:::proc
    P3["<b>3.0 Order Entry & Cart Calculation</b>"]:::proc
    P4["<b>4.0 Billing & Invoice Finalization</b>"]:::proc
    P5["<b>5.0 Audit Logging & Chain Verification</b>"]:::proc

    D1[("<b>D1: users</b>")]:::store
    D2[("<b>D2: menu_items</b>")]:::store
    D3[("<b>D3: bills & bill_items</b>")]:::store
    D4[("<b>D4: audit_logs</b>")]:::store

    Staff -->|Login Input| P1
    P1 -->|Verify Credentials| D1
    P1 -->|Log Auth Event| P5

    Staff -->|Catalog Updates| P2
    P2 -->|Save Menu Changes| D2
    P2 -->|Log Menu Action| P5

    D2 -->|Feed Active Items| P3
    Staff -->|Order Items & Quantities| P3
    P3 -->|Cart Calculations| Staff

    Staff -->|Confirm Checkout| P4
    P4 -->|Write Invoices & Items| D3
    P4 -->|Generate Receipt| Staff
    P4 -->|Log Billing Event| P5

    P5 -->|Append Hash Chained Log| D4
    D4 -->|Verify Hash Integrity| P5
```

---

## 4. Security Architecture & Threat Mitigation Matrix

| Threat Category | Potential Risk / Attack | Mitigating Architectural Component | Verification Technique |
| :--- | :--- | :--- | :--- |
| **Credential Exposure** | Stolen database file with exposed passwords | PBKDF2-HMAC-SHA256 (100k iterations, 16-byte random salt). | Direct SQLite query confirming zero plaintext credentials. |
| **SQL Injection (SQLi)** | Malicious SQL syntax in search/login inputs (`' OR 1=1;--`) | 100% Parameterized queries (`?` parameter bindings). | Security payload test suite rejected safely. |
| **Privilege Escalation** | Cashier attempting to edit menu prices or void bills | Strict RBAC enforced at GUI controller and DB layers. | Automated role privilege boundary tests. |
| **Input Corruption** | Negative quantities, negative prices, excessive discounts | Poka-Yoke boundary guards ($Qty > 0$, $Price > 0$, $Disc \le 20\%$). | Boundary value input test suite. |
| **Audit Log Tampering** | Rogue actor altering or deleting audit records | Append-only audit table with SHA-256 cryptographic chaining. | Hash-chain verification tool recalculates sequential hashes. |
| **Customer Data Breach** | Unauthorized viewing of patron contact numbers | AES-256 symmetric encryption for optional customer phone numbers. | SQLite inspection confirming ciphertext blob at rest. |
| **Invoice Alteration** | Tampering with stored or reprinted bill amounts | HMAC-SHA256 digital receipt checksum over bill number & total. | Checksum validator flags altered bill figures immediately. |
