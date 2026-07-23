"""Placeholder — no Bedrock/LLM required for this app."""
# This file exists to prevent ImportError from health router's optional Bedrock probe.


def get_bedrock_client():
    raise NotImplementedError("Bedrock not used in student-management")
