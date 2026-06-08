# ──────────────────────────────────────────────
# WORKFLOW NAME — shown in the GitHub Actions tab
# ──────────────────────────────────────────────
name: CI/CD Pipeline

# ──────────────────────────────────────────────
# ON — WHEN does this workflow run?
# ──────────────────────────────────────────────
on:
  push:
    branches: [main, develop]   # run when code is pushed to these branches
  pull_request:
    branches: [main]            # run when a PR targets main
  workflow_dispatch:            # allows you to trigger it manually from GitHub UI

# ──────────────────────────────────────────────
# ENV — global environment variables
# available to ALL jobs
# ──────────────────────────────────────────────
env:
  NODE_VERSION: '20'
  DOCKER_IMAGE: my-app

# ══════════════════════════════════════════════
# JOBS
# Each job runs in its own fresh virtual machine
# ══════════════════════════════════════════════
jobs:

  # ────────────────────────────────
  # JOB 1: BUILD
  # Install dependencies, compile
  # ────────────────────────────────
  build:
    name: Build
    runs-on: ubuntu-latest       # use GitHub's Ubuntu machine

    steps:
      # Step 1: Get your code onto the runner machine
      - name: Checkout code
        uses: actions/checkout@v4

      # Step 2: Set up the right Node.js version
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'           # cache node_modules to speed up future runs

      # Step 3: Install all packages
      - name: Install dependencies
        run: npm ci              # like npm install but faster & deterministic

      # Step 4: Compile TypeScript / build the app
      - name: Build app
        run: npm run build

      # Step 5: Save build output so the next job can use it
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: build-output
          path: dist/            # upload the dist folder

  # ────────────────────────────────
  # JOB 2: TEST
  # Runs ONLY after build succeeds
  # ────────────────────────────────
  test:
    name: Test
    runs-on: ubuntu-latest
    needs: build                 # ← waits for 'build' job to pass

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      # Download the built files from the previous job
      - name: Download build artifact
        uses: actions/download-artifact@v4
        with:
          name: build-output
          path: dist/

      # Run unit tests
      - name: Run unit tests
        run: npm test

      # Run tests with coverage report
      - name: Run tests with coverage
        run: npm run test:coverage

      # Upload coverage report to Codecov (optional)
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}

  # ────────────────────────────────
  # JOB 3: DEPLOY
  # Runs only on main branch, after tests pass
  # ────────────────────────────────
  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    needs: test                  # ← waits for 'test' job to pass

    # Only deploy when pushing to main — NOT on PRs
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    # Environment protection rules (optional — configure in GitHub settings)
    environment: production

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # Log in to Docker Hub using secrets stored in GitHub
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      # Build and push Docker image
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/${{ env.DOCKER_IMAGE }}:latest
            ${{ secrets.DOCKER_USERNAME }}/${{ env.DOCKER_IMAGE }}:${{ github.sha }}

      # SSH into your server and pull the new image
      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            docker pull ${{ secrets.DOCKER_USERNAME }}/${{ env.DOCKER_IMAGE }}:latest
            docker stop my-app || true
            docker run -d --name my-app -p 80:3000 \
              ${{ secrets.DOCKER_USERNAME }}/${{ env.DOCKER_IMAGE }}:latest
