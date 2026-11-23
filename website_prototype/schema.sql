CREATE DATABASE IF NOT EXISTS trip_events CHARACTER SET utf8mb4;
USE trip_events;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NULL UNIQUE, -- NULL for a guest account (see password_hash)
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NULL, -- NULL means this is a guest account: a placeholder a host created for
                                      -- someone without a login (e.g. backfilling an old trip's attendance
                                      -- sheet) via the "+" next to a trip's Guest list. Can't log in; otherwise
                                      -- a full participant everywhere (contributions, fee-splitting, etc).
    salt VARCHAR(64) NULL,
    profile_picture_url VARCHAR(512) NULL,
    is_admin TINYINT(1) NOT NULL DEFAULT 0,
    is_treasurer TINYINT(1) NOT NULL DEFAULT 0,
    is_assessor TINYINT(1) NOT NULL DEFAULT 0, -- can check off members' skills, see user_skills below
    skill_notes TEXT NULL, -- free-text notes an assessor keeps on this member's skills page
    membership_expiry DATE NULL, -- NULL means not a current NUCC member (can still sign up/log in); set by the ANU Sport sync
    anusportid VARCHAR(32) NULL UNIQUE, -- u<student id> or a<ANU Sport UserId>, used to re-match this account on future syncs
    bank_name_aliases VARCHAR(255) NULL, -- comma-separated name(s) this person appears as in bank transaction descriptions, used to auto-match imported transactions to them
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Site-wide settings; a single row (id=1) holding things admins can change,
-- such as the banner image shown on the events page and the formula used to
-- price driven_distance contributions (a small expression over the variable
-- `km`, see formula.py).
CREATE TABLE site_settings (
    id INT PRIMARY KEY,
    banner_url VARCHAR(512) NULL,
    distance_formula VARCHAR(255) NULL,
    anusport_sync_enabled TINYINT(1) NOT NULL DEFAULT 0, -- whether the background daemon polls ANU Sport
    anusport_sync_minutes INT NOT NULL DEFAULT 1440, -- interval between automatic syncs (default: daily)
    anusport_sync_next_at DATETIME NULL, -- when the daemon should next run; updated after every run
    anusport_sync_last_run_at DATETIME NULL,
    anusport_sync_last_summary TEXT NULL, -- short human-readable result of the last run, shown on /admin/anusport-sync
    anusport_sync_send_emails TINYINT(1) NOT NULL DEFAULT 0 -- whether the automatic (background) sync sends renewal/welcome emails
);
INSERT INTO site_settings (id, banner_url, distance_formula) VALUES (1, '/static/banner.jpg', 'km * 0.88');

CREATE TABLE sessions (
    token VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Self-service "forgot password" tokens (also doubles as the way to claim a
-- passwordless account created by the ANU Sport sync or "+ add guest" --
-- setting a password via a valid token works the same regardless of
-- whether the account already had one). One-time use: deleted once consumed.
CREATE TABLE password_resets (
    token VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    host_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    picture_url VARCHAR(512),
    date_start DATETIME NOT NULL,
    date_end DATETIME NOT NULL,
    location VARCHAR(255) NOT NULL,
    location_label VARCHAR(255) NULL,
    signup_mode ENUM('fcfs','host_picks') NOT NULL DEFAULT 'fcfs',
    participant_limit INT NULL,
    distance_formula VARCHAR(255) NULL, -- overrides site_settings.distance_formula for this event; NULL = use the global default
    lodged_at DATETIME NULL, -- host-set via the "Lodge" button on the Contributions page: once set, this
                              -- trip's fees count toward the club-wide Member balances rollup (see
                              -- event_fee_lodgements below), via a snapshot rather than a live recomputation
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (host_id) REFERENCES users(id)
);

CREATE TABLE event_signups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_event_user (event_id, user_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE discussion_posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Club-wide catalog of required skills/items a trip leader can pick from
-- when building their trip's checklist (see event_checklist_items), managed
-- by an admin -- e.g. skill "Vertical sign-off", item "Wetsuit".
-- Admin-editable reference pages, written in Markdown (see markdown.py) and
-- rendered to HTML for viewing, e.g. the club's skill-levels writeup linked
-- from a trip's "Required skills & items".
CREATE TABLE content_pages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    content_markdown LONGTEXT NOT NULL,
    show_in_nav TINYINT(1) NOT NULL DEFAULT 0, -- whether this page gets a link in the site header
    nav_label VARCHAR(100) NULL, -- link text when show_in_nav is set; falls back to title if blank
    nav_order INT NOT NULL DEFAULT 0, -- header links are ordered by this, then title
    visible_roles VARCHAR(255) NULL, -- comma-separated subset of anonymous/member/admin/treasurer/assessor;
                                      -- NULL or empty means visible to everyone (the default, unrestricted)
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE checklist_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    kind ENUM('skill','item') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name_kind (name, kind)
);

