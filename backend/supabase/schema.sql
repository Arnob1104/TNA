-- Run this in the Supabase SQL editor (or `supabase db push`).
-- Sets up tables for the Merch Ops SaaS: tenants, orders, TNA calendar,
-- assessments, human-in-the-loop threads, and notifications.

create extension if not exists "uuid-ossp";

-- One row per customer company.
create table tenants (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  created_at timestamptz not null default now()
);

-- Maps a Supabase auth user to a tenant. Populated by a trigger or by
-- your signup flow right after supabase.auth.signUp().
create table profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

create table orders (
  tenant_id uuid not null references tenants(id) on delete cascade,
  order_ref text not null,
  style text,
  quantity integer,
  ship_date timestamptz,
  status text default 'In Progress',
  created_at timestamptz not null default now(),
  primary key (tenant_id, order_ref)
);

create table tna_calendar (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  order_ref text not null,
  task_name text not null,
  deadline timestamptz not null,
  status text not null default 'Pending',   -- 'Pending' | 'Complete'
  foreign key (tenant_id, order_ref) references orders(tenant_id, order_ref) on delete cascade
);

-- One row per Order Status Agent run.
create table assessments (
  job_id uuid primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  order_ref text not null,
  is_at_risk boolean,
  summary text,
  status text not null default 'queued',    -- 'queued' | 'done' | 'error'
  assessed_at timestamptz not null default now()
);

-- Tracks paused TNA Watcher threads awaiting human approval.
create table tna_threads (
  thread_id text primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  status text not null default 'pending',   -- 'pending' | 'approved' | 'rejected'
  created_at timestamptz not null default now()
);

create table notifications (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  message text not null,
  kind text not null,
  read boolean not null default false,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Row Level Security: belt-and-suspenders alongside the FastAPI
-- tenant_id filtering. Even if a query forgot a WHERE clause, RLS
-- stops cross-tenant reads at the database level.
-- ---------------------------------------------------------------------

alter table orders enable row level security;
alter table tna_calendar enable row level security;
alter table assessments enable row level security;
alter table tna_threads enable row level security;
alter table notifications enable row level security;

create policy tenant_isolation_orders on orders
  using (tenant_id = (select tenant_id from profiles where user_id = auth.uid()));

create policy tenant_isolation_tna on tna_calendar
  using (tenant_id = (select tenant_id from profiles where user_id = auth.uid()));

create policy tenant_isolation_assessments on assessments
  using (tenant_id = (select tenant_id from profiles where user_id = auth.uid()));

create policy tenant_isolation_threads on tna_threads
  using (tenant_id = (select tenant_id from profiles where user_id = auth.uid()));

create policy tenant_isolation_notifications on notifications
  using (tenant_id = (select tenant_id from profiles where user_id = auth.uid()));

-- Note: the FastAPI backend connects with the Postgres service-role
-- connection string, which bypasses RLS by design (it enforces
-- tenant_id in application code instead). RLS here protects any
-- direct-from-frontend Supabase client calls you add later.
