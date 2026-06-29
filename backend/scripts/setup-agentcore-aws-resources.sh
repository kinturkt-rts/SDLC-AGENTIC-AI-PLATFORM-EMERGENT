#!/usr/bin/env bash
# Create S3 + DynamoDB resources for AgentCore pipeline artifacts (manual bootstrap).
# Requires: aws CLI, authenticated credentials, explicit approval to create AWS resources.
set -euo pipefail

REGION="${AWS_REGION:-us-east-2}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${ARTIFACT_S3_BUCKET:-sdlc-agent-artifacts-${ACCOUNT_ID}-${REGION}}"
TABLE="${ARTIFACT_DYNAMODB_TABLE:-sdlc-pipeline-runs}"

echo "Region: ${REGION}"
echo "Account: ${ACCOUNT_ID}"
echo "S3 bucket: ${BUCKET}"
echo "DynamoDB table: ${TABLE}"

if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "S3 bucket already exists: ${BUCKET}"
else
  if [ "${REGION}" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket \
      --bucket "${BUCKET}" \
      --region "${REGION}" \
      --create-bucket-configuration "LocationConstraint=${REGION}"
  fi
  aws s3api put-bucket-versioning \
    --bucket "${BUCKET}" \
    --versioning-configuration Status=Enabled
  aws s3api put-bucket-encryption \
    --bucket "${BUCKET}" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  echo "Created S3 bucket: ${BUCKET}"
fi

if aws dynamodb describe-table --table-name "${TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "DynamoDB table already exists: ${TABLE}"
else
  aws dynamodb create-table \
    --table-name "${TABLE}" \
    --attribute-definitions \
      AttributeName=runId,AttributeType=S \
      AttributeName=artifactKey,AttributeType=S \
      AttributeName=targetApp,AttributeType=S \
      AttributeName=createdAt,AttributeType=S \
    --key-schema \
      AttributeName=runId,KeyType=HASH \
      AttributeName=artifactKey,KeyType=RANGE \
    --global-secondary-indexes \
      "IndexName=targetApp-index,KeySchema=[{AttributeName=targetApp,KeyType=HASH},{AttributeName=createdAt,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region "${REGION}"
  echo "Created DynamoDB table: ${TABLE}"
fi

cat <<EOF

Export these for agentcore deploy:
  ARTIFACT_STORE=s3
  ARTIFACT_S3_BUCKET=${BUCKET}
  ARTIFACT_DYNAMODB_TABLE=${TABLE}
  AWS_REGION=${REGION}

Attach to AgentCore execution role:
  - s3:PutObject, s3:GetObject, s3:ListBucket on arn:aws:s3:::${BUCKET}/runs/*
  - dynamodb:PutItem, dynamodb:GetItem, dynamodb:Query on table ${TABLE}
  - bedrock:InvokeModel
  - logs:CreateLogStream, logs:PutLogEvents

EOF
