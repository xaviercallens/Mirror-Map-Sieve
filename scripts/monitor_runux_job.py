#!/usr/bin/env python3
import subprocess
import json
import sys
from datetime import datetime

PROJECT_ID = "agora-autoresearch-001"
REGION = "us-central1"
JOB_NAME = "runux-pipeline"

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command {' '.join(cmd)}: {e.stderr}", file=sys.stderr)
        return None

def main():
    print(f"=== Monitoring GCP Job: {JOB_NAME} at {datetime.now().isoformat()} ===")
    
    # 1. Get the latest execution name and status
    list_cmd = [
        "gcloud", "run", "jobs", "executions", "list",
        "--job", JOB_NAME,
        "--region", REGION,
        "--project", PROJECT_ID,
        "--limit", "1",
        "--format", "json"
    ]
    
    output = run_cmd(list_cmd)
    if not output or output == "[]":
        print(f"No executions found for job {JOB_NAME}.")
        return
        
    try:
        executions = json.loads(output)
        exec_info = executions[0]
        exec_name = exec_info["metadata"]["name"]
        
        # Determine status
        status_cond = exec_info.get("status", {}).get("conditions", [])
        status_str = "UNKNOWN"
        for cond in status_cond:
            if cond.get("type") == "Completed":
                if cond.get("status") == "True":
                    status_str = "SUCCEEDED"
                elif cond.get("status") == "False":
                    status_str = "FAILED"
                else:
                    status_str = "RUNNING"
                break
        
        print(f"Latest Execution : {exec_name}")
        print(f"Status           : {status_str}")
        print(f"Created Time     : {exec_info['metadata']['creationTimestamp']}")
        
        # 2. Fetch latest logs
        print("\n--- Recent Logs from Cloud Logging ---")
        log_filter = f"resource.type=cloud_run_job AND resource.labels.job_name={JOB_NAME} AND resource.labels.location={REGION}"
        log_cmd = [
            "gcloud", "logging", "read",
            log_filter,
            "--project", PROJECT_ID,
            "--limit", "50",
            "--format", "value(textPayload)"
        ]
        
        logs = run_cmd(log_cmd)
        if logs:
            log_lines = logs.split("\n")
            non_empty_logs = [line for line in log_lines if line.strip()]
            for line in non_empty_logs[-30:]:  # show last 30 lines
                print(line)
        else:
            print("No logs found yet.")
            
        # Write state to a local scratch file
        import os
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/runux_monitor_status.txt", "w") as f:
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Execution: {exec_name}\n")
            f.write(f"Status: {status_str}\n")
            if logs:
                f.write("\nLogs:\n" + logs)
                
    except Exception as e:
        print(f"Failed to parse execution info: {e}")

if __name__ == "__main__":
    main()
