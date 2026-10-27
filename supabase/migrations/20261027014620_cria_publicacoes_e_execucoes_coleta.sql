-- Fase 2, primeira migracao. Modelo conforme a secao 6 do SPEC.md.
-- Nomes em portugues, sem acento, minusculas com sublinhado (CLAUDE.md).

create table if not exists publicacoes (
  id_djen                bigint primary key,            -- `id` do DJEN: chave natural
  hash_djen              text not null,                 -- `hash` do DJEN
  link                   text,                          -- identifica o ATO: varias publicacoes
                                                        -- do mesmo despacho compartilham este link
  numero_cnj             text not null,                 -- sem mascara, serve ao DataJud
  numero_com_mascara     text,
  tribunal               text,
  orgao                  text,
  id_orgao               integer,
  tipo_comunicacao       text,
  tipo_documento         text,
  nome_classe            text,
  codigo_classe          text,
  meio                   text,
  data_disponibilizacao  date not null,                 -- base da contagem de prazo (regra 8)
  texto                  text,
  partes                 jsonb,                         -- `destinatarios` cru
  advogados              jsonb,                         -- `destinatarioadvogados` cru
  -- Cancelamento: o DJEN pode anular uma publicacao ja feita, e com ela o prazo
  ativo                  boolean,
  situacao               text,                          -- `status` do DJEN
  data_cancelamento      timestamptz,
  motivo_cancelamento    text,
  coletado_em            timestamptz not null default now(),
  atualizado_em          timestamptz not null default now(),
  visto_em               timestamptz not null default now()
);

create index if not exists publicacoes_data_idx      on publicacoes (data_disponibilizacao desc);
create index if not exists publicacoes_numero_idx    on publicacoes (numero_cnj);
create index if not exists publicacoes_tribunal_idx  on publicacoes (tribunal);
create index if not exists publicacoes_link_idx      on publicacoes (link);
create index if not exists publicacoes_coletado_idx  on publicacoes (coletado_em desc);

comment on table publicacoes is
  'Publicacoes do DJEN. Chave de deduplicacao: id_djen. Publicacoes diferentes do MESMO ato compartilham `link` (uma por intimado).';

create table if not exists execucoes_coleta (
  id                 bigserial primary key,
  fonte              text not null default 'DJEN',
  iniciada_em        timestamptz not null default now(),
  terminada_em       timestamptz,
  periodo_inicio     date not null,
  periodo_fim        date not null,
  total_informado    integer,
  itens_recebidos    integer,
  novos              integer,
  atualizados        integer,
  completa           boolean not null default false,
  erro               text
);

create index if not exists execucoes_completa_idx on execucoes_coleta (completa, periodo_fim desc);

comment on table execucoes_coleta is
  'Diz ate que dia a coleta esta completa. Regra 2 do CLAUDE.md: nunca afirmar "sem novidades" sem consultar esta tabela.';

alter table publicacoes      enable row level security;
alter table execucoes_coleta enable row level security;
