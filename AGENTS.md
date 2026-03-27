# Agent Guide (toys/jenkins-mgt)

Flask web app that aggregates Jenkins job/build info and renders a dashboard.

## Commands (Run/Test)

Run commands from `toys/jenkins-mgt/`.

- Setup
  - `python3 -m venv venv`
  - `source venv/bin/activate`
  - `python3 -m pip install -r requirements.txt`

- Run
  - `python3 app.py`
  - Default: `http://localhost:5000`

- Tests
  - `./run_tests.sh`
  - Single unittest:
    - `python3 -m unittest test_jenkins_manager.TestJenkinsManager.test_load_config_success`

## Configuration

- Primary config: `jobs_config.yaml`
  - Jenkins environments, folder/job grouping, and tokens.
- The app expects to read `jobs_config.yaml` from the current working directory.

## Docker / K8s

- Docker: `Dockerfile` exists; `build.sh` uses `docker buildx` + push to a registry.
- K8s manifests under `k8s/` mount `jobs_config.yaml` via ConfigMap.

## Safety / Gotchas

- Treat Jenkins tokens in `jobs_config.yaml` as secrets; do not commit/share them.
- Network/VPN may be required to reach Jenkins.
- Keep diffs minimal; avoid formatting or dependency churn unrelated to the dashboard.
