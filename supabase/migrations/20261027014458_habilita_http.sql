-- Extensao http: permite ao proprio banco (em Sao Paulo) chamar a API do DJEN.
-- Testa a hipotese da Fase 1: o bloqueio do DJEN e por pais do IP de saida.
create extension if not exists http with schema extensions;
