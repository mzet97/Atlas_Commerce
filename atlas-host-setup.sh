#!/bin/bash
# Atlas host setup (M8 unlock) — executa via pkexec (diálogo de senha na
# sessão do usuário) ou sudo. Idempotente.
set -euxo pipefail

# 1) delegação de controllers para serviços do usuário (corrige o k3s
#    rootless do usuário de forma PERSISTENTE — sem restart da sessão)
mkdir -p /etc/systemd/system/user@.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids\n' \
  > /etc/systemd/system/user@.service.d/50-delegate.conf
systemctl daemon-reload

# 2) k3s como serviço do SISTEMA com Delegate=yes: control plane + agente
#    completos (embedded containerd/kubelet, CNI flannel, NodePort),
#    rodando como root com todos os controllers da árvore do sistema.
systemctl stop atlas-k3s.service 2>/dev/null || true
systemd-run --system --unit=atlas-k3s --property=Delegate=yes \
  /home/mzet/.local/bin/k3s server \
  --disable traefik --disable servicelb --disable metrics-server \
  --disable-cloud-controller \
  --data-dir /var/lib/rancher-k3s-atlas \
  --write-kubeconfig /home/mzet/.kube/atlas-kubeconfig \
  --write-kubeconfig-mode 644

# 3) kubeconfig legível pelo usuário (container acessa via 127.0.0.1 —
#    o container compartilha o netns do host)
for i in $(seq 1 90); do
  [ -s /home/mzet/.kube/atlas-kubeconfig ] && break
  sleep 2
done
chown -R mzet:mzet /home/mzet/.kube 2>/dev/null || true
echo "ATLAS-HOST-SETUP-OK"