-- Which catalog entries a given trip requires -- the host picks from
-- checklist_items to build their trip's "Required skills & items" section.
CREATE TABLE event_checklist_items (
    event_id INT NOT NULL,
    checklist_item_id INT NOT NULL,
    PRIMARY KEY (event_id, checklist_item_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE
);

-- A member's acquired skills (checklist_items of kind 'skill'), checked off
-- by an assessor (a user with is_assessor set, or an admin) on the user's
-- skills page -- see handle_user_skills_page. Recorded who signed it off
-- and when; unchecking a skill just deletes the row.
CREATE TABLE user_skills (
    user_id INT NOT NULL,
    checklist_item_id INT NOT NULL,
    assessor_id INT NOT NULL,
    assessed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, checklist_item_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE,
    FOREIGN KEY (assessor_id) REFERENCES users(id)
);

-- A trip's lodged fees, as an auditable ledger rather than a live number:
-- "Lodge" (once, per trip) inserts one row per member with their owed
-- amount at that moment. If contributions/gear use change afterwards,
-- "Amend" inserts a reversal row (negating the previously lodged total)
-- plus a new row with the current amount, for each member whose amount
-- changed -- so the club-wide Member balances history (see
-- handle_accounting_user_balance_page) shows the correction rather than
-- silently updating a number. A member's lodged total for a trip is
-- SUM(amount) over their rows for that event.
CREATE TABLE event_fee_lodgements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Club-wide gear types and their default per-person rate (e.g. "Horizontal
-- Gear": $5), managed by an admin. A new event snapshots these into
-- event_gear_rates at creation time, which a host can then override per
-- event -- later changes here don't retroactively change existing trips.
CREATE TABLE gear_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    rate DECIMAL(10,2) NOT NULL,
    description VARCHAR(512) NULL, -- when to charge this, shown as a hint when logging gear use
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Per-event effective gear rates, seeded from gear_types when the event is
-- created; a host can edit their event's row to override the club default.
CREATE TABLE event_gear_rates (
    event_id INT NOT NULL,
    gear_type_id INT NOT NULL,
    rate DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (event_id, gear_type_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (gear_type_id) REFERENCES gear_types(id) ON DELETE CASCADE
);
INSERT INTO gear_types (name, rate, description) VALUES
    ('Horizontal Gear', 5.00, 'Any members hired club horizontal gear (helmets, headtorches, etc.).'),
    ('Camping Gear', 10.00, 'Any members hired club camping gear (e.g. sleeping bag, mat, stove, etc.).'),
    ('SRT Kit', 5.00, 'The club''s SRT kit was used on the trip.');

-- A contribution is either a plain expense (amount entered directly) or a
-- driven_distance entry (km entered, dollar amount derived from the per-km
-- rate at the time it was recorded).
-- contributor_id is NULL for a contribution made on behalf of someone who
-- isn't a registered user (e.g. importing a past trip's paper attendance
-- sheet); contributor_name holds their plain name in that case. It's also
-- NULL for a gear-use fee (gear_type_id set): nobody "paid" that money to
-- the club, it's just a direct charge to whoever's in contribution_consumers.
CREATE TABLE contributions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    contributor_id INT NULL,
    contributor_name VARCHAR(255) NULL,
    type ENUM('expense','driven_distance') NOT NULL DEFAULT 'expense',
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    km DECIMAL(10,2) NULL,
    rate_per_km DECIMAL(6,3) NULL,
    gear_type_id INT NULL, -- set when this row is a gear-use fee rather than a regular contribution; see gear_types
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (contributor_id) REFERENCES users(id),
    FOREIGN KEY (gear_type_id) REFERENCES gear_types(id) ON DELETE SET NULL
);

-- Club income/expenses not tied to a member or a trip (gear purchases,
-- external funding/grants, etc). Logged manually by the treasurer; a bank
-- transaction can optionally be linked to one via
-- bank_transactions.ledger_entry_id to show it's been recognised/accounted
-- for, separately from the per-member reconciliation.
CREATE TABLE ledger_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entry_date DATE NOT NULL,
    description VARCHAR(512) NOT NULL,
    amount DECIMAL(10,2) NOT NULL, -- always positive: what the club owes to reimburse the assigned member
    external_link VARCHAR(1024) NULL,
    image_url VARCHAR(512) NULL,
    user_id INT NULL, -- the member this entry should reconcile against (e.g. who bought the gear and is owed back)
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- The club bank account's raw transaction history, imported from the bank's
-- CSV export. Each transaction is linked to the member it belongs to (not
-- to a specific trip) -- reconciliation is per-member, pooled across all
-- their trips, not per-transaction-per-trip. See accounting.py and the
-- Member balances page.
CREATE TABLE bank_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    txn_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    description VARCHAR(512) NOT NULL,
    user_id INT NULL, -- auto-matched (or manually set) from the name in the description, via users.bank_name_aliases
    ledger_entry_id INT NULL, -- alternative to user_id: this transaction is a non-member item (gear, external funding, etc), see ledger_entries
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_txn (txn_date, amount, description(255)),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (ledger_entry_id) REFERENCES ledger_entries(id) ON DELETE SET NULL
);

-- Who a contribution's cost is charged to, if not split across everyone.
-- No rows for a contribution means its cost is pooled and shared evenly
-- across all approved participants of the event.
CREATE TABLE contribution_consumers (
    contribution_id INT NOT NULL,
    user_id INT NOT NULL,
    PRIMARY KEY (contribution_id, user_id),
    FOREIGN KEY (contribution_id) REFERENCES contributions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
