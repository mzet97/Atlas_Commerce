# sdd/dependency-matrix.md — toolchain verificada (M1-increment-1, 2026-10-27)

Versões observadas na execução, não congeladas. Locks pinam no bootstrap.

| Ferramenta | Versão observada | Fonte | Estado |
|---|---|---|---|
| Python | 3.14.7 | `python3 --version` | VERIFIED |
| uv | 0.11.15 | `uv --version` | VERIFIED |
| Node | v24.15.0 | `node --version` | VERIFIED |
| pnpm | 11.1.3 | `pnpm --version` | VERIFIED |
| Java (PlantUML) | OpenJDK 25.0.4.1 | `java -version` | VERIFIED |
| Docker (host) | 29.9.2 via `distrobox-host-exec` | `docker --version` | VERIFIED |
| git | 2.55.0 | `git --version` | VERIFIED |
| mermaid-cli | 12.0.0 via npx | render 10/10 OK | VERIFIED |
| PlantUML | 1.2025.0 | `-checkonly` 2/2 OK | VERIFIED |
| Angular CLI (`ng`) | ausente | `command -v ng` vazio | TODO (M1-next: `npm i -g @angular/cli`) |
| buf | ausente | `command -v buf` vazio | TODO (M1-next: install + `buf lint/breaking`) |

Regra: nunca `latest` em manifests de produção; SBOM + lockfiles no bootstrap
de cada serviço. FastAPI/Pydantic/Mongo-driver e demais libs Python serão
pinadas via `uv lock` no primeiro serviço (SPEC-002), não aqui.
