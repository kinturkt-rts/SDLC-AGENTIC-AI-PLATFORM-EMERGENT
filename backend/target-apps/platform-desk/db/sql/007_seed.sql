-- Password for all seed API keys: "RunbookDesk2024!"
-- 007_seed.sql — Dev/test fixture data for Platform Desk
-- Follows design §6.2: 8-10 services, 12-15 runbooks, 60+ steps, 3 api_keys, 20+ search_events, 15+ incident_touches

SET search_path = platform_desk, public;

-- ============================================================
-- SERVICES (10 rows)
-- ============================================================
INSERT INTO platform_desk.services (id, name, owning_team, criticality_tier, active_support, created_at) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'payments-api', 'Payments Team', 1, TRUE, '2024-01-10 08:00:00+00'),
    ('a1000000-0000-0000-0000-000000000002', 'auth-gateway', 'Identity Team', 1, TRUE, '2024-01-10 08:05:00+00'),
    ('a1000000-0000-0000-0000-000000000003', 'order-service', 'Commerce Team', 2, TRUE, '2024-01-11 09:00:00+00'),
    ('a1000000-0000-0000-0000-000000000004', 'notification-hub', 'Messaging Team', 2, TRUE, '2024-01-12 10:00:00+00'),
    ('a1000000-0000-0000-0000-000000000005', 'inventory-tracker', 'Supply Chain Team', 2, TRUE, '2024-01-13 11:00:00+00'),
    ('a1000000-0000-0000-0000-000000000006', 'search-indexer', 'Platform Team', 3, TRUE, '2024-01-14 08:30:00+00'),
    ('a1000000-0000-0000-0000-000000000007', 'metrics-collector', 'Observability Team', 3, TRUE, '2024-01-15 09:00:00+00'),
    ('a1000000-0000-0000-0000-000000000008', 'cdn-edge-proxy', 'Networking Team', 1, TRUE, '2024-01-16 10:00:00+00'),
    ('a1000000-0000-0000-0000-000000000009', 'ml-inference-svc', 'ML Engineering', 2, FALSE, '2024-01-17 11:00:00+00'),
    ('a1000000-0000-0000-0000-00000000000a', 'data-pipeline', 'Data Engineering', 3, TRUE, '2024-01-18 12:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- RUNBOOKS (15 rows — mix of draft/active/retired)
-- ============================================================
INSERT INTO platform_desk.runbooks (id, title, service_id, default_severity, short_summary, author, lifecycle_status, created_at, updated_at) VALUES
    ('b2000000-0000-0000-0000-000000000001', 'Redis Connection Pool Recovery', 'a1000000-0000-0000-0000-000000000001', 'high', 'Steps to recover from Redis connection pool exhaustion in payments-api', 'alice.chen', 'active', '2024-02-01 08:00:00+00', '2024-02-15 10:00:00+00'),
    ('b2000000-0000-0000-0000-000000000002', 'Database Failover Procedure', 'a1000000-0000-0000-0000-000000000001', 'critical', 'Primary to replica failover for payments database', 'bob.martinez', 'active', '2024-02-02 09:00:00+00', '2024-02-20 11:00:00+00'),
    ('b2000000-0000-0000-0000-000000000003', 'JWT Token Rotation', 'a1000000-0000-0000-0000-000000000002', 'medium', 'Rotate JWT signing keys without downtime', 'carol.wu', 'active', '2024-02-03 10:00:00+00', '2024-02-25 12:00:00+00'),
    ('b2000000-0000-0000-0000-000000000004', 'Kafka Consumer Lag Remediation', 'a1000000-0000-0000-0000-000000000003', 'high', 'Handle consumer group lag spikes in order processing', 'dave.kim', 'active', '2024-02-04 11:00:00+00', '2024-03-01 09:00:00+00'),
    ('b2000000-0000-0000-0000-000000000005', 'Email Queue Drain', 'a1000000-0000-0000-0000-000000000004', 'medium', 'Clear blocked email notification queue', 'eve.johnson', 'active', '2024-02-05 08:30:00+00', '2024-03-05 14:00:00+00'),
    ('b2000000-0000-0000-0000-000000000006', 'Inventory Sync Failure', 'a1000000-0000-0000-0000-000000000005', 'high', 'Recover from warehouse inventory sync failures', 'frank.lee', 'active', '2024-02-06 09:30:00+00', '2024-03-10 10:00:00+00'),
    ('b2000000-0000-0000-0000-000000000007', 'Elasticsearch Index Corruption', 'a1000000-0000-0000-0000-000000000006', 'critical', 'Rebuild corrupted search indices from primary store', 'grace.patel', 'active', '2024-02-07 10:30:00+00', '2024-03-12 15:00:00+00'),
    ('b2000000-0000-0000-0000-000000000008', 'Prometheus OOM Recovery', 'a1000000-0000-0000-0000-000000000007', 'high', 'Recover metrics collector after out-of-memory kill', 'henry.nguyen', 'active', '2024-02-08 11:30:00+00', '2024-03-15 08:00:00+00'),
    ('b2000000-0000-0000-0000-000000000009', 'CDN Cache Invalidation', 'a1000000-0000-0000-0000-000000000008', 'medium', 'Force-purge stale CDN cache across all edge nodes', 'iris.zhao', 'active', '2024-02-09 12:00:00+00', '2024-03-18 09:00:00+00'),
    ('b2000000-0000-0000-0000-00000000000a', 'Model Rollback Procedure', 'a1000000-0000-0000-0000-000000000009', 'high', 'Roll back ML model deployment to previous version', 'jack.brown', 'active', '2024-02-10 08:00:00+00', '2024-03-20 10:00:00+00'),
    ('b2000000-0000-0000-0000-00000000000b', 'Spark Job Failure Triage', 'a1000000-0000-0000-0000-00000000000a', 'medium', 'Diagnose and restart failed Spark ETL jobs', 'karen.davis', 'active', '2024-02-11 09:00:00+00', '2024-03-22 11:00:00+00'),
    ('b2000000-0000-0000-0000-00000000000c', 'Redis Cluster Rebalance', 'a1000000-0000-0000-0000-000000000001', 'medium', 'Rebalance Redis cluster slots after node addition', 'alice.chen', 'draft', '2024-03-01 08:00:00+00', '2024-03-25 10:00:00+00'),
    ('b2000000-0000-0000-0000-00000000000d', 'Legacy Auth Migration', 'a1000000-0000-0000-0000-000000000002', 'low', 'Migrate users from legacy auth to new gateway', 'carol.wu', 'retired', '2023-06-01 08:00:00+00', '2024-01-15 09:00:00+00'),
    ('b2000000-0000-0000-0000-00000000000e', 'Order DB Connection Pool Tuning', 'a1000000-0000-0000-0000-000000000003', 'medium', 'Tune HikariCP connection pool for order-service', 'dave.kim', 'draft', '2024-03-10 08:00:00+00', '2024-03-28 12:00:00+00'),
    ('b2000000-0000-0000-0000-00000000000f', 'CDN Origin Shield Failover', 'a1000000-0000-0000-0000-000000000008', 'critical', 'Failover to secondary origin when primary is unreachable', 'iris.zhao', 'retired', '2023-08-01 10:00:00+00', '2024-02-01 08:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- RUNBOOK STEPS (65 rows — realistic SRE content)
-- ============================================================
INSERT INTO platform_desk.runbook_steps (id, runbook_id, step_number, title, body_text, estimated_minutes, warning_callout) VALUES
    -- Redis Connection Pool Recovery (5 steps)
    ('c3000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 1, 'Verify alert source', 'Check PagerDuty alert details. Confirm the alert originated from payments-api Redis connection metrics. Verify the connection pool utilization is above 90% in Grafana dashboard "Payments Redis" panel.', 2, NULL),
    ('c3000000-0000-0000-0000-000000000002', 'b2000000-0000-0000-0000-000000000001', 2, 'Check Redis server health', 'SSH to Redis primary (redis-payments-01). Run redis-cli INFO clients to check connected_clients count. Compare against maxclients setting. Check memory usage with INFO memory.', 3, 'Do NOT restart Redis without confirming no active transactions are in flight.'),
    ('c3000000-0000-0000-0000-000000000003', 'b2000000-0000-0000-0000-000000000001', 3, 'Identify connection leaks', 'Review payments-api application logs for connection timeout errors. Check for long-running commands with redis-cli CLIENT LIST filtering by age > 300 seconds. Correlate with recent deployments.', 5, NULL),
    ('c3000000-0000-0000-0000-000000000004', 'b2000000-0000-0000-0000-000000000001', 4, 'Kill idle connections', 'Run redis-cli CLIENT KILL ID <id> for connections idle > 600s that are not from critical background jobs. Monitor pool utilization dropping in real-time.', 3, 'Only kill connections idle > 600s. Active connections may be mid-transaction.'),
    ('c3000000-0000-0000-0000-000000000005', 'b2000000-0000-0000-0000-000000000001', 5, 'Restart affected pods', 'If pool remains saturated after killing idle connections, perform a rolling restart of payments-api pods: kubectl rollout restart deployment/payments-api -n payments. Monitor new pod readiness.', 5, NULL),

    -- Database Failover Procedure (5 steps)
    ('c3000000-0000-0000-0000-000000000006', 'b2000000-0000-0000-0000-000000000002', 1, 'Confirm primary failure', 'Verify the primary database is truly unreachable. Check RDS console for instance status. Attempt pg_isready from bastion host. Rule out network partition by checking from multiple AZs.', 3, 'Ensure this is a real failure, not a monitoring false positive. Check from at least 2 sources.'),
    ('c3000000-0000-0000-0000-000000000007', 'b2000000-0000-0000-0000-000000000002', 2, 'Notify stakeholders', 'Page payments-team-leads in #payments-incidents Slack channel. Post incident timeline start. Set incident status to SEV-1 in status page.', 2, NULL),
    ('c3000000-0000-0000-0000-000000000008', 'b2000000-0000-0000-0000-000000000002', 3, 'Promote read replica', 'In AWS RDS console, select the read replica payments-db-replica-01. Click Actions > Promote. Confirm the promotion. Wait for instance status to change to "available" (typically 2-5 minutes).', 5, 'This action is irreversible. The replica becomes a standalone instance.'),
    ('c3000000-0000-0000-0000-000000000009', 'b2000000-0000-0000-0000-000000000002', 4, 'Update connection string', 'Update the DATABASE_URL in payments-api secrets: kubectl edit secret payments-db-secret -n payments. Replace the endpoint with the newly promoted instance endpoint. Trigger rolling restart.', 5, NULL),
    ('c3000000-0000-0000-0000-00000000000a', 'b2000000-0000-0000-0000-000000000002', 5, 'Verify transactions flowing', 'Monitor the payments-api health endpoint and transaction success rate in Grafana. Confirm no 5xx errors related to database connectivity. Run a test transaction in staging environment.', 3, NULL),

    -- JWT Token Rotation (4 steps)
    ('c3000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000003', 1, 'Generate new signing key', 'Use openssl to generate a new RSA-256 key pair: openssl genrsa -out new-jwt-key.pem 2048. Store the private key securely in AWS Secrets Manager under auth-gateway/jwt-signing-key-v2.', 3, NULL),
    ('c3000000-0000-0000-0000-00000000000c', 'b2000000-0000-0000-0000-000000000003', 2, 'Deploy with dual-key validation', 'Update auth-gateway configuration to accept tokens signed by BOTH the old and new keys. Deploy the updated config: kubectl apply -f auth-gateway-config.yaml. Verify both old and new tokens validate.', 5, 'Both keys must validate simultaneously during rotation window.'),
    ('c3000000-0000-0000-0000-00000000000d', 'b2000000-0000-0000-0000-000000000003', 3, 'Switch signing to new key', 'Update the JWT_SIGNING_KEY environment variable to point to the new key. All newly issued tokens will use the new key. Old tokens remain valid until expiry (configured TTL).', 3, NULL),
    ('c3000000-0000-0000-0000-00000000000e', 'b2000000-0000-0000-0000-000000000003', 4, 'Remove old key after TTL', 'After the maximum token TTL has elapsed (default 24h), remove the old key from the validation set. Deploy config update. Archive old key in Secrets Manager with "rotated" tag.', 2, 'Wait the FULL token TTL before removing old key. Premature removal causes mass 401 errors.'),

    -- Kafka Consumer Lag Remediation (5 steps)
    ('c3000000-0000-0000-0000-00000000000f', 'b2000000-0000-0000-0000-000000000004', 1, 'Assess lag severity', 'Check Kafka consumer group lag in Burrow or kafka-consumer-groups.sh --describe. Identify which partitions have the most lag. Calculate estimated time to catch up at current throughput rate.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000010', 'b2000000-0000-0000-0000-000000000004', 2, 'Check consumer health', 'Verify all consumer instances are running: kubectl get pods -l app=order-consumer -n commerce. Check for OOMKilled or CrashLoopBackoff status. Review consumer logs for deserialization errors.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000011', 'b2000000-0000-0000-0000-000000000004', 3, 'Scale consumer group', 'If consumers are healthy but throughput is insufficient, scale the consumer deployment: kubectl scale deployment/order-consumer --replicas=6 -n commerce. Ensure replica count does not exceed partition count.', 3, 'Never scale consumers beyond the number of topic partitions. Extra replicas will be idle.'),
    ('c3000000-0000-0000-0000-000000000012', 'b2000000-0000-0000-0000-000000000004', 4, 'Investigate upstream spike', 'Check producer metrics for the order-events topic. Look for unusual traffic spike from order-service. Correlate with marketing campaigns or flash sales that may have increased order volume.', 5, NULL),
    ('c3000000-0000-0000-0000-000000000013', 'b2000000-0000-0000-0000-000000000004', 5, 'Monitor recovery', 'Watch lag metrics decrease over time. Expected recovery: lag should halve every 5 minutes with scaled consumers. If lag is not decreasing, check for poison pill messages blocking partitions.', 5, NULL),

    -- Email Queue Drain (4 steps)
    ('c3000000-0000-0000-0000-000000000014', 'b2000000-0000-0000-0000-000000000005', 1, 'Identify queue depth', 'Check the notification-hub SQS queue depth in AWS console. If dead-letter queue has messages, inspect sample messages for common error patterns.', 2, NULL),
    ('c3000000-0000-0000-0000-000000000015', 'b2000000-0000-0000-0000-000000000005', 2, 'Check SES sending limits', 'Verify AWS SES is not throttling. Check SES dashboard for bounce rate and complaint rate. If either exceeds 5%, pause sending immediately and investigate root cause.', 3, 'If bounce rate > 5%, do NOT force-drain. Contact messaging-team lead first.'),
    ('c3000000-0000-0000-0000-000000000016', 'b2000000-0000-0000-0000-000000000005', 3, 'Restart notification workers', 'Perform rolling restart of notification workers: kubectl rollout restart deployment/notification-worker -n messaging. Monitor processing rate in CloudWatch metrics.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000017', 'b2000000-0000-0000-0000-000000000005', 4, 'Purge stale messages', 'If messages are older than 24h and no longer relevant (e.g., time-sensitive notifications), purge the DLQ after archiving: aws sqs purge-queue --queue-url <dlq-url>.', 2, 'Archive DLQ messages to S3 before purging. Messages cannot be recovered after purge.'),

    -- Inventory Sync Failure (4 steps)
    ('c3000000-0000-0000-0000-000000000018', 'b2000000-0000-0000-0000-000000000006', 1, 'Check sync job status', 'Review the inventory-sync CronJob in Kubernetes: kubectl get cronjobs -n supply-chain. Check the last run status and logs: kubectl logs job/inventory-sync-<timestamp> -n supply-chain.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000019', 'b2000000-0000-0000-0000-000000000006', 2, 'Verify warehouse API connectivity', 'Test connectivity to the external warehouse API endpoint from within the cluster. Run a curl test pod: kubectl run curl-test --image=curlimages/curl -- curl -v https://warehouse-api.partner.com/health.', 3, NULL),
    ('c3000000-0000-0000-0000-00000000001a', 'b2000000-0000-0000-0000-000000000006', 3, 'Retry failed batch', 'Trigger a manual sync run: kubectl create job inventory-sync-manual --from=cronjob/inventory-sync -n supply-chain. Monitor logs for completion. Verify inventory counts updated in DB.', 5, NULL),
    ('c3000000-0000-0000-0000-00000000001b', 'b2000000-0000-0000-0000-000000000006', 4, 'Reconcile discrepancies', 'Run the inventory reconciliation script: python scripts/reconcile_inventory.py --source=warehouse --target=local. Review diff report and apply corrections for any items with delta > 10 units.', 5, 'Reconciliation modifies live inventory counts. Run during low-traffic window only.'),

    -- Elasticsearch Index Corruption (5 steps)
    ('c3000000-0000-0000-0000-00000000001c', 'b2000000-0000-0000-0000-000000000007', 1, 'Identify corrupted shards', 'Run GET _cluster/health and GET _cat/shards?v to identify RED or UNASSIGNED shards. Note the affected index names and shard numbers.', 2, NULL),
    ('c3000000-0000-0000-0000-00000000001d', 'b2000000-0000-0000-0000-000000000007', 2, 'Attempt shard reallocation', 'Try reassigning unassigned shards: POST _cluster/reroute with allocate_stale_primary or allocate_empty_primary. Accept data loss flag only if replicas are also corrupted.', 5, 'allocate_empty_primary results in data loss for that shard. Use only as last resort.'),
    ('c3000000-0000-0000-0000-00000000001e', 'b2000000-0000-0000-0000-000000000007', 3, 'Close and reopen index', 'If reallocation fails, close the index: POST /affected-index/_close. Then reopen: POST /affected-index/_open. This triggers shard recovery from translog.', 3, NULL),
    ('c3000000-0000-0000-0000-00000000001f', 'b2000000-0000-0000-0000-000000000007', 4, 'Reindex from source', 'If recovery fails, trigger full reindex from the source PostgreSQL database. Run the reindex job: kubectl create job search-reindex-manual --from=cronjob/search-full-reindex -n platform.', 10, NULL),
    ('c3000000-0000-0000-0000-000000000020', 'b2000000-0000-0000-0000-000000000007', 5, 'Validate search results', 'Run the search validation suite: pytest tests/search_validation/ -v. Verify result counts match expected baselines. Spot-check 5 known queries for correct top results.', 5, NULL),

    -- Prometheus OOM Recovery (4 steps)
    ('c3000000-0000-0000-0000-000000000021', 'b2000000-0000-0000-0000-000000000008', 1, 'Confirm OOM kill', 'Check pod events: kubectl describe pod prometheus-server-0 -n monitoring. Look for OOMKilled reason. Check node memory pressure: kubectl top nodes.', 2, NULL),
    ('c3000000-0000-0000-0000-000000000022', 'b2000000-0000-0000-0000-000000000008', 2, 'Increase memory limits', 'Edit the Prometheus StatefulSet to increase memory limits: kubectl edit statefulset prometheus-server -n monitoring. Recommended: increase by 50% from current limit. Apply and wait for pod restart.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000023', 'b2000000-0000-0000-0000-000000000008', 3, 'Reduce cardinality', 'Identify high-cardinality metrics causing memory bloat. Check TSDB status: curl localhost:9090/api/v1/status/tsdb. Drop unused metrics with relabeling rules in prometheus.yml.', 10, NULL),
    ('c3000000-0000-0000-0000-000000000024', 'b2000000-0000-0000-0000-000000000008', 4, 'Verify data continuity', 'After restart, check for gaps in metric data. Query rate(http_requests_total[5m]) and verify no extended null periods. If gaps exist, they are expected during the OOM window.', 3, NULL),

    -- CDN Cache Invalidation (4 steps)
    ('c3000000-0000-0000-0000-000000000025', 'b2000000-0000-0000-0000-000000000009', 1, 'Identify stale content', 'Determine which paths need invalidation. Check the CDN origin for updated content. Use curl with Host header to verify origin serves fresh content but edge returns stale.', 2, NULL),
    ('c3000000-0000-0000-0000-000000000026', 'b2000000-0000-0000-0000-000000000009', 2, 'Create invalidation batch', 'Log into CloudFront console. Create invalidation with path patterns (e.g., /api/v1/products/* or specific paths). For > 15 paths, use wildcard invalidation to stay within rate limits.', 3, 'Wildcard invalidations count as one path but invalidate all matching objects. Use judiciously.'),
    ('c3000000-0000-0000-0000-000000000027', 'b2000000-0000-0000-0000-000000000009', 3, 'Monitor propagation', 'Check invalidation status in CloudFront console. Status changes from InProgress to Completed. Full propagation typically takes 5-10 minutes across all edge locations.', 5, NULL),
    ('c3000000-0000-0000-0000-000000000028', 'b2000000-0000-0000-0000-000000000009', 4, 'Verify from edge', 'Use curl from multiple geographic regions (or CloudFront testing tool) to confirm fresh content is served. Check x-cache header shows "Miss from cloudfront" on first request.', 3, NULL),

    -- Model Rollback Procedure (5 steps)
    ('c3000000-0000-0000-0000-000000000029', 'b2000000-0000-0000-0000-00000000000a', 1, 'Identify failing model version', 'Check SageMaker endpoint metrics for error rate spike. Identify the current model version from endpoint config. Cross-reference with the last deployment timestamp in CI/CD pipeline.', 3, NULL),
    ('c3000000-0000-0000-0000-00000000002a', 'b2000000-0000-0000-0000-00000000000a', 2, 'Locate previous model artifact', 'Find the previous working model artifact in S3: aws s3 ls s3://ml-models/inference-svc/ --recursive | sort | tail -5. Identify the artifact from the last successful deployment.', 2, NULL),
    ('c3000000-0000-0000-0000-00000000002b', 'b2000000-0000-0000-0000-00000000000a', 3, 'Update endpoint configuration', 'Create a new endpoint config pointing to the previous model: aws sagemaker create-endpoint-config --endpoint-config-name rollback-config --production-variants ... Update the endpoint to use the new config.', 5, NULL),
    ('c3000000-0000-0000-0000-00000000002c', 'b2000000-0000-0000-0000-00000000000a', 4, 'Verify rollback', 'Send test inference requests to the endpoint. Compare predictions against known-good baseline. Monitor error rate dropping in CloudWatch metrics. Confirm latency is within acceptable range.', 5, NULL),
    ('c3000000-0000-0000-0000-00000000002d', 'b2000000-0000-0000-0000-00000000000a', 5, 'Post-mortem and lock deploy', 'Lock the ML deployment pipeline to prevent accidental re-deployment of the bad model. Create a post-mortem ticket. Notify the ML team with the model version that failed and observed symptoms.', 3, NULL),

    -- Spark Job Failure Triage (5 steps)
    ('c3000000-0000-0000-0000-00000000002e', 'b2000000-0000-0000-0000-00000000000b', 1, 'Check Spark UI for failed stage', 'Access Spark History Server UI. Find the failed application. Identify the failed stage and task. Look for common errors: OOM, shuffle fetch failure, or data skew.', 3, NULL),
    ('c3000000-0000-0000-0000-00000000002f', 'b2000000-0000-0000-0000-00000000000b', 2, 'Review executor logs', 'Download executor logs from S3 or YARN. Search for exceptions: OutOfMemoryError, FileNotFoundException, or connection timeouts to external sources.', 5, NULL),
    ('c3000000-0000-0000-0000-000000000030', 'b2000000-0000-0000-0000-00000000000b', 3, 'Check input data quality', 'Verify input data in S3 is not corrupted. Check file sizes and counts match expected. Run a quick schema validation on a sample: spark.read.parquet("s3://...").printSchema()', 5, NULL),
    ('c3000000-0000-0000-0000-000000000031', 'b2000000-0000-0000-0000-00000000000b', 4, 'Adjust resources and retry', 'If OOM: increase executor memory in job config. If shuffle failure: increase spark.sql.shuffle.partitions. Resubmit the job with adjusted parameters.', 5, NULL),
    ('c3000000-0000-0000-0000-000000000032', 'b2000000-0000-0000-0000-00000000000b', 5, 'Verify output and downstream', 'After successful retry, verify output data in target table/S3 path. Check row counts match expected. Trigger downstream dependent jobs if they were blocked.', 3, NULL),

    -- Redis Cluster Rebalance - draft (3 steps)
    ('c3000000-0000-0000-0000-000000000033', 'b2000000-0000-0000-0000-00000000000c', 1, 'Add new node to cluster', 'Join the new Redis node to the existing cluster using redis-cli --cluster add-node <new-ip>:6379 <existing-node-ip>:6379. Verify the node appears in cluster nodes output.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000034', 'b2000000-0000-0000-0000-00000000000c', 2, 'Rebalance slots', 'Run redis-cli --cluster rebalance <any-node-ip>:6379 --cluster-use-empty-masters. Monitor slot migration progress. This may take several minutes for large datasets.', 10, 'Rebalancing causes brief latency spikes. Run during maintenance window.'),
    ('c3000000-0000-0000-0000-000000000035', 'b2000000-0000-0000-0000-00000000000c', 3, 'Verify cluster health', 'Run redis-cli --cluster check <node-ip>:6379. All slots should be assigned. No slots in migrating/importing state. Run CLUSTER INFO and verify cluster_state:ok.', 2, NULL),

    -- Legacy Auth Migration - retired (2 steps)
    ('c3000000-0000-0000-0000-000000000036', 'b2000000-0000-0000-0000-00000000000d', 1, 'Export legacy user records', 'Run the legacy auth export script to dump user records to CSV. Validate record count matches the legacy DB user table count.', 5, NULL),
    ('c3000000-0000-0000-0000-000000000037', 'b2000000-0000-0000-0000-00000000000d', 2, 'Import to new auth gateway', 'Run the import script against the new auth-gateway API. Verify imported count matches exported count. Spot-check 10 random users can authenticate with existing credentials.', 10, NULL),

    -- Order DB Connection Pool Tuning - draft (3 steps)
    ('c3000000-0000-0000-0000-000000000038', 'b2000000-0000-0000-0000-00000000000e', 1, 'Baseline current pool metrics', 'Connect to order-service metrics endpoint and record current HikariCP pool stats: active connections, idle connections, pending threads, connection timeout count.', 3, NULL),
    ('c3000000-0000-0000-0000-000000000039', 'b2000000-0000-0000-0000-00000000000e', 2, 'Calculate optimal pool size', 'Use the formula: pool_size = (core_count * 2) + effective_spindle_count. For our 4-core RDS instance with SSDs, target pool size = 10. Adjust maximumPoolSize in application.yml.', 2, NULL),
    ('c3000000-0000-0000-0000-00000000003a', 'b2000000-0000-0000-0000-00000000000e', 3, 'Deploy and validate', 'Deploy the updated config to staging first. Run load tests and compare connection wait times against baseline. If improved, promote to production during low-traffic window.', 5, NULL),

    -- CDN Origin Shield Failover - retired (3 steps)
    ('c3000000-0000-0000-0000-00000000003b', 'b2000000-0000-0000-0000-00000000000f', 1, 'Detect origin failure', 'Monitor origin health checks in CloudFront. When 5xx error rate from origin exceeds 50% for 2 consecutive minutes, begin failover procedure.', 2, NULL),
    ('c3000000-0000-0000-0000-00000000003c', 'b2000000-0000-0000-0000-00000000000f', 2, 'Switch to secondary origin', 'Update CloudFront distribution origin to point to secondary origin endpoint. Apply changes via AWS CLI for speed: aws cloudfront update-distribution --id <dist-id> --distribution-config file://failover-config.json.', 5, NULL),
    ('c3000000-0000-0000-0000-00000000003d', 'b2000000-0000-0000-0000-00000000000f', 3, 'Validate and communicate', 'Verify requests are flowing to secondary origin. Check access logs for new origin IP. Post update to #cdn-ops channel with ETA for primary restoration.', 3, NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- API KEYS (3 rows — one per role; use __BCRYPT_PLACEHOLDER__ for key_hash)
-- ============================================================
INSERT INTO platform_desk.api_keys (id, key_hash, role, label, active, created_at) VALUES
    ('d4000000-0000-0000-0000-000000000001', '__BCRYPT_PLACEHOLDER_VIEWER__', 'viewer', 'dev-viewer-key', TRUE, '2024-01-20 08:00:00+00'),
    ('d4000000-0000-0000-0000-000000000002', '__BCRYPT_PLACEHOLDER_EDITOR__', 'editor', 'dev-editor-key', TRUE, '2024-01-20 08:00:00+00'),
    ('d4000000-0000-0000-0000-000000000003', '__BCRYPT_PLACEHOLDER_ADMIN__', 'admin', 'dev-admin-key', TRUE, '2024-01-20 08:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- SEARCH EVENTS (20 rows)
-- ============================================================
INSERT INTO platform_desk.search_events (id, query_text, service_filter_id, result_count, top_score, response_time_ms, created_at) VALUES
    ('e5000000-0000-0000-0000-000000000001', 'Redis connection pool exhausted', 'a1000000-0000-0000-0000-000000000001', 3, 0.92, 245, '2024-03-01 14:00:00+00'),
    ('e5000000-0000-0000-0000-000000000002', 'database failover steps', NULL, 2, 0.88, 312, '2024-03-02 09:30:00+00'),
    ('e5000000-0000-0000-0000-000000000003', 'kafka consumer lag high', 'a1000000-0000-0000-0000-000000000003', 2, 0.85, 198, '2024-03-03 16:45:00+00'),
    ('e5000000-0000-0000-0000-000000000004', 'JWT token expired how to rotate', NULL, 1, 0.79, 267, '2024-03-04 11:00:00+00'),
    ('e5000000-0000-0000-0000-000000000005', 'email notifications stuck in queue', 'a1000000-0000-0000-0000-000000000004', 2, 0.91, 189, '2024-03-05 08:15:00+00'),
    ('e5000000-0000-0000-0000-000000000006', 'elasticsearch red cluster status', NULL, 3, 0.87, 334, '2024-03-06 22:30:00+00'),
    ('e5000000-0000-0000-0000-000000000007', 'prometheus out of memory killed', 'a1000000-0000-0000-0000-000000000007', 1, 0.93, 156, '2024-03-07 03:45:00+00'),
    ('e5000000-0000-0000-0000-000000000008', 'CDN serving stale content', 'a1000000-0000-0000-0000-000000000008', 2, 0.82, 278, '2024-03-08 12:00:00+00'),
    ('e5000000-0000-0000-0000-000000000009', 'ML model inference errors spike', 'a1000000-0000-0000-0000-000000000009', 1, 0.76, 445, '2024-03-09 15:30:00+00'),
    ('e5000000-0000-0000-0000-00000000000a', 'spark job failed shuffle', 'a1000000-0000-0000-0000-00000000000a', 2, 0.84, 223, '2024-03-10 10:00:00+00'),
    ('e5000000-0000-0000-0000-00000000000b', 'connection timeout payments', NULL, 2, 0.72, 301, '2024-03-11 19:00:00+00'),
    ('e5000000-0000-0000-0000-00000000000c', 'how to restart notification workers', NULL, 1, 0.68, 189, '2024-03-12 07:30:00+00'),
    ('e5000000-0000-0000-0000-00000000000d', 'inventory count mismatch warehouse', NULL, 1, 0.81, 267, '2024-03-13 14:15:00+00'),
    ('e5000000-0000-0000-0000-00000000000e', 'search index rebuild procedure', 'a1000000-0000-0000-0000-000000000006', 2, 0.89, 178, '2024-03-14 09:45:00+00'),
    ('e5000000-0000-0000-0000-00000000000f', 'kubernetes pod crashloopbackoff', NULL, 0, 0.32, 156, '2024-03-15 11:30:00+00'),
    ('e5000000-0000-0000-0000-000000000010', 'network partition detection', NULL, 0, 0.28, 134, '2024-03-16 04:00:00+00'),
    ('e5000000-0000-0000-0000-000000000011', 'Redis connection pool exhausted', 'a1000000-0000-0000-0000-000000000001', 3, 0.94, 201, '2024-03-17 20:00:00+00'),
    ('e5000000-0000-0000-0000-000000000012', 'SES bounce rate too high', 'a1000000-0000-0000-0000-000000000004', 1, 0.73, 289, '2024-03-18 13:00:00+00'),
    ('e5000000-0000-0000-0000-000000000013', 'database connection pool tuning', NULL, 2, 0.71, 267, '2024-03-19 16:30:00+00'),
    ('e5000000-0000-0000-0000-000000000014', 'CDN origin unreachable failover', 'a1000000-0000-0000-0000-000000000008', 1, 0.86, 312, '2024-03-20 08:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- INCIDENT TOUCHES (15 rows)
-- ============================================================
INSERT INTO platform_desk.incident_touches (id, runbook_id, step_number, ticket_reference, notes, role, created_at) VALUES
    ('f6000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 4, 'INC-4401', 'Killed 12 idle connections, pool recovered to 45% utilization', 'viewer', '2024-03-01 14:15:00+00'),
    ('f6000000-0000-0000-0000-000000000002', 'b2000000-0000-0000-0000-000000000001', 5, 'INC-4401', 'Also restarted 2 pods that had stale connections', 'viewer', '2024-03-01 14:30:00+00'),
    ('f6000000-0000-0000-0000-000000000003', 'b2000000-0000-0000-0000-000000000002', 3, 'INC-4455', 'Promoted replica successfully, 3 min downtime', 'editor', '2024-03-02 10:00:00+00'),
    ('f6000000-0000-0000-0000-000000000004', 'b2000000-0000-0000-0000-000000000004', 3, 'INC-4480', 'Scaled from 3 to 6 consumers, lag cleared in 8 minutes', 'viewer', '2024-03-03 17:00:00+00'),
    ('f6000000-0000-0000-0000-000000000005', 'b2000000-0000-0000-0000-000000000005', 3, 'INC-4512', NULL, 'viewer', '2024-03-05 08:45:00+00'),
    ('f6000000-0000-0000-0000-000000000006', 'b2000000-0000-0000-0000-000000000007', 4, 'INC-4530', 'Full reindex took 45 minutes for 3 indices', 'editor', '2024-03-06 23:30:00+00'),
    ('f6000000-0000-0000-0000-000000000007', 'b2000000-0000-0000-0000-000000000008', 2, 'INC-4545', 'Increased memory from 8Gi to 12Gi', 'viewer', '2024-03-07 04:00:00+00'),
    ('f6000000-0000-0000-0000-000000000008', 'b2000000-0000-0000-0000-000000000009', 2, 'INC-4560', 'Invalidated /api/v1/products/* path pattern', 'viewer', '2024-03-08 12:30:00+00'),
    ('f6000000-0000-0000-0000-000000000009', 'b2000000-0000-0000-0000-00000000000a', 3, 'INC-4578', 'Rolled back from v2.3.1 to v2.2.9', 'editor', '2024-03-09 16:00:00+00'),
    ('f6000000-0000-0000-0000-00000000000a', 'b2000000-0000-0000-0000-00000000000b', 4, 'INC-4590', 'Increased spark.executor.memory to 8g and retried', 'viewer', '2024-03-10 10:30:00+00'),
    ('f6000000-0000-0000-0000-00000000000b', 'b2000000-0000-0000-0000-000000000001', 2, 'INC-4612', 'Redis primary was healthy, issue was in app connection config', 'viewer', '2024-03-17 20:30:00+00'),
    ('f6000000-0000-0000-0000-00000000000c', 'b2000000-0000-0000-0000-000000000004', 1, 'INC-4625', 'Lag was 2M messages, estimated 20 min catch-up', 'viewer', '2024-03-18 09:00:00+00'),
    ('f6000000-0000-0000-0000-00000000000d', 'b2000000-0000-0000-0000-000000000006', 2, 'INC-4640', 'Warehouse API returned 503, contacted partner team', 'editor', '2024-03-19 11:00:00+00'),
    ('f6000000-0000-0000-0000-00000000000e', 'b2000000-0000-0000-0000-000000000003', 4, 'INC-4655', NULL, 'viewer', '2024-03-20 14:00:00+00'),
    ('f6000000-0000-0000-0000-00000000000f', 'b2000000-0000-0000-0000-000000000002', 1, 'INC-4670', 'False alarm — monitoring blip, primary was reachable from bastion', 'viewer', '2024-03-21 06:00:00+00')
ON CONFLICT DO NOTHING;
