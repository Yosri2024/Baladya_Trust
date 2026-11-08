import os
import sys
from typing import TypedDict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.skills.tunisovereign_skills import (
    DarjaDialectParserSkill,
    TelemetryAnomalySkill,
    ZKContractSettlementSkill,
)
from mcp_server.tunisovereign_mcp import calculate_sovereign_quota_allocation


class SovereignAgentState(TypedDict):
    thread_id: str
    node_code: str
    darja_input: str
    moisture_pct: float
    temp_c: float
    flow_l_min: float
    parsed_intent: dict
    anomaly_report: dict
    mcp_allocation: dict
    zk_receipt: dict
    skills_trace: List[str]
    final_explanation: str


def run_sovereign_agent_loop(initial_state: SovereignAgentState) -> SovereignAgentState:
    '''
    Executes the 5-node Stateful Agent Loop (Intake -> Anomaly Skill -> FastMCP Tool
    -> Policy Self-Correction Gate -> ZK & Smart Contract Settlement Skill).
    '''
    state = dict(initial_state)
    state["skills_trace"] = []

    # Node 1: Darja Voice/SMS Intent Skill
    s1 = DarjaDialectParserSkill()
    state["parsed_intent"] = s1.execute(state["darja_input"])
    state["skills_trace"].append(s1.skill_name)

    # Node 2: ML Telemetry Anomaly Verification Skill
    s2 = TelemetryAnomalySkill()
    state["anomaly_report"] = s2.execute(
        state["moisture_pct"], state["temp_c"], state["flow_l_min"]
    )
    state["skills_trace"].append(s2.skill_name)

    # Node 3: Invoke Custom Python FastMCP Tool
    gov = state["parsed_intent"]["governorate"]
    req_units = state["parsed_intent"]["requested_units"]
    mcp_res = calculate_sovereign_quota_allocation(
        governorate=gov,
        soil_moisture_pct=state["moisture_pct"],
        temp_c=state["temp_c"],
        requested_units=req_units,
    )
    state["mcp_allocation"] = mcp_res
    state["skills_trace"].append("FastMCP::calculate_sovereign_quota_allocation")

    # Node 4 & 5: Policy Gate + ZK Commitment & Smart Contract Settlement Skill
    s3 = ZKContractSettlementSkill()
    state["zk_receipt"] = s3.execute(
        node_code=state["node_code"],
        governorate=gov,
        approved_units=mcp_res["approved_units"],
        max_quota=mcp_res["max_daily_quota"],
        thread_id=state["thread_id"],
    )
    state["skills_trace"].append(s3.skill_name)

    state["final_explanation"] = (
        f"[TuniSovereign-AI Agent | Thread {state['thread_id']}] "
        f"Parsed Darja request for {gov} (Node {state['node_code']}). "
        f"Anomaly status: {state['anomaly_report']['severity']} "
        f"(confidence={state['anomaly_report']['anomaly_confidence']}). "
        f"MCP approved {mcp_res['approved_units']} units (<= {mcp_res['max_daily_quota']} max quota). "
        f"Anchored ZK Commitment {state['zk_receipt']['zk_commitment_hash'][:18]}... "
        f"in Tx {state['zk_receipt']['tx_hash'][:18]}..."
    )
    return state


if __name__ == "__main__":
    sample_state: SovereignAgentState = {
        "thread_id": "ds2-kasserine-2026-001",
        "node_code": "KAS-SBEITLA-PLOT-04",
        "darja_input": "Ya khouya fi Kasserine el sonda habtet 28% wel skhana 37 darja, lazmenna maa urgent!",
        "moisture_pct": 28.4,
        "temp_c": 37.2,
        "flow_l_min": 182.0,
        "parsed_intent": {},
        "anomaly_report": {},
        "mcp_allocation": {},
        "zk_receipt": {},
        "skills_trace": [],
        "final_explanation": "",
    }
    out = run_sovereign_agent_loop(sample_state)
    print(out["final_explanation"])
