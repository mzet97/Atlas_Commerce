# EVD-008-002 — M8 increment-2: superfície de deploy completa + bloqueio de cluster (2026-11-03)

Status: PARCIAL-MELHORADO — manifests completos e validados (46/46
kubeconform strict, validate.py ALL PASS); DEPLOY bloqueado por ambiente
rootless, com receita de reanimação documentada.

## Manifests novos (superfície de deploy fim-a-fim)
- `deploy.sh`: cria `atlas-secrets` a partir do `.env` do compose NO
  momento do apply (nenhum segredo no git; clusters reais trocam por
  SealedSecrets/ESO); envsubst dos endpoints de infra; `DRY_RUN` repassa
  `--dry-run=server` para clusters reais.
- `20-infra-endpoints.yaml`: Services ExternalName apontando a infra
  publicada pelo compose (mongo/pg/kafka/keycloak/redis/rabbit) — topologia
  dev; statefulsets in-cluster seguem como M8-next. Kafka publica 29092 no
  host para o listener anunciado resolver nos pods.
- `30-ingress.yaml` (storefront /, control /ops, assistant /assistant via
  ingress-nginx, host atlas.local), `40-networkpolicy.yaml` (default-deny
  ingress + same-namespace + ingress controller; egress aberto documentado
  como escolha de dev), `50-hpa-pdb.yaml` (HPA catalog/order 1-3 CPU70%;
  PDB minAvailable=1 para catalog/order/payment/control).
- `validate.py` atualizado: 18 Deployments + 14 Services (aware de
  ExternalName). **ALL PASS.**
- `kubeconform -strict`: **46 resources, 0 invalid** (esquema k8s 1.31).

## Bloqueio de deploy (3 rotas tentadas, mesma raiz)
A máquina inteira é rootless (sem sudo), então NENHUM runtime consegue:
1. **k3s em podman (container `atlas-k3s` do usuário)**: com
   `--cgroupns=host` o cpuset passa, mas `mkdir /sys/fs/cgroup/kubepods`
   → permission denied (userns não cria cgroups no host); sem host-ns,
   falha no cpuset (o crash original registrado no container).
2. **k3d** (docker rootless disponível): server nunca chega a
   "k3s is up and running" (mesma raiz) — rollback completo.
3. **k3s `--rootless` binário nativo**: `net.ipv4.ip_forward` exige
   `sudo sysctl` — indisponível.

## Receita de reanimação (executar COM sudo uma única vez)
```sh
# rootless podman + k3s:
sudo sysctl -w net.ipv4.ip_forward=1
sudo loginctl enable-linger mzet
mkdir -p ~/.config/systemd/user/@.service.d
printf '[Service]\nDelegate=yes\n' > ~/.config/systemd/user/@.service.d/delegate.conf
systemctl --user daemon-reload
# então recriar o container k3s com --cgroupns=host --device /dev/kmsg
# e kubelet-arg feature-gates=KubeletInUserNamespace=true (testado até o
# limite rootless; os passos acima removem os três bloqueios registrados)
# deploy: ENV_FILE=... ./deploy.sh   (ou DRY_RUN='--dry-run=server' antes)
```
Alternativa não-root: executar o deploy num cluster gerenciado de teste
(kind/k3d numa VM com kernel ajustado, ou managed k8s).

## Como reproduzir a validação
```sh
python3 validate.py                      # ALL PASS (18 Deployments, 14 Services)
kubeconform -strict -summary -ignore-missing-schemas *.yaml
./deploy.sh                              # num cluster com kubectl configurado
```
