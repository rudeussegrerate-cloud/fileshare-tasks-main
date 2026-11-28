"""Function calling with constrained decoding for small LLMs.

This package translates natural-language prompts into structured function
calls by driving a small local LLM token-by-token: at every generation step
the logits are masked so that only tokens keeping the output schema-valid
can be selected. See the project README for the full algorithm description.
"""
