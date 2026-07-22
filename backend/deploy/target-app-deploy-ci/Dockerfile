# CI image for apps-repo target-app:deploy (gitlab-apps-repo-ci.yml).
# Pre-bakes the per-job apt / Terraform / AWS CLI installs so before_script
# only does OIDC, clone, and pip requirements from the platform branch.
#
# Build + push (from backend/):
#   .\scripts\push-deploy-ci-ecr.ps1
#
# Pin TF_VERSION to match gitlab-apps-repo-ci.yml variables.TF_VERSION.
ARG TF_VERSION=1.10.5
ARG DOCKER_CLI_VERSION=24.0.9

FROM mcr.microsoft.com/powershell:7.4-debian-12

ARG TF_VERSION
ARG DOCKER_CLI_VERSION

USER root

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        ca-certificates \
        curl \
        unzip \
        git \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI only — juno-labs-3 bind-mounts the host daemon socket into jobs.
RUN curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
        -o /tmp/docker.tgz \
    && tar -xzf /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz \
    && docker --version

# AWS CLI v2 (same family as oidc:test's amazon/aws-cli image).
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip \
    && aws --version

# Terraform (pinned; bump ARG + image tag together when upgrading).
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" \
        -o /tmp/tf.zip \
    && unzip -q /tmp/tf.zip -d /usr/local/bin \
    && rm /tmp/tf.zip \
    && terraform -version

# Smoke-check tools the deploy job expects on PATH.
RUN python3 --version && pip3 --version && git --version
