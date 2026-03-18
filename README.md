<img width="1171" height="830" alt="Screenshot 2026-03-18 115123" src="https://github.com/user-attachments/assets/a9602a20-1130-4447-b91a-ae62aaadc8a1" /># 🐳 AI-Based Container Health Monitoring System

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5?logo=kubernetes)
![Prometheus](https://img.shields.io/badge/Prometheus-Metrics-E6522C?logo=prometheus)
![Grafana](https://img.shields.io/badge/Grafana-Dashboard-F46800?logo=grafana)
![scikit-learn](https://img.shields.io/badge/scikit--learn-IsolationForest-F7931E?logo=scikitlearn)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?logo=githubactions)

An AI-driven monitoring platform for Docker and Kubernetes containers that uses machine learning (Isolation Forest) to detect anomalies, trigger automated recovery workflows, and visualize container health in real time.

---

## 📸 Screenshots

### 🤖 AI Anomaly Detection — Grafana Dashboard
Live anomaly scores for all containers, with Prometheus scoring `1.0` as a behavioral outlier.

![Grafana Dashboard](![ss_anomaly_logs](https://github.com/user-attachments/assets/eb73e537-9201-4fa0-9030-27def0e208a9))

---

### 📊 Prometheus Targets — All UP
All scrape targets healthy and collecting metrics every 15 seconds.

![Prometheus Targets](<img width="1911" height="909" alt="Screenshot 2026-03-18 043515" src="https://github.com/user-attachments/assets/d6a4c10d-308a-43d6-9b37-f3b659139d58" />)

---

### 🔍 Anomaly Detector — Live Logs
The AI model detecting normal behavior across all 6 containers in real time.

![Anomaly Detector Logs](<img width="1916" height="923" alt="Screenshot 2026-03-18 042249" src="https://github.com/user-attachments/assets/3719ff74-551e-4023-814e-bb13fef4197b" />)

---

### 📈 Live Anomaly Scores via API
Real-time container anomaly scores returned by the FastAPI endpoint.

![Live Scores](<img width="1171" height="830" alt="Screenshot 2026-03-18 115123" src="https://github.com/user-attachments/assets/3cfdcd7d-1e8a-472f-9294-2c8a83737ae6" />)

---

### 🚀 FastAPI — AI Detector API Docs
Auto-generated Swagger UI showing all available endpoints.

![API Docs](<img width="1916" height="923" alt="Screenshot 2026-03-18 042249" src="https://github.com/user-attachments/assets/03db1908-f4dc-4d0c-81bd-59c160e3050c" />)

---

### 🚨 Alertmanager — Alert Fired
Alertmanager receiving and displaying a fired alert successfully.

![Alertmanager](<img width="1919" height="927" alt="Screenshot 2026-03-18 115314" src="https://github.com/user-attachments/assets/8cdc2baf-3e48-49ce-88d2-2c6a0a60347a" />)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network                          │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  cAdvisor   │    │ Node Exporter│    │   Containers  │  │
│  │  :8080      │    │   :9100      │    │  (monitored)  │  │
│  └──────┬──────┘    └──────┬───────┘    └───────┬───────┘  │
│         │                  │                    │           │
│         └──────────────────┼────────────────────┘           │
│                            │ scrape                         │
│                    ┌───────▼───────┐                        │
│                    │  Prometheus   │◄── Anomaly Detector    │
│                    │    :9090      │    metrics (:8001)      │
│                    └───────┬───────┘                        │
│                            │ alert rules                    │
│                    ┌───────▼───────┐                        │
│                    │ Alertmanager  │──► Webhook Recovery     │
│                    │    :9093      │                        │
│                    └───────────────┘                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           AI Anomaly Detector  :8000/:8001          │   │
│  │  Docker SDK → Feature Vector → Isolation Forest     │   │
│  │  Score > 0.7 → Recovery Engine → Restart/Scale      │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                               │
│                    ┌───────▼───────┐                        │
│                    │    Grafana    │                        │
│                    │    :3000      │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
AI-HealthMonitoringSystem/
├── docker-compose.yml              # Full local stack
├── anomaly_detector/
│   ├── main.py                     # AI detection + FastAPI server
│   ├── recovery.py                 # Auto-recovery engine
│   ├── Dockerfile                  # Container image
│   └── requirements.txt            # Python dependencies
├── Prometheus/
│   ├── prometheus.yml              # Scrape config
│   └── alert.rules.yml             # Alerting rules
├── Alert-Manager/
│   └── alertmanager.yml            # Alert routing config
├── grafana/
│   └── provisioning/
│       ├── datasources/            # Auto-provisioned Prometheus datasource
│       └── dashboards/
│           ├── dashboard.yml       # Dashboard provider config
│           └── ai-container-health.json  # Dashboard definition
├── Kubernetes/
│   ├── 00-namespace-rbac.yml       # Namespace + RBAC
│   ├── 01-configmaps.yml           # All configs
│   ├── 02-storage.yml              # PersistentVolumeClaims
│   ├── 03-prometheus.yml           # Prometheus deployment
│   ├── 04-grafana.yml              # Grafana + Secret
│   ├── 05-daemonsets.yml           # cAdvisor + Node Exporter
│   ├── 06-alertmanager.yml         # Alertmanager deployment
│   └── 07-anomaly-detector.yml     # AI detector + HPA
├── github/
│   └── ci-cd.yml                   # GitHub Actions pipeline
└── scripts/
    └── deploy.sh                   # One-command K8s deploy
```

---

## 🤖 How the AI Works

The system uses **Isolation Forest** — an unsupervised ML algorithm from scikit-learn.

### Feature Collection
Every 15 seconds, the detector collects 4 metrics per container via the Docker SDK:
```
[cpu_percent, memory_mb, net_rx_bytes, net_tx_bytes]
```

### Anomaly Scoring
The Isolation Forest builds 100 decision trees. It randomly splits data until each container is isolated. The key insight:
- **Normal containers** take many splits to isolate (they cluster together)
- **Anomalous containers** get isolated in very few splits (they're outliers)

### Decision Matrix
| Anomaly Score | Action |
|---|---|
| 0.0 – 0.5 | Normal — log and continue |
| 0.5 – 0.7 | Warning — send notification |
| 0.7 – 0.9 | Anomaly — restart container |
| 0.9 – 1.0 | Critical — restart + alert immediately |

### Crash Loop Protection
If a container restarts more than **3 times in 5 minutes**, the recovery engine stops auto-restarting and fires a critical alert for manual intervention.

---

## 🚀 Quick Start (Docker Compose)

### Prerequisites
- Docker Desktop installed and running
- WSL2 (Windows) or Linux/macOS

### Run the full stack
```bash
git clone https://github.com/OmkarOjha/AI-Based_Container_Health_Monitor_System.git
cd AI-Based_Container_Health_Monitor_System
docker compose up -d
```

### Access the services
| Service | URL | Credentials |
|---|---|---|
| 📊 Grafana | http://localhost:3000 | admin / admin123 |
| 🔥 Prometheus | http://localhost:9090 | — |
| 🤖 Anomaly API | http://localhost:8000/docs | — |
| 🚨 Alertmanager | http://localhost:9093 | — |
| 📦 cAdvisor | http://localhost:8080 | — |

### Check anomaly scores
```bash
curl http://localhost:8000/scores
```

### Trigger manual recovery
```bash
curl -X POST http://localhost:8000/recover/grafana
```

### Simulate anomaly (stress test)
```bash
docker run --rm -d --name stress-test \
  containerstack/alpine-stress stress --cpu 4 --timeout 120
```

---

## ☸️ Kubernetes Deployment

```bash
# Start Minikube
minikube start --memory=4096 --cpus=2

# Deploy everything
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# Check pods
kubectl get pods -n monitoring

# Access Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health + model status |
| GET | `/scores` | Live anomaly scores for all containers |
| GET | `/metrics-raw` | Raw container metrics (CPU, memory, network) |
| POST | `/alert` | Webhook for Alertmanager alerts |
| POST | `/alert/critical` | Webhook for critical alerts |
| POST | `/recover/{container}` | Manually trigger container recovery |

---

## ⚙️ GitHub Actions CI/CD

On every push to `main`:
1. **Lint** — flake8 checks Python code
2. **Test** — runs pytest suite
3. **Build** — builds and pushes Docker image to Docker Hub
4. **Deploy** — applies Kubernetes manifests

### Required GitHub Secrets
| Secret | Description |
|---|---|
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `KUBECONFIG` | Base64-encoded kubeconfig |

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Docker + Docker Compose | Container orchestration (local) |
| Kubernetes | Container orchestration (production) |
| Prometheus | Metrics collection and alerting rules |
| Grafana | Dashboard visualization |
| Python + scikit-learn | Anomaly detection (Isolation Forest) |
| FastAPI + Uvicorn | REST API for detector service |
| Docker SDK for Python | Direct container metrics collection |
| Alertmanager | Alert routing and webhook delivery |
| GitHub Actions | CI/CD pipeline |

---

## 👨‍💻 Author

**Omkar Ojha**
- GitHub: [@OmkarOjha](https://github.com/OmkarOjha)
- Project: [AI-Based_Container_Health_Monitor_System](https://github.com/OmkarOjha/AI-Based_Container_Health_Monitor_System)
