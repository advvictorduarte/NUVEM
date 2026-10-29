-- Exclusivo do projeto whatsapp-gpt-piloto. Nunca aplicar no monitoramento-prazos.
create schema if not exists privado;
revoke all on schema privado from public, anon, authenticated;
create extension if not exists vector with schema extensions;

create table privado.credenciais (
 finalidade text primary key check(finalidade in ('ingestao','consulta')),
 hash_sha256 text not null check(length(hash_sha256)=64),
 ativo boolean not null default true
);
create table public.grupos (
 instancia text not null, jid text not null check(jid like '%@g.us'),
 nome text not null, autorizado boolean not null default false,
 primary key(instancia,jid)
);
create table public.clientes (id uuid primary key default gen_random_uuid(), nome text not null);
create table public.processos (
 id uuid primary key default gen_random_uuid(), cliente_id uuid references public.clientes,
 numero text, descricao text
);
create table public.grupos_processos (
 instancia text not null, grupo_jid text not null, processo_id uuid references public.processos,
 primary key(instancia,grupo_jid,processo_id),
 foreign key(instancia,grupo_jid) references public.grupos(instancia,jid)
);
create table public.mensagens (
 id uuid primary key default gen_random_uuid(), instancia text not null,
 grupo_jid text not null, mensagem_id text not null, participante text,
 enviada_por_mim boolean not null default false, data_mensagem timestamptz,
 texto text not null default '', tipo text not null, nome_arquivo text,
 mime_type text, midia_status text not null default 'nao_aplicavel'
 check(midia_status in ('nao_aplicavel','pendente','armazenada','indisponivel')),
 caminho_arquivo text, sha256 text, tamanho_bytes bigint,
 midia_tentativas integer not null default 0, midia_proxima timestamptz not null default now(),
 excluida boolean not null default false, origem_evento text not null,
 recebido_em timestamptz not null default now(),
 busca tsvector generated always as (to_tsvector('portuguese',texto)) stored,
 unique(instancia,grupo_jid,mensagem_id),
 foreign key(instancia,grupo_jid) references public.grupos(instancia,jid)
);
create index mensagens_busca on public.mensagens using gin(busca);
create index mensagens_grupo_data on public.mensagens(instancia,grupo_jid,data_mensagem);
create table public.fragmentos (
 id uuid primary key default gen_random_uuid(), mensagem_uuid uuid not null references public.mensagens on delete cascade,
 texto text not null, embedding extensions.vector(1536), modelo text,
 origem text not null check(origem in ('mensagem','pdf','ocr','transcricao')),
 pagina integer, segundo_inicio numeric
);
create table public.eventos (
 hash text primary key, instancia text not null, tipo text not null,
 recebidas integer not null, aceitas integer not null, recebido_em timestamptz not null default now()
);
create table public.auditoria (
 id bigint generated always as identity primary key, acao text not null,
 quantidade integer not null, instante timestamptz not null default now()
);

alter table public.grupos enable row level security;
alter table public.clientes enable row level security;
alter table public.processos enable row level security;
alter table public.grupos_processos enable row level security;
alter table public.mensagens enable row level security;
alter table public.fragmentos enable row level security;
alter table public.eventos enable row level security;
alter table public.auditoria enable row level security;
alter table privado.credenciais enable row level security;
revoke all on public.grupos, public.clientes, public.processos, public.grupos_processos,
 public.mensagens, public.fragmentos, public.eventos, public.auditoria from anon,authenticated;
grant all on public.grupos, public.clientes, public.processos, public.grupos_processos,
 public.mensagens, public.fragmentos, public.eventos, public.auditoria to service_role;
grant usage,select on sequence public.auditoria_id_seq to service_role;

-- Única função com elevação: guarda hashes fora da API, executável só no backend.
create function public.autorizar_gateway(finalidade_arg text, hash_arg text)
returns boolean language sql stable security definer set search_path=''
as $$ select exists(select 1 from privado.credenciais
 where finalidade=finalidade_arg and hash_sha256=hash_arg and ativo) $$;
revoke all on function public.autorizar_gateway(text,text) from public,anon,authenticated;
grant execute on function public.autorizar_gateway(text,text) to service_role;

create function public.registrar_lote(hash_arg text, instancia_arg text, evento_arg text,
 recebidas_arg integer, registros_arg jsonb)
returns jsonb language plpgsql security invoker set search_path=''
as $$ declare item jsonb; n integer:=0; begin
 if exists(select 1 from public.eventos where hash=hash_arg) then
  return jsonb_build_object('duplicado',true,'aceitas',0);
 end if;
 for item in select * from jsonb_array_elements(registros_arg) loop
  if exists(select 1 from public.grupos where instancia=instancia_arg
   and jid=item->>'grupo_jid' and autorizado) then
   insert into public.mensagens(instancia,grupo_jid,mensagem_id,participante,enviada_por_mim,
    data_mensagem,texto,tipo,nome_arquivo,mime_type,midia_status,origem_evento,excluida)
   values(instancia_arg,item->>'grupo_jid',item->>'mensagem_id',item->>'participante',
    (item->>'enviada_por_mim')::boolean,(item->>'data_mensagem')::timestamptz,
    item->>'texto',item->>'tipo',item->>'nome_arquivo',item->>'mime_type',
    item->>'midia_status',evento_arg,coalesce((item->>'excluida')::boolean,false))
   on conflict(instancia,grupo_jid,mensagem_id) do update set
    texto=case when public.mensagens.excluida or excluded.excluida then '' else excluded.texto end,
    excluida=public.mensagens.excluida or excluded.excluida,
    data_mensagem=coalesce(excluded.data_mensagem,public.mensagens.data_mensagem);
   n:=n+1;
  end if;
 end loop;
 insert into public.eventos values(hash_arg,instancia_arg,evento_arg,recebidas_arg,n,now())
 on conflict(hash) do nothing;
 return jsonb_build_object('duplicado',false,'aceitas',n);
end $$;
revoke all on function public.registrar_lote(text,text,text,integer,jsonb) from public,anon,authenticated;
grant execute on function public.registrar_lote(text,text,text,integer,jsonb) to service_role;

create function public.buscar_mensagens(consulta text, grupo text default null, limite integer default 20)
returns table(id uuid,instancia text,grupo_jid text,mensagem_id text,participante text,
 data_mensagem timestamptz,texto text,tipo text,midia_status text,origem_evento text)
language sql stable security invoker set search_path=''
as $$ select m.id,m.instancia,m.grupo_jid,m.mensagem_id,m.participante,m.data_mensagem,
 m.texto,m.tipo,m.midia_status,m.origem_evento from public.mensagens m
 join public.grupos g on (g.instancia=m.instancia and g.jid=m.grupo_jid and g.autorizado)
 where not m.excluida and (grupo is null or m.grupo_jid=grupo)
 and m.busca @@ websearch_to_tsquery('portuguese',consulta)
 order by ts_rank(m.busca,websearch_to_tsquery('portuguese',consulta)) desc,m.data_mensagem desc
 limit least(greatest(limite,1),50) $$;
revoke all on function public.buscar_mensagens(text,text,integer) from public,anon,authenticated;
grant execute on function public.buscar_mensagens(text,text,integer) to service_role;

-- Bucket privado: sem políticas públicas de leitura, gravação ou listagem.
insert into storage.buckets(id,name,public,file_size_limit)
values('whatsapp-teste','whatsapp-teste',false,20971520) on conflict(id) do nothing;
