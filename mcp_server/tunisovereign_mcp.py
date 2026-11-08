try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class FastMCP:
        '''Lightweight fallback decorator shim when running outside the Docker/MCP venv.'''
        def __init__(self, name: str):
            self.name = name
        def resource(self, uri: str):
            def decorator(fn):
                return fn
            return decorator
        def tool(self):
            def decorator(fn):
                return fn
            return decorator
        def prompt(self):
            def decorator(fn):
                return fn
            return decorator
        def run(self):
            print(f"[{self.name}] FastMCP Server initialized (install 'mcp' package for stdio/SSE transport).")

mcp = FastMCP("TuniSovereign-MCP-Server")

GOVERNORATE_POLICIES = {
    "Kasserine": {"max_daily_quota": 4200.0, "critical_threshold": 35.0, "priority_tier": "Priority-A (Interior Aquifer)"},
    "Sidi_Bouzid": {"max_daily_quota": 4500.0, "critical_threshold": 33.0, "priority_tier": "Priority-A (Agricultural Basin)"},
    "Gafsa": {"max_daily_quota": 3800.0, "critical_threshold": 36.0, "priority_tier": "Priority-A (Mining & Oasis Basin)"},
    "Kairouan": {"max_daily_quota": 4400.0, "critical_threshold": 34.0, "priority_tier": "Priority-A (Central Plain)"},
    "Tozeur": {"max_daily_quota": 4000.0, "critical_threshold": 35.0, "priority_tier": "Priority-A (Southern Oasis / Solar)"},
    "Tunis": {"max_daily_quota": 5000.0, "critical_threshold": 30.0, "priority_tier": "Standard-Urban"},
}


@mcp.resource("tunisovereign://governorate/{governorate}/quota-policy")
def get_governorate_quota_policy(governorate: str) -> dict:
    '''Exposes official Tunisian governorate resource quota rules and thresholds.'''
    return GOVERNORATE_POLICIES.get(
        governorate,
        {"max_daily_quota": 4000.0, "critical_threshold": 35.0, "priority_tier": "Standard"},
    )


@mcp.tool()
def calculate_sovereign_quota_allocation(
    governorate: str,
    current_metric_value: float,
    ambient_temp_c: float = 31.0,
    requested_units: float = 1200.0,
) -> dict:
    '''Deterministic MCP tool calculating optimal compliant resource allocation.'''
    policy = get_governorate_quota_policy(governorate)
    max_quota = policy["max_daily_quota"]
    critical_threshold = policy["critical_threshold"]

    stress_factor = 1.0 + max(0.0, (critical_threshold - current_metric_value) / 100.0) + max(0.0, (ambient_temp_c - 28.0) / 100.0)
    recommended_units = round(min(max_quota, requested_units * stress_factor), 2)
    within_quota = recommended_units <= max_quota

    return {
        "governorate": governorate,
        "priority_tier": policy["priority_tier"],
        "recommended_units": recommended_units,
        "max_daily_quota": max_quota,
        "within_quota": within_quota,
        "utilization_ratio": round(recommended_units / max(1.0, max_quota), 4),
    }


@mcp.prompt()
def sovereign_auditor_system_prompt(track_name: str, governorate: str) -> str:
    '''Standardized system prompt template for the TuniSovereign LangGraph agent.'''
    return (
        f"You are the autonomous TuniSovereign-AI auditor for {track_name} in {governorate}, Tunisia. "
        "Always verify telemetry anomalies via ML, check governorate quotas via MCP tools, and anchor "
        "privacy-preserving ZK commitments before authorizing physical actuation or fund release."
    )


if __name__ == "__main__":
    mcp.run()
