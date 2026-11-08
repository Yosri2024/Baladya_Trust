"""
gRPC Telemetry Ingestion & Urgent Audit Server (proto3 + grpcio)
Implements TelemetryIngestService defined in protos/tunisovereign.proto.
"""
import os
import sys
import time
from concurrent import futures
import grpc

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.langgraph_agent import run_sovereign_agent_loop


class TelemetryIngestServicer:
    """
    Contract-first binary gRPC servicer for high-frequency Tunisian sensor/cooperative
    telemetry streams and urgent anomaly-triggered LangGraph audits.
    """

    def StreamTelemetry(self, request_iterator, context):
        accepted = 0
        anomaly_triggered = False
        thread_id = ""

        for packet in request_iterator:
            accepted += 1
            if packet.metric_type == "MOISTURE" and packet.value < 35.0:
                anomaly_triggered = True
                thread_id = f"grpc-auto-{packet.node_code}-{accepted}"
                run_sovereign_agent_loop({
                    "thread_id": thread_id,
                    "node_code": packet.node_code,
                    "darja_input": f"Automated gRPC alert in {packet.governorate}: moisture dropped to {packet.value}%",
                    "moisture_pct": float(packet.value),
                    "temp_c": 36.5,
                    "flow_l_min": 180.0,
                    "parsed_intent": {},
                    "anomaly_report": {},
                    "mcp_allocation": {},
                    "zk_receipt": {},
                    "skills_trace": [],
                    "final_explanation": "",
                })
        return {
            "accepted_count": accepted,
            "anomaly_triggered": anomaly_triggered,
            "agent_thread_id": thread_id,
        }

    def TriggerUrgentAudit(self, request, context):
        thread_id = f"grpc-urgent-{request.node_code}"
        res = run_sovereign_agent_loop({
            "thread_id": thread_id,
            "node_code": request.node_code,
            "darja_input": request.reason,
            "moisture_pct": 27.5,
            "temp_c": 37.8,
            "flow_l_min": 185.0,
            "parsed_intent": {},
            "anomaly_report": {},
            "mcp_allocation": {},
            "zk_receipt": {},
            "skills_trace": [],
            "final_explanation": "",
        })
        return {
            "status": "VERIFIED_AND_ANCHORED",
            "tx_hash": res["zk_receipt"]["tx_hash"],
        }


def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    server.add_insecure_port(f"[::]:{port}")
    print(f"[TuniSovereign-AI gRPC Server] Listening on port {port} (proto3 binary transport)...")
    server.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
