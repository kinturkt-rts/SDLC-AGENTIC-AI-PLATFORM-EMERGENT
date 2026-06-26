"""SDLC pipeline orchestrator.

Sequentially invokes product -> architect -> database -> developer -> gitlab
agents using a pluggable transport (subprocess CLI today, A2A HTTP after the
agents are deployed to Bedrock AgentCore). Run state is persisted to
``agents/pipeline/<feature>.run.json`` so the frontend can show live progress.
"""
