{{- define "pinger.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "pinger.fullname" -}}
{{- printf "%s" (include "pinger.name" .) -}}
{{- end -}}