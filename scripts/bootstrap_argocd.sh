#!/bin/bash
set -e

echo "🚀 Bootstrapping Argo CD..."

# 1. Apply Namespaces
kubectl apply -f infra/manifests/namespaces.yaml

# 2. Install Argo CD (Stable)
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

echo "⏳ Waiting for Argo CD components to be ready..."
kubectl wait --for=condition=available deployment -l "app.kubernetes.io/name=argocd-server" -n argocd --timeout=300s

# 3. Apply Root App
kubectl apply -f infra/argocd/applications/root-app.yaml

echo "✅ Argo CD Bootstrapped!"
echo "🔑 Initial Admin Password:"
echo "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"

