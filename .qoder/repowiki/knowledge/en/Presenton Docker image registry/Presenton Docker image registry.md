---
kind: external_dependency
name: Presenton Docker image registry
slug: github-container-registry
category: external_dependency
category_hints:
    - vendor_identity
scope:
    - '**'
---

### Presenton distribution
- The official prebuilt image is published under `ghcr.io/presenton/presenton:latest` and pulled by the README's one-command Docker run.
- When building from source, `docker compose up production` builds the local `Dockerfile` into the image tag `presenton-production:latest` (compose service name `production`).
- GPU variants (`production-gpu`, `development-gpu`) reserve an NVIDIA device via Compose `deploy.resources.reservations.devices`.
- Verify exact image tags against the GitHub Packages/Publishing workflow that publishes them.