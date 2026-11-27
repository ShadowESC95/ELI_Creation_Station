"""Provenance: what every asset was made with, recorded and marked.

Every asset gets a manifest (the models and their licences, the request, the seed, the assets it was
made from, the edits), an entry in ELI Legal's tamper-evident audit ledger (reused:
adapters/local/hmac_audit.py, an HMAC-SHA-256 chain with a head anchor beside its key), and, in the
file itself, the IPTC digital-source-type marking that says whether a trained model made it. That
machine-readable marking is what Article 50(2) of the EU AI Act asks of a provider of a system that
generates images, audio, video or text, and it cannot be switched off. A visible label is the
person's choice (Settings).
"""
