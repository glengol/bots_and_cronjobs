{{- define "application-template" -}}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ include "app.name" . }}
  namespace: argocd
  labels:
    firefly.ai/argo: application
    firefly.ai/application: product
    firefly.ai/project: applications
spec:
  project: applications
  source:
    repoURL: {{ include "application-sets.argocdRepoName" . | quote}}
    targetRevision: HEAD
    path: "{{ include "application-sets.clusters.prod.product.valuesFiles" . }}/{{ include "app.name" . }}"
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: {{ include "app.namespace" . }}
  syncPolicy:
    automated: {}
    syncOptions:
      - CreateNamespace=true
{{- end -}}