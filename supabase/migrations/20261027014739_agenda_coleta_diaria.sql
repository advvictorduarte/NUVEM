create extension if not exists pg_cron;

-- 12:00 UTC = 09:00 em Brasilia (sem horario de verao desde 2019).
select cron.schedule(
  'coleta-djen-diaria',
  '0 12 * * *',
  $$select coletar_monitoramentos();$$
);
