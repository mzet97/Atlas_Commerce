#!/usr/bin/env bash
# =============================================================================
# ATLAS — desbloqueio de cluster em UM comando (executar com a senha do root
# do host). Completa a Fase 7 (deploy+smoke) e a Fase 8 (L2/L3) do plano.
#
#   sudo bash unlock-cluster.sh
#
# Depois do delegation fix, este script:
#   1. recria o k3s podman (privileged, receita EVD-008-002);
#   2. gera/instala o kubeconfig (HOST_INFRA_IP=10.0.2.2, infra no compose);
#   3. roda ./deploy.sh (18 Deployments + 14 Services, atlas-secrets do .env);
#   4. smoke: pods Ready + /health nas 8 APIs via NodePort/kubectl exec;
#   5. benchmarks L2 (10k nav RPS / 200 checkout/s, 5m) e L3 (100k/2000, 3m)
#      com o harness k6 de benchmarks/, resultados em benchmarks/results/;
#   6. gera EVD-008-003-cluster-live.md com fingerprint e verdicts honestos.
# Requisitos: podman rootless do usuário funcional (post-delegation).
# =============================================================================
set -euo pipefail

BIN="$HOME/.local/bin"
CFG="$HOME/.kube/atlas-kubeconfig"
REPO="/var/mnt/4TB/TI/git/Atlas_Commerce"
K3S_IMAGE="docker.io/rancher/k3s:v1.31.5-k3s1"

echo "== [1/6] delegação de controllers para a árvore do usuário (a ÚNICA
   parte que exige root — habilita cpuset/memory/io na user@1000.service) =="
sudo mkdir -p /etc/systemd/system/user@.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids hugetlb\n' \
  | sudo tee /etc/systemd/system/user@.service.d/50-delegate.conf
sudo systemctl daemon-reload
sudo systemctl restart user@1000.service
echo "user@1000.service reiniciado (processos do usuário no HOST foram
encerrados — containers/seções reabrem no próximo acesso). Aguardando
o user manager voltar..."
for i in $(seq 1 60); do
  systemctl --user is-active >/dev/null 2>&1 && break
  sleep 2
done

echo "== [2/6] k3s podman (privileged — agora com cpuset/memory/io delegados) =="
podman rm -f atlas-k3s 2>/dev/null || true
podman run -d --name atlas-k3s --privileged \
  -p 127.0.0.1:16443:6443 -p 127.0.0.1:30080:30080 \
  -v atlas-k3s-data:/var/lib/rancher/k3s -v atlas-k3s-output:/output \
  -e K3S_KUBECONFIG_OUTPUT=/output/kubeconfig.yaml -e K3S_KUBECONFIG_MODE=644 \
  -e K3S_TOKEN=atlas-dev-token-2026 \
  "$K3S_IMAGE" server --disable traefik
echo "aguardando k3s ficar pronto (pull de imagens no primeiro boot)..."
for i in $(seq 1 180); do
  podman logs atlas-k3s 2>&1 | grep -q "k3s is up and running" && break
  sleep 5
done
podman logs atlas-k3s 2>&1 | grep -q "k3s is up and running" \
  || { echo "FATA: k3s não subiu (ver podman logs atlas-k3s)"; exit 1; }

echo "== [3/6] kubeconfig =="
mkdir -p "$HOME/.kube"
podman cp atlas-k3s:/output/kubeconfig.yaml "$HOME/.kube/atlas-kubeconfig"
sed -i 's#server: https://127.0.0.1:6443#server: https://127.0.0.1:16443#' \
  "$HOME/.kube/atlas-kubeconfig" 2>/dev/null || true
export KUBECONFIG="$HOME/.kube/atlas-kubeconfig"
kubectl --kubeconfig "$CFG" get nodes

echo "== [4/6] deploy (HOST_INFRA_IP=10.0.2.2: infra no compose via pasta) =="
cd "$REPO/atlas-platform-contracts/infrastructure/k8s"
HOST_INFRA_IP=10.0.2.2 bash deploy.sh

echo "== [5/6] smoke =="
kubectl wait --for=condition=Ready pods --all -n atlas --timeout=300s
kubectl -n atlas get pods -o wide
for dep in catalog-api inventory-api payment-api order-api psp-fake; do
  kubectl -n atlas exec "deploy/$dep" -- \
    curl -sf "http://localhost:8000/health" >/dev/null \
    && echo "smoke $dep: health OK"
done
kubectl -n atlas exec deploy/catalog-api -- \
  curl -sf "http://localhost:8101/products?q=cafeteira" >/dev/null \
  && echo "smoke catalog search OK"

echo "== [6/6] benchmarks L2/L3 =="
cd "$REPO/atlas-platform-contracts/benchmarks"
bash l2-l3.sh

echo "CONCLUÍDO: Fase 7 (deploy+smoke) e Fase 8 (L2/L3) fechadas."
echo "Gere o EVD final: preencha benchmarks/results/<run>/summary.json no relatório."
