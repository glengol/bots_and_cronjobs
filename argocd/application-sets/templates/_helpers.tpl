{{- define "application-sets.clusters.prod.product.generator" -}}
- cluster: {{ include "application-sets.clusters.prod.product.name" . | quote }}
  url: {{ include "application-sets.clusters.prod.product.url" . | quote }}
  env: "prod"
  autoSync: {{ include "application-sets.autoSync.prod" .  }}
{{- end }}



{{- define "application-sets.clusters.prod.product.valuesFiles" -}}
- $values/argocd/application-sets/values/{{"{{"}}.env{{"}}"}}/_global.yaml
- $values/argocd/application-sets/values/{{"{{"}}.env{{"}}"}}/{{"{{"}}.cluster{{"}}"}}/total-assets.yaml
# - $helm-values/{{"{{"}}.env{{"}}"}}/{{"{{"}}.cluster{{"}}"}}/total-assets.yaml
{{- end }}


{{- define "application-sets.clusters.prod.product.url" -}}
{{- printf "https://kubernetes.default.svc" }}
{{- end }}


{{- define "application-sets.argocdRepoName" -}}
{{- printf "https://github.com/infralight/product-projects" }}
{{- end }}


{{- define "application-sets.helmValuesRepoName" -}}
{{- printf "https://github.com/infralight/helm-values" }}
{{- end }}


{{- define "application-sets.clusters.prod.product.name" -}}
{{- printf "product" }}
{{- end }}


{{- define "application-sets.charts.rootPath" -}}
{{- printf "argocd/charts" }}
{{- end }}


{{- define "application-sets.charts.productPath" -}}
{{- printf "%s" (include "application-sets.charts.rootPath" .) }}
{{- end }}


{{- define "application-sets.autoSync.prod" -}}
false
{{- end }}