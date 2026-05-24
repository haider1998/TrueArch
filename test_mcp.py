import json
import subprocess
import time

def send_rpc(proc, method, params=None):
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }
    if params is not None:
        request["params"] = params
    
    print(f"--> {json.dumps(request)}")
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"<-- {response}")
    return json.loads(response)

def main():
    print("Starting MCP server...")
    proc = subprocess.Popen(
        ["venv/bin/python", "-m", "src.mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Initialize
        send_rpc(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        })
        send_rpc(proc, "notifications/initialized")
        
        print("\n--- Testing quick_context ---")
        send_rpc(proc, "tools/call", {
            "name": "quick_context",
            "arguments": {
                "problem": "building a multi-agent system",
                "compliance": ["hipaa"]
            }
        })
        
        print("\n--- Testing get_code_patterns ---")
        send_rpc(proc, "tools/call", {
            "name": "get_code_patterns",
            "arguments": {
                "framework": "langgraph"
            }
        })

        print("\n--- Testing recommend_ai_stack (to check telemetry log) ---")
        send_rpc(proc, "tools/call", {
            "name": "recommend_ai_stack",
            "arguments": {
                "problem": "scalable API",
                "compliance": ["soc2"]
            }
        })
        
        print("\n--- Testing latest_stable_versions (to check staleness warning) ---")
        send_rpc(proc, "tools/call", {
            "name": "latest_stable_versions",
            "arguments": {
                "frameworks": ["fastapi", "langgraph"]
            }
        })
        
    finally:
        proc.terminate()
        
if __name__ == "__main__":
    main()
