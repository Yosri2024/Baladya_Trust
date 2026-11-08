import os
import sys
import streamlit as st
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.langgraph_agent import run_sovereign_agent_loop
from backend.tunisovereign_core.ml_anomaly import TunisianTelemetryAnomalyEngine

st.set_page_config(page_title="TuniSovereign-AI Command Center (ISG Tunis DS2)", layout="wide")

st.title("TuniSovereign-AI: Multi-Protocol Django 6, LangGraph, MCP & ZK Blockchain Cockpit")
st.caption("Higher Institute of Management of Tunis (ISG Tunis) — 3-BI & 3-BIS Capstone (Chaouki Bayoudhi)")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Tunisian Governorates", "8 Hubs", "Kasserine, Sidi Bouzid, Gafsa...")
col2.metric("Multi-Protocol Ingress", "REST + GraphQL + gRPC", "Django 6 Core")
col3.metric("Agent & MCP Architecture", "LangGraph + FastMCP", "3 Modular Skills")
col4.metric("Blockchain & ZK Layer", "Foundry Anvil / Amoy", "Zero-Leakage Proofs")

st.subheader("1. Interactive Tunisian Darja Agent Loop, MCP & ZK Smart-Contract Simulator")
with st.form("darja_agent_form"):
    c1, c2 = st.columns(2)
    darja_text = c1.text_input(
        "Farmer / Pharmacist / Citizen Message (Tunisian Darja / French):",
        "Ya khouya fi Kasserine el sonda habtet 28% wel skhana 37 darja, lazmenna maa urgent!",
    )
    node_code = c2.text_input("Resource Node / Clinic / Plot Code:", "KAS-SBEITLA-PLOT-04")
    s1, s2, s3 = st.columns(3)
    moisture = s1.slider("Telemetry Soil Moisture / Stock Level (%)", 15.0, 80.0, 28.4)
    temp_c = s2.slider("Ambient / Cold-Chain Temperature (C)", 2.0, 45.0, 37.2)
    flow = s3.slider("Flow / Dispensation Rate (Units/min)", 20.0, 240.0, 182.0)
    submitted = st.form_submit_button("Run Stateful LangGraph Loop + FastMCP + ZK Settlement")

if submitted:
    res = run_sovereign_agent_loop({
        "thread_id": "ds2-live-thread-001",
        "node_code": node_code,
        "darja_input": darja_text,
        "moisture_pct": moisture,
        "temp_c": temp_c,
        "flow_l_min": flow,
        "parsed_intent": {},
        "anomaly_report": {},
        "mcp_allocation": {},
        "zk_receipt": {},
        "skills_trace": [],
        "final_explanation": "",
    })
    st.success(res["final_explanation"])
    j1, j2, j3 = st.columns(3)
    j1.json(res["parsed_intent"])
    j2.json(res["mcp_allocation"])
    j3.json(res["zk_receipt"])

st.subheader("2. IsolationForest Anomaly Detection Benchmark (Precision / Recall / F1)")
engine = TunisianTelemetryAnomalyEngine()
metrics = engine.fit_and_evaluate_synthetic_benchmark()
st.dataframe(pd.DataFrame([metrics]), use_container_width=True)
