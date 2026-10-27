-- Tabela `monitoramentos` conforme a secao 6 do SPEC.md: a OAB nao fica
-- escrita no codigo nem no agendamento.
create table if not exists monitoramentos (
  id               bigserial primary key,
  tipo             text not null default 'OAB' check (tipo in ('OAB', 'CNJ')),
  numero_oab       text,
  uf_oab           text,
  numero_cnj       text,
  descricao        text,
  ativo            boolean not null default true,
  ultima_execucao  timestamptz,
  criado_em        timestamptz not null default now(),
  constraint monitoramento_oab_completo
    check (tipo <> 'OAB' or (numero_oab is not null and uf_oab is not null)),
  constraint monitoramento_cnj_completo
    check (tipo <> 'CNJ' or numero_cnj is not null)
);

create unique index if not exists monitoramentos_oab_unico
  on monitoramentos (numero_oab, uf_oab) where tipo = 'OAB';

alter table monitoramentos enable row level security;

create or replace function coletar_monitoramentos()
returns setof execucoes_coleta
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  m          monitoramentos;
  v_execucao execucoes_coleta;
begin
  for m in select * from monitoramentos where ativo and tipo = 'OAB' loop
    v_execucao := coletar_djen(m.numero_oab, m.uf_oab);
    update monitoramentos set ultima_execucao = now() where id = m.id;
    return next v_execucao;
  end loop;
end;
$$;

comment on function coletar_monitoramentos is
  'Chamada pelo agendamento diario. Percorre as OABs ativas em monitoramentos.';
