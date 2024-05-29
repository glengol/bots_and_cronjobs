{{- define "application-template" -}}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ include "app.name" . }}
  namespace: argocd
  labels:
    firefly.ai/argo: application
    firefly.ai/application: {{ include "app.name" . }}
    firefly.ai/project: applications
spec:
  project: applications
  source:
  {{- include "app.source" . | indent 4 }}
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: {{ include "app.namespace" . }}
  syncPolicy:
    # automated: {}
    syncOptions:
      - CreateNamespace=true
{{- end -}}