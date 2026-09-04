# GitOps bootstrap documentation.
#
# 1. Deploy Argo CD into Minikube:
#    kubectl create namespace argocd
#    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
#
# 2. Add this repository as an Argo CD "Repository" (Settings -> Repositories)
#    using the URL in gitops/argo-application.yaml.
#
# 3. Apply the Application manifest:
#    kubectl apply -f gitops/argo-application.yaml
#
# Argo CD will now continuously sync helm/appointment-service from the
# `main` branch into the `appointment` namespace (GitOps / pull-based CD).

This directory contains the Argo CD Application manifest that performs
GitOps-based deployment of the appointment-service Helm chart to Minikube.
