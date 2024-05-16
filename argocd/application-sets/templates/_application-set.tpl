{{- define "application-sets.template" -}}
kind: ApplicationSet
apiVersion: argoproj.io/v1alpha1
metadata:
  name: {{ include "appName" . }}
  labels:
    firefly.ai/argo: application-sets
    firefly.ai/application: product
    firefly.ai/project: applications
spec:
  goTemplate: true
  generators:
    - list:
        elements:
          {{- include "application-sets.clusters.prod.product.generator" . | nindent 10 }}
  template:
    metadata:
      name: '{{"{{"}}.env{{"}}"}}-{{"{{"}}.cluster{{"}}"}}-{{ include "appName" . }}'
      labels:
        firefly.ai/argo: application-sets
        firefly.ai/application: {{ include "appName" . }}
        firefly.ai/cluster: '{{"{{"}}.cluster{{"}}"}}'
        firefly.ai/project: "applications"
    spec:
      project: "applications"
      sources:
        - repoURL: "https://infralight.github.io/app-charts"
          chart: "base"
          targetRevision: "0.0.95"
          helm:
            releaseName: {{ include "appName" . }}
            valueFiles:
            {{- include "application-sets.clusters.prod.product.valuesFiles" . | nindent 14 }}
        # - repoURL: {{ include "application-sets.helmValuesRepoName" . }}
        #   targetRevision: "master"
        #   ref: helm-values
        - repoURL: {{ include "application-sets.argocdRepoName" . }}
          targetRevision: {{ .Values.argocdRepoTargetRevision | quote }}
          ref: values
      destination:
        name: '{{"{{"}}.cluster{{"}}"}}'
        namespace: {{ include "appNamespace" . }}
  templatePatch: |
    spec:
      {{"{{"}}- if .autoSync {{"}}"}}
      syncPolicy:
        automated:
          prune: false
          selfHeal: true
          allowEmpty: false
        syncOptions:
          - PrunePropagationPolicy=orphan
          - ApplyOutOfSyncOnly=true
          - CreateNamespace=true
      {{"{{"}}- else {{"}}"}}
      syncPolicy: {}
      {{"{{"}}- end {{"}}"}}
{{- end -}}