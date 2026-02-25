---
phase: 5-scheduling-and-hardening
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker-compose.prod.yml
  - terraform/user_data.sh
autonomous: true
requirements:
  - INFR-05

must_haves:
  truths:
    - "docker-compose.prod.yml merges cleanly with docker-compose.yml via `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`"
    - "Prod overlay sets restart: always on all 5 services"
    - "Prod overlay adds JSON-file log rotation (max-size 10m, max-file 5) on all 5 services"
    - "Prod overlay pins image digests for pgvector/pgvector:pg17 and nginx:alpine"
    - "Prod overlay changes scraper command to sleep infinity (container stays alive)"
    - "Scraper container CMD in Dockerfile is unchanged (still runs main.py for dev use)"
    - "terraform/user_data.sh installs cronie, creates scripts directory, and creates log directory"
  artifacts:
    - path: "docker-compose.prod.yml"
      provides: "Production Docker Compose overlay"
      contains: "restart: always"
    - path: "terraform/user_data.sh"
      provides: "Updated EC2 user data with cronie and directory setup"
      contains: "cronie"
  key_links:
    - from: "docker-compose.prod.yml"
      to: "docker-compose.yml"
      via: "Docker Compose file merge (-f flag)"
      pattern: "services"
---

<objective>
Create the production Docker Compose overlay and update the EC2 provisioning script. The overlay hardens all services with restart policies, log rotation, image digest pinning, and converts the scraper to a long-lived container for cron-based execution.

Purpose: The prod overlay separates dev and production behavior without modifying existing files. The user_data.sh update ensures fresh EC2 instances are ready for scheduled scraping.

Output: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validates successfully. EC2 provisioning includes cronie and required directories.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/5/5-CONTEXT.md
@.planning/phases/5/5-RESEARCH.md
@docker-compose.yml
@scraper/Dockerfile
@terraform/user_data.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: Production Docker Compose overlay</name>
  <files>
    docker-compose.prod.yml
  </files>
  <action>
    1. Create `docker-compose.prod.yml` with the following overlay:

    ```yaml
    # Production overlay — use with:
    #   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    services:
      db:
        image: pgvector/pgvector:pg17@sha256:<DIGEST>
        restart: always
        logging:
          driver: json-file
          options:
            max-size: "10m"
            max-file: "5"

      scraper:
        restart: always
        command: ["sleep", "infinity"]
        logging:
          driver: json-file
          options:
            max-size: "10m"
            max-file: "5"

      api:
        restart: always
        logging:
          driver: json-file
          options:
            max-size: "10m"
            max-file: "5"

      web:
        restart: always
        logging:
          driver: json-file
          options:
            max-size: "10m"
            max-file: "5"

      nginx:
        image: nginx:alpine@sha256:<DIGEST>
        restart: always
        logging:
          driver: json-file
          options:
            max-size: "10m"
            max-file: "5"
    ```

    2. Fetch current image digests for pinning:
       ```bash
       docker pull pgvector/pgvector:pg17 2>/dev/null
       docker inspect --format='{{index .RepoDigests 0}}' pgvector/pgvector:pg17
       docker pull nginx:alpine 2>/dev/null
       docker inspect --format='{{index .RepoDigests 0}}' nginx:alpine
       ```
       If docker is not available locally, use placeholder digests with a comment:
       `# TODO: Replace with actual digest from EC2: docker inspect --format='{{index .RepoDigests 0}}' <image>`

    3. Key design decisions:
       - Scraper `command: ["sleep", "infinity"]` overrides the Dockerfile CMD so the container stays alive for `docker compose exec` invocations. No xvfb-run wrapper needed here — each exec call wraps its own xvfb-run since DISPLAY is per-process-tree.
       - Only `db` and `nginx` get pinned digests (pulled from registry). `scraper`, `api`, `web` are built from source via `build:` directives.
       - Log rotation: 10MB per file, 5 files = 50MB max per service = 250MB total worst case.
       - `restart: always` (not `unless-stopped`) ensures services restart even after `docker stop` + reboot.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet 2>&1 && echo "Docker Compose prod overlay merges successfully"</automated>
    <manual>Verify all 5 services have restart: always, logging config, and scraper has command: sleep infinity</manual>
  </verify>
  <done>
    - docker-compose.prod.yml created with production overlay
    - All 5 services: restart: always + JSON-file log rotation (10m/5 files)
    - pgvector and nginx images pinned by digest
    - Scraper command overridden to sleep infinity for cron-based execution
    - Compose config validates with merged files
  </done>
</task>

<task type="auto">
  <name>Task 2: Update EC2 user_data.sh with cronie and directory setup</name>
  <files>
    terraform/user_data.sh
  </files>
  <action>
    1. Update `terraform/user_data.sh` to add after the git install line:

    ```bash
    # Install cronie for scheduled tasks
    dnf install -y cronie
    systemctl enable crond
    systemctl start crond

    # Install rsync for deployments
    dnf install -y rsync
    ```

    2. Add directory creation after the app directory block:

    ```bash
    # Create directories for scripts and logs
    mkdir -p /opt/procurement-intel/scripts
    mkdir -p /opt/procurement-intel/logs
    chown -R ec2-user:ec2-user /opt/procurement-intel
    ```

    3. Keep all existing content intact. The additions go after the existing `dnf install -y git` line and the existing `mkdir -p /opt/procurement-intel` block respectively.

    NOTE: rsync is already mentioned in STATE.md as installed in Phase 1 ("rsync installed on EC2 (not in AL2023 by default)"). Including it here ensures fresh deployments have it too.
  </action>
  <verify>
    <automated>grep -q "cronie" /Users/clawbot/dev/terraform/user_data.sh && grep -q "scripts" /Users/clawbot/dev/terraform/user_data.sh && echo "user_data.sh updated"</automated>
    <manual>Verify user_data.sh installs cronie, enables crond, creates /opt/procurement-intel/scripts and /opt/procurement-intel/logs</manual>
  </verify>
  <done>
    - user_data.sh installs cronie and enables crond service
    - user_data.sh installs rsync for deployment consistency
    - Scripts and logs directories created under /opt/procurement-intel
    - All existing provisioning steps preserved
  </done>
</task>

</tasks>

<verification>
1. `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validates without errors
2. All 5 services in prod overlay have `restart: always`
3. All 5 services have JSON-file log rotation with max-size and max-file
4. Scraper service has `command: ["sleep", "infinity"]` in prod overlay
5. pgvector and nginx images have pinned SHA256 digests (or documented TODO)
6. terraform/user_data.sh includes cronie installation and directory creation
</verification>

<success_criteria>
- Production Docker Compose overlay merges cleanly with base config
- All services hardened with restart: always and log rotation
- Scraper container stays alive in production (sleep infinity)
- EC2 provisioning includes cronie and required directories
</success_criteria>

<output>
After completion, create `.planning/phases/5/5-01-SUMMARY.md`
</output>
