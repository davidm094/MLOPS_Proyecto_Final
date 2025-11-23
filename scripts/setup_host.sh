#!/bin/bash
set -e

# setup_host.sh
# Configuración inicial para Rocky Linux 9 y K3s
# Basado en References/Guia.md

# IP del Host (Target)
HOST_IP="10.43.100.94"

echo "🔧 Iniciando configuración del Host ($HOST_IP)..."

# 1. Preparación del Sistema Operativo
echo "🛡️ Configurando Firewall y SELinux..."
systemctl disable --now firewalld

# SELinux Permissive
setenforce 0 || true
sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config

# 2. Instalar Dependencias de Almacenamiento (Longhorn requiere iSCSI)
echo "📦 Instalando dependencias de iSCSI y NFS..."
dnf install -y iscsi-initiator-utils nfs-utils
systemctl enable --now iscsid

# 3. Instalación de K3s con Networking Customizado
# Se evitan conflictos con la IP del host (10.43.x.x) moviendo los CIDRs internos
echo "☸️ Instalando K3s..."

export INSTALL_K3S_EXEC="server \
  --node-ip=${HOST_IP} \
  --cluster-cidr=10.44.0.0/16 \
  --service-cidr=10.45.0.0/16 \
  --cluster-dns=10.45.0.10 \
  --disable servicelb \
  --disable traefik \
  --write-kubeconfig-mode 644"

curl -sfL https://get.k3s.io | sh -

echo "✅ Instalación de K3s completada."
echo "ℹ️ CIDRs configurados:"
echo "   - Pod CIDR: 10.44.0.0/16"
echo "   - Service CIDR: 10.45.0.0/16"
echo "   - DNS IP: 10.45.0.10"
echo "ℹ️ Para obtener el kubeconfig: cat /etc/rancher/k3s/k3s.yaml"

