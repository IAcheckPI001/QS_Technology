-- Đổi mã model trong doc_chunks sang product_name của CRM
-- (ASTRO_6AH -> 6AH, ASTRO_6AV -> 6AV, ASTRO_10I -> 10iV; bỏ ASTRO_10S).
-- Chạy thủ công trên Supabase (SQL editor), từng bước theo thứ tự.

-- 1. Xem trước: số chunk theo từng mã hiện có ----------------------------------
select m as product_model, count(*) as chunks
from doc_chunks, unnest(product_models) as m
group by m
order by m;

-- 2. Đổi mã (một transaction) --------------------------------------------------
-- Dừng nếu còn chunk gắn ASTRO_10S: model này không có trong CRM, cần quyết định gắn
-- lại hay xoá chunk trước; script không tự xoá tag.
begin;

do $$
declare
  c record;
begin
  if exists (select 1 from doc_chunks where 'ASTRO_10S' = any(product_models)) then
    raise exception 'doc_chunks còn chunk gắn ASTRO_10S; xử lý các chunk này trước khi migrate';
  end if;
  -- Check constraint cũ (tên tự sinh) liệt kê mã ASTRO_*: bỏ trước khi đổi dữ liệu.
  for c in
    select conname from pg_constraint
    where conrelid = 'doc_chunks'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) like '%product_models <@%'
  loop
    execute format('alter table doc_chunks drop constraint %I', c.conname);
  end loop;
end $$;

update doc_chunks
set product_models = (
  select array_agg(
           case m
             when 'ASTRO_6AH' then '6AH'
             when 'ASTRO_6AV' then '6AV'
             when 'ASTRO_10I' then '10iV'
             else m
           end
           order by ord)
  from unnest(product_models) with ordinality as t(m, ord)
)
where product_models && array['ASTRO_6AH','ASTRO_6AV','ASTRO_10I'];

alter table doc_chunks
  add constraint doc_chunks_product_models_check
  check (product_models <@ array['F54','F86','F86E','F10T','6AH','6AHE','6AV','6AVE','10iV','10iVE']);

commit;

-- 3. Kiểm tra lại: không còn mã ASTRO_* -----------------------------------------
select m as product_model, count(*) as chunks
from doc_chunks, unnest(product_models) as m
group by m
order by m;
