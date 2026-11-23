---
kind: business_term
name: Business Glossary
category: business_term
scope:
    - '**'
---

### Presenton Enterprise
- Definition：The commercial/enterprise tier of Presenton offering Helm chart deployment on Kubernetes, centralized admin console, audit logs, and enterprise authentication via SSO, OIDC, and SCIM for automated user provisioning.

### Community gallery
- Definition：The cloud-backed feature that lets users browse and import presentation designs created by other Presenton users; controlled by `PRESENTON_COMMUNITY_ENABLED` and disabled for air-gapped deployments.

### Presentation generation modes
- Definition：Three mutually exclusive UI modes exposed by `PRESENTATION_GENERATION_MODE`: `both` (default), `standard`, and `smart`; `smart` additionally hides template features. Controls which generation paths are available to the user and MCP server.

### First-run onboarding
- Definition：The initial setup flow presented to a new installation where the user creates the admin account and configures an LLM provider/API key; before completion, non-auth status endpoints return 200 but all other API calls return 428 Precondition Required.
