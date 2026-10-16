-- 在现有 Supabase 项目的 SQL Editor 中执行一次；不会修改知识库表。
-- 公开 Demo 的问答/搜索及天气调用分别共用每日 100 次额度。
-- 日期以北京时间为准；原子更新保证并发请求不会越过上限。

create table if not exists public.demo_daily_usage (
  usage_day date not null,
  scope text not null check (scope in ('query', 'weather')),
  used integer not null default 0 check (used >= 0),
  primary key (usage_day, scope)
);

alter table public.demo_daily_usage enable row level security;
revoke all on public.demo_daily_usage from public, anon, authenticated;

create or replace function public.reserve_demo_quota(p_scope text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  reserved_count integer;
begin
  if p_scope not in ('query', 'weather') then
    raise exception 'invalid demo quota scope';
  end if;

  insert into public.demo_daily_usage (usage_day, scope, used)
  values ((now() at time zone 'Asia/Shanghai')::date, p_scope, 1)
  on conflict (usage_day, scope)
  do update set used = public.demo_daily_usage.used + 1
    where public.demo_daily_usage.used < 100
  returning used into reserved_count;

  return reserved_count is not null;
end;
$$;

revoke all on function public.reserve_demo_quota(text) from public, anon, authenticated;
grant execute on function public.reserve_demo_quota(text) to service_role;
