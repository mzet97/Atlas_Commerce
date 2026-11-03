# SPEC-001 risks

| # | Risco | Estado |
|---|---|---|
| R-M1-01 | Credenciais dev em `.env` vazarem para commit | Contido: guards de CI + `.gitignore`; rever antes do 1º push |
| R-M1-02 | `network_mode: host` no control-api vazar para prod | Contido: marcado dev-only no compose; charts M8 não herdam |
| R-M1-03 | Keycloak `start-dev` sem TLS em demo | Aceito p/ M1; TLS termina no Ingress em M8 |
| R-M1-04 | Sem remote: CI nunca executada em runner | OPEN — exige decisão de hospedagem |
| R-M1-05 | Imagens pinadas por tag (digest só em evidência) | Aceito p/ dev; digests no `docker-compose` travam em M8 |
