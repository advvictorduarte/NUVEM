-- Coletor do DJEN, rodando dentro do banco em Sao Paulo.
-- Validado em 27/10/2026: deste IP o DJEN responde HTTP 200.

create or replace function coletar_djen(
  p_oab    text,
  p_uf     text,
  p_inicio date default current_date - 1,
  p_fim    date default current_date
)
returns execucoes_coleta
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_execucao   execucoes_coleta;
  v_pagina     int  := 1;
  v_resposta   extensions.http_response;
  v_corpo      jsonb;
  v_lote       jsonb;
  v_qtd        int;
  v_recebidos  int := 0;
  v_novos      int := 0;
  v_atualizados int := 0;
  v_n          int;
  v_a          int;
  v_url        text;
begin
  insert into execucoes_coleta (periodo_inicio, periodo_fim)
  values (p_inicio, p_fim)
  returning * into v_execucao;

  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '120000');

  loop
    v_url := 'https://comunicaapi.pje.jus.br/api/v1/comunicacao'
          || '?pagina=' || v_pagina || '&itensPorPagina=100'
          || '&numeroOab=' || p_oab || '&ufOab=' || p_uf
          || '&dataDisponibilizacaoInicio=' || to_char(p_inicio, 'YYYY-MM-DD')
          || '&dataDisponibilizacaoFim='    || to_char(p_fim,    'YYYY-MM-DD');

    begin
      v_resposta := extensions.http_get(v_url);
    exception when others then
      update execucoes_coleta
         set erro = 'pagina ' || v_pagina || ': falha de rede - ' || sqlerrm,
             completa = false, terminada_em = now(), itens_recebidos = v_recebidos
       where id = v_execucao.id returning * into v_execucao;
      return v_execucao;
    end;

    -- Erro HTTP NUNCA vira "nenhuma publicacao" (CLAUDE.md, regra 2)
    if v_resposta.status <> 200 then
      update execucoes_coleta
         set erro = 'pagina ' || v_pagina || ': HTTP ' || v_resposta.status
                 || case when v_resposta.content like '%block access from your country%'
                         then ' - bloqueio por pais' else '' end,
             completa = false, terminada_em = now(), itens_recebidos = v_recebidos
       where id = v_execucao.id returning * into v_execucao;
      return v_execucao;
    end if;

    begin
      v_corpo := v_resposta.content::jsonb;
    exception when others then
      update execucoes_coleta
         set erro = 'pagina ' || v_pagina || ': resposta nao e JSON',
             completa = false, terminada_em = now(), itens_recebidos = v_recebidos
       where id = v_execucao.id returning * into v_execucao;
      return v_execucao;
    end;

    v_lote := coalesce(v_corpo -> 'items', '[]'::jsonb);
    v_qtd  := jsonb_array_length(v_lote);

    if v_pagina = 1 then
      update execucoes_coleta set total_informado = (v_corpo ->> 'count')::int
       where id = v_execucao.id;
    end if;

    with dados as (
      select i from jsonb_array_elements(v_lote) as i
    ), gravadas as (
      insert into publicacoes (
        id_djen, hash_djen, link, numero_cnj, numero_com_mascara, tribunal,
        orgao, id_orgao, tipo_comunicacao, tipo_documento, nome_classe,
        codigo_classe, meio, data_disponibilizacao, texto, partes, advogados,
        ativo, situacao, data_cancelamento, motivo_cancelamento
      )
      select
        (i ->> 'id')::bigint, i ->> 'hash', i ->> 'link',
        i ->> 'numero_processo', i ->> 'numeroprocessocommascara',
        i ->> 'siglaTribunal', i ->> 'nomeOrgao',
        nullif(i ->> 'idOrgao', '')::int,
        i ->> 'tipoComunicacao', i ->> 'tipoDocumento', i ->> 'nomeClasse',
        i ->> 'codigoClasse', i ->> 'meio',
        (i ->> 'data_disponibilizacao')::date, i ->> 'texto',
        i -> 'destinatarios', i -> 'destinatarioadvogados',
        nullif(i ->> 'ativo', '')::boolean, i ->> 'status',
        nullif(i ->> 'data_cancelamento', '')::timestamptz,
        i ->> 'motivo_cancelamento'
      from dados
      on conflict (id_djen) do update set
        ativo               = excluded.ativo,
        situacao            = excluded.situacao,
        data_cancelamento   = excluded.data_cancelamento,
        motivo_cancelamento = excluded.motivo_cancelamento,
        texto               = excluded.texto,
        visto_em            = now(),
        atualizado_em       = case
          when publicacoes.ativo is distinct from excluded.ativo
            or publicacoes.data_cancelamento is distinct from excluded.data_cancelamento
            or publicacoes.texto is distinct from excluded.texto
          then now() else publicacoes.atualizado_em end
      returning (xmax = 0) as inserido
    )
    select count(*) filter (where inserido), count(*) filter (where not inserido)
      into v_n, v_a from gravadas;

    v_recebidos   := v_recebidos + v_qtd;
    v_novos       := v_novos + coalesce(v_n, 0);
    v_atualizados := v_atualizados + coalesce(v_a, 0);

    exit when v_qtd < 100;
    v_pagina := v_pagina + 1;
    exit when v_pagina > 100;
  end loop;

  update execucoes_coleta
     set itens_recebidos = v_recebidos, novos = v_novos,
         atualizados = v_atualizados, terminada_em = now(),
         completa = (total_informado is null or total_informado = v_recebidos),
         erro = case when total_informado is not null and total_informado <> v_recebidos
                     then 'a API informou ' || total_informado || ' publicacoes e chegaram '
                          || v_recebidos end
   where id = v_execucao.id
   returning * into v_execucao;

  return v_execucao;
end;
$$;

comment on function coletar_djen is
  'Coleta do DJEN com paginacao e deduplicacao por id_djen. Erro nunca vira ausencia de publicacao.';
