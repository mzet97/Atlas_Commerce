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

## Receita de reanimação (EXECUTADA nesta sessão com sudo local — ver
## "Investigação final" abaixo)
A investigação final (com sudo local) refinou a causa-raiz: **o controlador
`cpuset` não está delegado na árvore systemd-user** (user@1000.service
delega apenas cpu/io/memory/pids/dmem) e o kubelet exige cpuset no cgroup
v2 — mas `net.ipv4.ip_forward` é namespaced (gravável num netns próprio,
como provado: `unshare -n` + write = OK). Receita correta com sudo do
HOST (a de baixo é do usuário, insuficiente para cpuset):
```sh
# 1) delegar TODOS os controladores (inclusive cpuset) para a árvore do usuário:
sudo mkdir -p /etc/systemd/system/user@1000.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids hugetlb\n' \
  | sudo tee /etc/systemd/system/user@1000.service.d/50-delegate.conf
sudo systemctl daemon-reload
sudo systemctl restart user@1000.service   # encerra processos do usuário!

# 2) recriar o k3s (podman rootless, privileged):
podman rm -f atlas-k3s
podman run -d --name atlas-k3s --privileged \
  -p 127.0.0.1:16443:6443 -p 127.0.0.1:30080:30080 \
  -v atlas-k3s-data:/var/lib/rancher/k3s -v atlas-k3s-output:/output \
  -e K3S_KUBECONFIG_OUTPUT=/output/kubeconfig.yaml \
  -e K3S_KUBECONFIG_MODE=644 rancher/k3s:v1.31.5-k3s1 server

# 3) export KUBECONFIG=/var/home/mzet/.local/share/containers/storage/
#    volumes/atlas-k3s-output/_data/kubeconfig.yaml && ./deploy.sh
```

## Investigação final desta sessão (2026-11-03, sudo local disponível)
- `sudo -n` funciona NO CONTAINER ZCode (passwordless) mas o kernel é o
  do host via distrobox: **user namespace** (uid_map 0→1) + netns inicial
  → sysctl host (`ip_forward`) e veth no netns host: EPERM definitivo.
- Netns PRÓPRIO: `unshare -n` → `ip_forward=1` gravável (net sysctl é
  namespaced) + slirp4netns anexado (tap0 10.0.2.100, internet OK).
- k3s NATIVO dentro do netns (com `cgroups-per-qos=false`,
  `KubeletInUserNamespace=true`): fatal **"failed to find cpuset cgroup
  (v2)"** — k3s valida cpuset no pre-flight, intransponível sem cpuset
  delegado (o `cgroups-per-qos=false` do kubelet não afeta o pre-flight
  do k3s).
- Delegação user-systemd testada: drop-ins user-1000.slice/app.slice/
  session.slice + `Delegate=yes` em serviço transiente → controllers =
  `cpu io memory pids dmem` (**cpuset NUNCA desce**: falta no
  user@1000.service pai, que é unidade do HOST systemd).
- Conclusão: kubelet não roda sob o usuário mzet neste host; a receita
  acima (root do host, uma vez) é o caminho, ou cluster externo.

## Alternativa não-root: executar o deploy num cluster gerenciado de teste
(kind/k3d numa VM com kernel ajustado, ou managed k8s).

## Como reproduzir a validação
```sh
python3 validate.py                      # ALL PASS (18 Deployments, 14 Services)
kubeconform -strict -summary -ignore-missing-schemas *.yaml
./deploy.sh                              # num cluster com kubectl configurado
```


## Investigação de desbloqueio #2 (2026-11-03, sudo local — resultado DEFINITIVO)
Executando a receita com o sudo disponível (dentro da user namespace do
container ZCode/distrobox — uid_map `0 1 1000`):
- `ip_forward`: gravável em **netns próprio** (`unshare -n` — sysctl é
  namespaced) → não é bloqueador (provado com slirp4netns anexado,
  internet OK no netns).
- k3s server **sem agente** (`--disable-agent`): sobe limpo (etcd/CM/
  scheduler Healthy; o pre-flight de cpuset pertence ao AGENT).
- kubelet standalone (binário oficial v1.31.5, `cgroups-per-qos=false`,
  `KubeletInUserNamespace=true`, `--fail-swap-on=false`): registra o node
  (amdr7, NotReady sem CNI — tolerado) MAS **nenhum pod cria sandbox**:
  o kernel do host (`7.2.11-ogc4.1`, kernel customizado) retorna
  **ENOTS ("Operation not supported")** ao delegar os controladores
  `memory` e `io` na árvore do usuário (`cgroup.subtree_control`), e o
  runc falha com "cannot enter cgroupv2 /sys/fs/cgroup/k8s.io ... invalid
  state" (no-internal-process + controllers indisponíveis).
- Delegação systemd-user testada por drop-ins (user-1000.slice,
  app.slice, session.slice, `@.service`) + serviço transiente
  `Delegate=yes`: os controladores que chegam à árvore do usuário são
  SEMPRE `cpu io memory pids dmem` conforme o pai — `cpuset` e o próprio
  `memory`(delegação efetiva) exigem unidades do HOST systemd
  (`/etc/systemd/system/user@.service.d`), i.e. root do host de verdade.

## Conclusão definitiva
O kubelet **não pode rodar** sob o usuário `mzet` neste host: o kernel
`7.2.11-ogc4.1` restringe a delegação de `memory`/`io` (ENOTS) e o
`cpuset` nunca desce na árvore do usuário. Os caminhos são EXATAMENTE
dois, e ambos dependem de credencial que só o usuário possui:
1. **Root do host (uma vez)**: `/etc/systemd/system/user@.service.d`
   delegando `cpu cpuset io memory pids` + restart de user@1000.service
   (encerra processos do usuário — fazer em logout), depois
   `podman run ... k3s server` + `./deploy.sh` + L2/L3 (harness pronto).
2. **Kubeconfig externo**: qualquer cluster; `./deploy.sh` aceita
   `HOST_INFRA_IP` para alcançar a infraestrutura e os benchmarks L2/L3
   rodam com o harness k6 parametrizado.

Artefato adicional pronto para o primeiro cluster disponível:
`infrastructure/k8s/island/island-checkout.yaml` (5 pods hostNetwork do
caminho de checkout, imagens importadas via `podman save | ctr import`).
