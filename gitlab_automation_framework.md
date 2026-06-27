# GitLab Automation Framework (Jira-like Automation)

## 🎯 Objective
Build a scalable, event-driven automation engine for GitLab Work Items (Issues) that replicates Jira-like automation features such as:

- Automatic Epic assignment
- Status-based date updates (start / done)
- Workflow automation via labels
- Weight (story points) tracking
- Rule-based automation using YAML

---

## 🧠 Architecture Overview

```
GitLab (Webhook Events)
        │
        ▼
Automation Service (Python - Flask/FastAPI)
        │
        ├── Rules Engine (YAML-based)
        ├── Action Executor (GitLab API)
        │
        ▼
GitLab API (Update Issues)
```

---

## ⚙️ Core Components

### 1. Webhook Listener
- Receives GitLab events (issue open/update)
- Stateless and lightweight

### 2. Rules Engine (YAML)
- Declares automation logic
- Avoids hardcoding rules

### 3. Action Engine
- Executes API calls to GitLab

### 4. Optional Database
Use only if needed:
- Audit logs
- Metrics
- Historical tracking

---

## 🗂️ Project Structure

```
project-root/
│
├── app/
│   ├── main.py
│   ├── handler.py
│   ├── rules_engine.py
│   ├── actions.py
│   └── gitlab_client.py
│
├── config/
│   ├── rules.yaml
│   └── settings.yaml
│
├── logs/
│   └── automation.log
│
├── Dockerfile
└── requirements.txt
```

---

## 📜 Example Rules (rules.yaml)

```
rules:
  - name: projeto_epic
    match:
      labels: ["tipo::projeto"]
    actions:
      - set_epic: 123

  - name: start_date
    match:
      labels: ["status::in-progress"]
      on_change: true
    actions:
      - set_start_date: now

  - name: done_date
    match:
      labels: ["status::done"]
      on_change: true
    actions:
      - set_due_date: now
```

---

## 🚀 Processing Flow

1. GitLab triggers webhook
2. Service receives payload
3. Extracts labels and changes
4. Matches rules (YAML)
5. Executes corresponding actions
6. Calls GitLab API

---

## ⚡ Optimization Strategy

- Event-driven (no polling)
- No CI/CD pipelines required
- No runner usage
- Execute only on relevant change

---

## 🐳 Containerization

### Dockerfile Example

```
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app/main.py"]
```

---

## ☸️ High Availability (Kubernetes)

- Use 2+ replicas
- Stateless service
- Horizontal scaling

Example:

```
replicas: 2
```

---

## 🔐 Best Practices

- Validate webhook secret
- Avoid loops (ignore bot updates)
- Implement idempotency
- Use structured logging (JSON)

---

## 📊 Metrics (Weight / Story Points)

- Use GitLab `weight` field
- Aggregate via API or scheduled job

---

## ✅ Conclusion

This architecture provides:

- Jira-like automation in GitLab
- Low resource consumption
- High scalability
- Full governance and auditability

---

## 🧠 Prompt for AI Usage

Design a GitLab automation system using Python that:
- Uses webhooks (event-driven)
- Applies rules defined in YAML
- Automatically assigns epics based on labels
- Sets start_date when label 'in-progress' is applied
- Sets due_date when label 'done' is applied
- Uses GitLab API for updates
- Avoids pipelines and runners
- Supports containerization and Kubernetes deployment
- Includes best practices for idempotency, logging, and scalability

Provide full implementation including:
- Project structure
- Python code (Flask or FastAPI)
- YAML rules examples
- API integration
- Deployment strategy (Docker + Kubernetes)
