import subprocess
import time

# Kubernetes command helper
def run_kubectl(command):
    result = subprocess.run(["kubectl"] + command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(result.stdout)

# Step 1: Deploy Memcached on the high-memory node (node-a-2core)
def deploy_memcached():
    print("Deploying Memcached on node-a-2core...")
    
    # Define the Memcached deployment YAML
    memcached_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memcached
spec:
  replicas: 1
  selector:
    matchLabels:
      app: memcached
  template:
    metadata:
      labels:
        app: memcached
    spec:
      containers:
        - name: memcached
          image: memcached:latest
          ports:
            - containerPort: 11211
          resources:
            requests:
              memory: "1Gi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "1"
      nodeSelector:
        kubernetes.io/hostname: node-a-2core  # Ensure it runs on the high-memory node
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
                - key: app
                  operator: In
                  values:
                    - memcached
            topologyKey: kubernetes.io/hostname
    """
    
    # Apply the YAML to deploy memcached
    with open("/tmp/memcached-deployment.yaml", "w") as f:
        f.write(memcached_yaml)
    
    run_kubectl(["apply", "-f", "/tmp/memcached-deployment.yaml"])

    # Pin memcached to specific CPU cores if needed (taskset-like functionality)
    run_kubectl(["exec", "-it", "memcached", "--", "taskset", "-c", "0,1", "memcached"])

# Step 2: Deploy batch jobs on appropriate nodes
def deploy_batch_jobs():
    print("Deploying batch jobs...")

    # Define job deployments (example for blackscholes, others follow similar structure)
    batch_jobs = [
        {"workload": "blackscholes", "node": "node-d-4core", "parallelism": "4"},
        {"workload": "canneal", "node": "node-d-4core", "parallelism": "4"},
        {"workload": "radix", "node": "node-d-4core", "parallelism": "4"},
        {"workload": "dedup", "node": "node-d-4core", "parallelism": "2"},
        {"workload": "freqmine", "node": "node-d-4core", "parallelism": "2"},
        {"workload": "vips", "node": "node-d-4core", "parallelism": "2"},
        {"workload": "ferret", "node": "node-a-2core", "parallelism": "2"}
    ]

    for job in batch_jobs:
        deploy_job(job["workload"], job["node"], job["parallelism"])

def deploy_job(workload, node, parallelism):
    print(f"Deploying {workload} on {node} with {parallelism} cores...")

    job_yaml = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {workload}
spec:
  template:
    spec:
      containers:
      - name: {workload}
        image: anakli/cca:parsec_{workload}
        command: ["./run", "-S", "parsec", "-p", "{workload}", "-n", "{parallelism}"]
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2"
      nodeSelector:
        kubernetes.io/hostname: {node}  # Ensure placement on the right node
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
                - key: app
                  operator: In
                  values:
                    - {workload}
            topologyKey: kubernetes.io/hostname
  backoffLimit: 4
    """
    
    with open(f"/tmp/{workload}-job.yaml", "w") as f:
        f.write(job_yaml)
    
    run_kubectl(["apply", "-f", f"/tmp/{workload}-job.yaml"])

# Step 3: Ensure safe collocation and avoid conflicts
def ensure_collocation():
    print("Ensuring safe collocation...")

    # Example logic to check job conflicts
    # e.g., ensure ferret doesn't run on nodes with memcached or other sensitive jobs
    run_kubectl(["get", "pods", "--all-namespaces"])

# Step 4: Monitor and adjust based on performance
def monitor_and_adjust():
    print("Monitoring performance...")

    # You can implement logic to monitor memcached latency using `mcperf`
    # and trigger re-scheduling of jobs if necessary.

    time.sleep(30)  # Simulate monitoring time
    print("Adjusting job placements or parallelism if needed...")

# Main function to orchestrate the scheduling policy
def main():
    deploy_memcached()      # Deploy Memcached
    deploy_batch_jobs()     # Deploy all batch jobs
    ensure_collocation()    # Ensure safe collocation
    monitor_and_adjust()    # Monitor and adjust as needed

if __name__ == "__main__":
    main()