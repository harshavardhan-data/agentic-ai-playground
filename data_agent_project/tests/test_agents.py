from datetime import datetime,timezone
from models.analysis import Finding, Evidence
from agents.coder import GeneratorAgent
from prompts.formatter import format_findings
from core.client import gemini_client

generator_agent=GeneratorAgent(client=gemini_client)
# 1. Create a fake Finding and Evidence object matching your ORM models
fake_evidence = Evidence(
    evidence_id="ev_test1234",
    origin="tool",
    type="stat",
    content_json={"check": "z_score_anomaly", "window": "7d"},
    result_json={
        "direction": "down",
        "magnitude": 0.3297,
        "current_mean": 12400.50,
        "baseline_mean": 18500.00,
        "pct_change": -32.97,
        "z_score": -3.42
    },
    direction="down",
    interpretation="Initial detection",
    supports=True,
    created_at=datetime.now()
)

fake_finding = Finding(
    finding_id="fnd_test9999",
    run_id="run_test_01",
    source_id="src_sales_db",
    fingerprint="xiw3291",
    category="anomaly",
    claim="", # Will be populated by generator
    metric="revenue",
    dimension="region",
    dimension_value="EU",
    current_direction="down",
    confidence=0.5,
    status="new",
    evidence=[fake_evidence]
)

# 2. Test your format_findings function directly to see how it renders
findings_list = [fake_finding]
formatted_output = format_findings(findings_list)

print("--- RENDERED FINDINGS TEXT ---")
print(formatted_output)
print("------------------------------")

# 3. Test your generator agent call individually
# (Assumes generator_agent is already initialized in your scope)
try:
    claims_map = generator_agent.generate_claims(
        findings=findings_list,
        source_name="Global Sales Database",
        run_date=datetime.now()
    )
    
    print("\n--- GENERATED CLAIM RESULT ---")
    print(f"Finding ID: {fake_finding.finding_id}")
    print(f"Generated Claim: {claims_map.get(fake_finding.finding_id)}")
    print("------------------------------")

except Exception as e:
    print(f"\n❌ Generator agent call failed: {e}")