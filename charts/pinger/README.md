# Pinger Helm chart

Usage: helm install pinger ./charts/pinger -f charts/pinger/values.yaml

## Notes

- The chart exposes two ports: metrics and health. Prometheus scrape annotations are added to the Deployment.

- If you use Prometheus Operator, set `prometheus.serviceMonitor.enabled=true` to create a ServiceMonitor.

- Adjust env values in `values.yaml` as needed.
