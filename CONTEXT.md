# ADK 2.0 Global Development & Security Context

## Architecture Paradigm
Rule: All state transitions must use type-validated Pydantic models. No raw dictionary manipulation of the shared file bus.

## Security Guardrails
Rule 1: Zero Ambient Authority. External tools must run under gVisor kernel-isolated sandboxing wrappers.
Rule 2: High-stakes execution stages require a secure SHA-256 HMAC cryptographic signature verification turn via the local file bus.
Rule 3: Personal emails or identifiers must never be hardcoded; utilize generic corporate fallbacks with environment variables.

## Static Analysis Rules
Rule: Unsafe subprocess calls, hardcoded plaintext secret keys, or raw string equality tokens are strictly prohibited and will fail linter compilation.
