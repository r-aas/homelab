# MCP Platform for k3d

Local agentic platform based on MCP Gateway Registry, deployed on k3d with Traefik ingress.

## Stack
- k3d + Traefik ingress
- MCP Gateway Registry (agents, MCPs, A2A)
- Keycloak (auth)
- OpenTelemetry (observability)

## Services

| Service | URL | Port |
|---------|-----|------|
| Registry | https://mcp-registry.127-0-0-1.sslip.io | 7860 |
| Auth | https://mcp-auth.127-0-0-1.sslip.io | 8888 |
| Keycloak | https://keycloak.127-0-0-1.sslip.io | 8080 |
| Metrics | https://mcp-metrics.127-0-0-1.sslip.io | 8890 |

## Quick Start

```bash
# Full platform startup
task up

# Check status
task status

# Test endpoints
task test

# Full shutdown
task down
```

## Taskfile Commands

| Command | Description |
|---------|-------------|
| `task up` | Full platform startup |
| `task down` | Full platform shutdown |
| `task status` | Show platform status |
| `task test` | Test all endpoints |
| `task logs` | Tail all logs |
| `task restart` | Restart deployments |
| `task clean` | Delete cluster and images |

### Build Commands
| Command | Description |
|---------|-------------|
| `task build:all` | Build all images |
| `task build:registry` | Build registry image |
| `task build:auth` | Build auth-server image |
| `task build:metrics` | Build metrics-service image |

### Cluster Commands
| Command | Description |
|---------|-------------|
| `task cluster:create` | Create k3d cluster |
| `task cluster:delete` | Delete cluster |
| `task cluster:start` | Start existing cluster |
| `task cluster:stop` | Stop without deleting |

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │           Traefik Ingress           │
                    │  (*.127-0-0-1.sslip.io → Services)  │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐        ┌─────────────────┐        ┌─────────────────┐
│    Registry   │◀──────▶│   Auth Server   │◀──────▶│    Keycloak     │
│   (7860)      │        │    (8888)       │        │    (8080)       │
└───────┬───────┘        └────────┬────────┘        └────────┬────────┘
        │                         │                          │
        ▼                         ▼                          ▼
┌───────────────┐        ┌─────────────────┐        ┌─────────────────┐
│Metrics Service│        │   Metrics DB    │        │  Keycloak DB    │
│   (8890)      │◀──────▶│   (SQLite)      │        │  (PostgreSQL)   │
└───────────────┘        └─────────────────┘        └─────────────────┘
```

## Directory Structure

```
mcp-platform/
├── README.md
├── Taskfile.yml
└── k8s/
    ├── base/
    │   ├── kustomization.yaml
    │   ├── namespace.yaml
    │   ├── configmap.yaml
    │   ├── secrets.yaml
    │   ├── keycloak-db.yaml
    │   ├── keycloak.yaml
    │   ├── metrics-db.yaml
    │   ├── metrics-service.yaml
    │   ├── auth-server.yaml
    │   ├── registry.yaml
    │   └── ingress.yaml
    └── overlays/
        └── local/
            └── kustomization.yaml
```

## Reference
Based on: `~/code/references/mcp-gateway-registry`
