Comprehensive Architecture and Implementation Strategy for MLOps on Kubernetes: A Bare-Metal Deployment Analysis
1. Architectural Vision and MLOps Maturity Model
1.1 Project Scope and Strategic Alignment
The initiative to deploy a robust Machine Learning Operations (MLOps) platform, as outlined in the "MLOPS_Proyecto_Final_2025" documentation, represents a critical maturation in the management of artificial intelligence lifecycles. This project transcends simple model training; it necessitates the construction of an automated, resilient ecosystem capable of ingesting raw real estate data, transforming it into actionable intelligence, and serving predictive models through high-availability interfaces. The architecture mandates the integration of disparate but complementary technologies—Apache Airflow for orchestration, MLflow for experiment tracking, FastAPI for inference, and Streamlit for visualization—into a cohesive pipeline managed by Kubernetes.   

The transition from local, script-based execution to a containerized, orchestrator-managed environment is non-trivial. It requires a fundamental shift in infrastructure strategy, particularly when deploying on bare-metal Virtual Machines (VMs) running Rocky Linux rather than managed cloud services like AWS EKS or Google GKE. The constraints provided—specifically the host IP address 10.43.100.94—introduce unique networking challenges that necessitate a departure from standard configuration defaults. This report provides an exhaustive analysis of the architectural requirements, infrastructure prerequisites, and deployment strategies required to achieve the "Bonus" objective of a fully Kubernetes-native deployment managed via Argo CD.   

1.2 The MLOps Lifecycle and Component Integration
The proposed system architecture is designed to support a continuous loop of data ingestion, processing, training, and deployment. Each component plays a specific role in maintaining the integrity and reproducibility of the machine learning workflow.

1.2.1 Data Orchestration: Apache Airflow
Apache Airflow serves as the central nervous system of the platform. Its responsibility extends beyond simple task scheduling; it must enforce data dependencies and ensure that the raw data fetched from the external API (http://10.43.100.103:8000) is correctly versioned and processed before reaching the training stage. In a Kubernetes environment, Airflow allows for dynamic scalability. By utilizing the KubernetesExecutor, each task—whether it is a lightweight data fetch or a heavy model training job—runs in its own isolated pod. This isolation prevents dependency conflicts, a common plague in monolithic ML applications where data processing libraries might conflict with training frameworks (e.g., conflicting versions of numpy or pandas). The requirement to use "Git-Sync" for DAG management ensures that the logic governing these pipelines is version-controlled and immutable once deployed, adhering to Infrastructure-as-Code (IaC) principles.   

1.2.2 Experiment Tracking and Model Registry: MLflow
MLflow provides the necessary governance layer. In this architecture, it must track two distinct streams of information:

Metadata (Parameters and Metrics): Stored in a relational database (PostgreSQL).

Artifacts (Models and Plots): Stored in an object store (MinIO acting as S3).

The "Production" gating mechanism is critical. The system must be configured such that the Inference API only polls for models that have been explicitly transitioned to the "Production" stage in the MLflow Registry. This decoupling ensures that data scientists can experiment freely without risking the stability of the customer-facing application.

1.2.3 Continuous Delivery: Argo CD and GitOps
The introduction of Argo CD transforms the deployment process from a push-based model (CI pipelines running kubectl apply) to a pull-based GitOps model. Argo CD resides inside the cluster, constantly monitoring the state of the Git repository. When a new container image is built by GitHub Actions and the manifest is updated, Argo CD detects the drift and synchronizes the cluster state. This approach provides an audit trail of every change and allows for instant rollbacks, which is essential for maintaining high availability in production environments.   

1.3 Architectural Topology and Resource Planning
The user has requested deployment scenarios for 1, 2, or 3 VMs. Each topology presents different trade-offs regarding availability, complexity, and storage resilience.

Topology	Node Roles	Availability	Storage Strategy (Longhorn)	Use Case
Single-Node	Control Plane + Worker + Etcd	Low (SPOF)	Replica Count: 1 (Risk of data loss)	Dev / Proof of Concept
Dual-Node	
Node 1: Control Plane + Etcd


Node 2: Worker

Medium	Replica Count: 2 (Split-brain risk)	Resource Separation
Three-Node	
Node 1: CP + Etcd


Node 2: Worker + Etcd


Node 3: Worker + Etcd

High (HA)	Replica Count: 3 (Resilient)	Production Grade
Resource Allocation Analysis: For the Single-Node scenario (IP 10.43.100.94), the system is a monolith. All components—Airflow Scheduler, Webserver, Triggerer, MLflow server, Postgres databases, MinIO, and the Application pods—compete for the same CPU and Memory resources. K3s is chosen for its lightweight footprint , but the density of 15+ containers requires rigorous resource limits to prevent the OOM (Out of Memory) killer from terminating critical control plane processes.   

2. Infrastructure Engineering and Operating System Preparation
The foundation of a stable Kubernetes cluster lies in the preparation of the underlying operating system. Rocky Linux, being an enterprise-grade RHEL derivative, ships with security defaults that are often hostile to container orchestrators.

2.1 The Critical Network Conflict: Analysis of CIDR Collision
The most significant technical risk identified in this project is the IP address assignment. The provided host IP is 10.43.100.94 [User Query]. Standard Kubernetes distributions, including K3s, utilize specific Classless Inter-Domain Routing (CIDR) blocks for internal virtual networking:

Service CIDR: 10.43.0.0/16 (Default).   

Pod CIDR: 10.42.0.0/16 (Default).   

The Conflict Mechanism: The host IP 10.43.100.94 mathematically resides within the default Service CIDR range (10.43.0.0 to 10.43.255.255). When K3s initializes, it creates iptables rules (or IPVS entries) to intercept traffic destined for the Service CIDR and load-balance it to backing pods. If the Service CIDR is left at the default 10.43.0.0/16, the Linux kernel on the node will interpret any traffic destined for the Local Area Network (LAN)—including the gateway, other VMs, and even its own external interface—as internal cluster traffic. Consequences of Collision:   

Routing Blackholes: Packets meant for the user's laptop or the gateway will be trapped by the CNI (Container Network Interface) and dropped because no Kubernetes Service exists with those IPs.

DNS Loop Failures: CoreDNS (assigned 10.43.0.10 by default) may become unreachable if the node creates a conflict in the routing table, preventing pods from resolving external domains.   

Control Plane Isolation: In multi-node setups, if Node 2 tries to reach Node 1 at 10.43.100.94, and Node 2 thinks 10.43.x.x is an internal virtual network, the connection will fail.

Remediation Strategy: It is imperative to shift the Kubernetes internal networks to non-conflicting ranges during the installation phase. We cannot change this after installation without a full cluster teardown.   

Selected Service CIDR: 10.45.0.0/16.

Selected Pod CIDR: 10.44.0.0/16.

Selected DNS IP: 10.45.0.10.

This configuration ensures a clean separation between the Physical Network (10.43.x.x) and the Virtual Networks (10.44.x.x, 10.45.x.x).

2.2 Security Layer Configuration: Firewalld and SELinux
Rocky Linux 9 utilizes firewalld as its default dynamic firewall daemon and enforces SELinux (Security-Enhanced Linux) for mandatory access control. Both subsystems require modification to accommodate Kubernetes.

2.2.1 Firewall Management
Kubernetes relies heavily on iptables (or nftables in newer kernels) to manage pod-to-pod and node-to-node communication. The K3s CNI (Flannel) creates bridge interfaces (cni0) and VXLAN overlays that require unrestricted traffic flow between containers. firewalld can interfere with these dynamically generated rules. While it is possible to configure firewalld by explicitly opening ports 6443 (API), 10250 (Kubelet), and 8472 (Flannel VXLAN) , this approach is brittle. A simple firewall-cmd --reload can inadvertently flush the CNI's rules, causing a network outage.   

Recommendation: For this specific MLOps deployment, disabling firewalld is the recommended path to ensure network stability.

Rationale: K3s manages its own network policies. The complexity of debugging interactions between firewalld zones and Kubernetes overlays outweighs the marginal security benefit on a private lab VM.   

Implementation: The command systemctl disable --now firewalld must be executed prior to installation.

2.2.2 SELinux Contexts
SELinux provides robust security by isolating processes, but it is a frequent source of "Permission Denied" errors in Kubernetes, particularly regarding persistent volumes. If a pod attempts to mount a host directory that lacks the correct SELinux context label (e.g., container_file_t), the kernel will block access. K3s includes support for SELinux via the k3s-selinux RPM. However, installing this RPM requires matching the exact version of the selinux-policy package on the host. Mismatches can break the installation.   

Operational Strategy: To mitigate risk while maintaining log visibility, setting SELinux to Permissive mode is the optimal strategy for the project initialization.   

Mechanism: In Permissive mode, violations are logged to /var/log/audit/audit.log but are not blocked. This allows the cluster to function immediately while providing the data needed to create custom policy modules if strict enforcement is required later.

Implementation: This is achieved by editing /etc/selinux/config and running setenforce 0.

2.3 Storage Prerequisites: iSCSI for Longhorn
The project requirements specify a robust storage solution. Longhorn is the industry standard for cloud-native distributed block storage on Kubernetes. Longhorn operates by creating "replicas" of volumes on the underlying disks of the nodes and exposing them to pods as block devices. To achieve this, Longhorn leverages the iSCSI (Internet Small Computer Systems Interface) protocol. It creates a target on the node that the kernel connects to.   

The Rocky Linux Deficit: Standard Rocky Linux "Minimal" installations do not include the iSCSI initiator userspace tools. Without these tools, Longhorn cannot attach volumes. Pods requesting storage (like PostgreSQL for MLflow) will remain in a ContainerCreating state indefinitely, waiting for a volume that never attaches.

Requirement: The package iscsi-initiator-utils must be installed, and the iscsid daemon must be enabled and running on every node in the cluster.   

3. Kubernetes Deployment Topologies and Installation
This chapter details the specific execution steps for deploying K3s across the requested topologies (1, 2, or 3 VMs), incorporating the critical networking fixes identified in Chapter 2.

3.1 K3s Architecture on Rocky Linux
K3s is a certified Kubernetes distribution designed for low resource consumption. It consolidates the standard Kubernetes control plane components (API Server, Controller Manager, Scheduler) into a single binary.

Data Store: By default, K3s uses SQLite for single-node setups. For multi-node (High Availability), it can use an embedded Etcd (via the --cluster-init flag).   

Ingress: K3s ships with Traefik v2 by default.

Load Balancer: It includes "ServiceLB" (Klipper), a simple DaemonSet that uses host ports to simulate a LoadBalancer.

Strategic Deviation: For this project, we will disable the default Traefik and ServiceLB during installation.

Reasoning: The project requires Argo CD and potential customization of Ingress routes for MLflow and Airflow. Installing Traefik via Helm (managed by Argo CD) allows for declarative configuration of dashboards, middlewares, and TLS certificates, which is difficult to manage with the bundled "manifest-based" installation. Disabling ServiceLB paves the way for MetalLB, which provides a more production-realistic Layer 2 load balancing experience suitable for the "Bonus" objective.   

3.2 Scenario A: Single-Node Deployment (The "All-in-One")
This scenario deploys the entire stack on the single VM (10.43.100.94). This is the most likely starting point for the project.

Installation Command Construction: We utilize the INSTALL_K3S_EXEC environment variable to pass flags to the K3s binary.   

Bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --node-ip=10.43.100.94 \
  --cluster-cidr=10.44.0.0/16 \
  --service-cidr=10.45.0.0/16 \
  --cluster-dns=10.45.0.10 \
  --disable servicelb \
  --disable traefik \
  --write-kubeconfig-mode 644" sh -
Flag Analysis:

--node-ip: Explicitly binds the Kubelet to the correct interface.

--cluster-cidr=10.44.0.0/16: Sets the Pod network to a non-conflicting range.   

--service-cidr=10.45.0.0/16: Sets the Service network to a non-conflicting range.   

--cluster-dns=10.45.0.10: Ensures the internal DNS service IP exists within the new Service CIDR.   

--write-kubeconfig-mode 644: Allows the rocky user to read the k3s.yaml config file without sudo, facilitating easier debugging.

3.3 Scenario B: Three-Node High Availability (HA)
In this scenario, we assume the user has provisioned two additional VMs. This setup provides true redundancy.

Primary Node Bootstrap (Node 1): We add the --cluster-init flag. This instructs K3s to initialize an embedded Etcd cluster instead of using SQLite, enabling other control plane nodes to join.   

Bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --cluster-init \
  --node-ip=10.43.100.94 \
  --cluster-cidr=10.44.0.0/16 \
  --service-cidr=10.45.0.0/16 \
  --cluster-dns=10.45.0.10 \
  --token=MY_SECRET_TOKEN \
  --disable servicelb \
  --disable traefik" sh -
Secondary Nodes Join (Nodes 2 & 3): The secondary nodes join as servers (control plane nodes) to form a quorum.

Bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --server https://10.43.100.94:6443 \
  --token=MY_SECRET_TOKEN \
  --node-ip=<NODE_IP> \
  --cluster-cidr=10.44.0.0/16 \
  --service-cidr=10.45.0.0/16 \
  --cluster-dns=10.45.0.10 \
  --disable servicelb \
  --disable traefik" sh -
Consistency Requirement: It is critical that the --cluster-cidr and --service-cidr flags are identical on all nodes. If a joining node has different CIDR settings (or defaults to 10.43.0.0/16), it will fail to join or cause routing inconsistencies that break the cluster.   

4. Storage and Networking Implementation
With the Kubernetes control plane active, the focus shifts to the data plane: ensuring persistent storage for the databases and external access to the services.

4.1 Distributed Storage: Longhorn Implementation
Longhorn provides a highly available, distributed block storage system. It is particularly well-suited for this project because it supports backups to S3 (MinIO) and handles volume replication transparently.

4.1.1 The Single-Node Replica Challenge
A standard Longhorn installation defaults to a replica-count of 3. It enforces "Soft Anti-Affinity," attempting to place each replica on a different node to ensure survival if a node fails. In a Single-Node deployment (Scenario A), there is only one node available.   

The Failure Mode: If Longhorn attempts to create 3 replicas on 1 node, it may succeed if "Soft Anti-Affinity" allows it, or it may hang in a "Degraded" state if the scheduler cannot find eligible resources. A "Degraded" volume is readable/writable but reports as unhealthy in the UI.

The Configuration Fix: For the single-node setup, the storage class must be configured with numberOfReplicas: 1. This instructs Longhorn that a single copy of the data is sufficient, aligning the configuration with the physical topology.   

4.1.2 StorageClass Design
We will define a custom StorageClass named longhorn-single.

YAML
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: longhorn-single
provisioner: driver.longhorn.io
allowVolumeExpansion: true
parameters:
  numberOfReplicas: "1"
  staleReplicaTimeout: "2880"
  fromBackup: ""
  fsType: "ext4"
This configuration ensures that when Postgres or MinIO requests a Persistent Volume Claim (PVC), the volume is provisioned successfully on the single node without error.

4.2 Traffic Management: MetalLB Layer 2 Load Balancing
To expose services like the FastAPI Inference endpoint or the Streamlit UI to users outside the cluster, we require a LoadBalancer. Since we are on bare metal (VMs), there is no cloud controller (like AWS ELB) to provision an IP. MetalLB fills this gap. We will configure it in Layer 2 Mode.

4.2.1 Layer 2 Mode Architecture
In Layer 2 mode, one node in the cluster creates a "Leader" speaker pod. This pod responds to ARP (Address Resolution Protocol) requests on the local network.   

Mechanism: When a user requests the IP of a service (e.g., 10.43.100.95), the Leader node replies with its own MAC address. The switch sends the traffic to that node, and kube-proxy distributes it to the correct pod.

Leader Election: MetalLB uses a hashing algorithm based on the Node Name and the Service IP to deterministically select which node will be the leader for a specific IP. This spreads the load of different services across different nodes in a multi-node cluster.   

4.2.2 Single-Node Bottleneck & Limitations
In a Single-Node setup, Layer 2 mode works perfectly but offers no failover. The single node answers all ARP requests. In a Multi-Node setup, Layer 2 mode has a limitation: Single-Node Bottleneck. All traffic for a specific Service IP enters through one node (the Leader). The ingress bandwidth is limited to that single node's network interface capacity.   

Relevance: For this MLOps project, traffic (data ingestion, UI access) is unlikely to saturate a gigabit interface, making Layer 2 mode an acceptable and simpler alternative to the complex BGP configuration.

4.2.3 IP Address Pool Configuration
We must define a pool of IPs that MetalLB controls. Since the host is 10.43.100.94, we can assign a small range of unused IPs in the same subnet for services.

Address Pool: 10.43.100.95 - 10.43.100.99. This allows us to assign distinct IPs to the Ingress Controller or directly to services if needed.   

4.3 Ingress Controller: Traefik
With MetalLB providing an external IP, we deploy Traefik as the Ingress Controller.

Integration: The Traefik Service is defined with type: LoadBalancer. MetalLB detects this and assigns 10.43.100.95 (the first available IP) to Traefik.

Routing: Traefik then routes HTTP traffic based on Host headers (e.g., airflow.10.43.100.95.nip.io or mlflow.example.com) to the backend services.

Argo CD Implications: Traefik handles TLS termination. We can configure a Middleware to strip prefixes or handle authentication headers if we put the services behind a unified authentication layer later.   

5. GitOps, CI/CD, and Observability Pipeline
The final layer of the architecture is the automation machinery that drives the MLOps lifecycle. This adheres to the "Level 4" maturity model where operations are code-defined and automated.

5.1 Continuous Deployment: Argo CD Architecture
Argo CD acts as the Kubernetes controller for the Git repository.

Repo Server: Clones the repository containing Helm charts (for Airflow, MinIO) and raw manifests (for FastAPI, Streamlit).

Application Controller: Compares the live state of the cluster against the desired state in Git.

Image Updater: This optional but highly recommended component polls the container registry (Docker Hub) for new image tags. When a new image is pushed by the CI pipeline, the Image Updater modifies the Argo CD application parameters to use the new tag, triggering a deployment.   

Private Registry Configuration: The project mandates publishing images to Docker Hub. If the repositories are private, Argo CD needs credentials.

Configuration: A Kubernetes Secret (docker-registry type) must be created in the argocd namespace.

Rate Limits: Docker Hub enforces rate limits on anonymous pulls. Configuring authentication via registries.conf in the Argo CD Image Updater is critical to prevent "Too Many Requests" errors during frequent retraining cycles.   

5.2 CI Pipeline: GitHub Actions
The "Build" phase is handled outside the cluster by GitHub Actions.

Workflow Trigger: Pushes to the main branch or specific tags.

Matrix Builds: The workflow should build three distinct images:

FastAPI Image: Contains the model serving logic and mlflow dependencies.

Streamlit Image: Contains the visualization logic.

Airflow Custom Image: Extends the official Airflow image with project-specific Python requirements (e.g., scikit-learn, pandas, shap) needed for the processing DAGs.

Tagging Strategy: Images should be tagged with the Git Commit SHA (sha-xyz123). This immutable tagging allows Argo CD to uniquely identify changes. Using latest is discouraged for CD triggers as the tag name doesn't change, masking updates from the orchestrator.

5.3 MLOps Workflow Integration
The convergence of these tools creates the complete pipeline:

Airflow triggers a DAG. It creates a pod using the custom image.

The task fetches data from the API, cleans it, and trains a model.

The training script logs metrics to MLflow (Postgres) and saves the model artifact to MinIO.

If the model beats the baseline, the script uses the MLflow Client API to transition the model version to stage="Production".

FastAPI, running in a separate deployment, detects the change (via polling or restart) and loads the new "Production" model for inference.

Grafana/Prometheus scrapes metrics from the FastAPI endpoint (latency, request count) and the Node exporter (CPU/Memory), providing full system observability.

6. Implementation Plan and Operational Directives
This section translates the architectural analysis into actionable prompts for the engineering team. These prompts are designed to generate the specific configuration files and commands required for deployment.

6.1 Phase 1: Infrastructure Bootstrap
Operational Directive 1: Host Preparation

"Act as a Linux Systems Administrator. I have a fresh Rocky Linux 9 VM with IP 10.43.100.94.

Generate the sequence of commands to:

Update the system DNF repositories.

Permanently disable firewalld.

Set SELinux to Permissive mode and persist this change.

Install iscsi-initiator-utils and nfs-utils.

Enable and start the iscsid service.

Explain briefly why iscsid is required for Longhorn."

Operational Directive 2: K3s Cluster Installation (Single Node)

"Act as a Kubernetes Engineer. I need to install a single-node K3s cluster on the host prepared above (IP 10.43.100.94).

Write the exact curl installation command using INSTALL_K3S_EXEC.

CRITICAL: You must override the default networking to avoid conflict with the host IP. Use:

--cluster-cidr=10.44.0.0/16

--service-cidr=10.45.0.0/16

--cluster-dns=10.45.0.10

Disable servicelb and traefik via flags.

Explain in the output how these CIDR changes prevent routing loops with the host's 10.43.x.x network."

6.2 Phase 2: Storage and Networking
Operational Directive 3: Longhorn and MetalLB Configuration

"Act as a Cloud-Native Storage Architect.

Create a Helm values.yaml file for Longhorn that sets the persistence.defaultClassReplicaCount to 1 (for single-node survival).

Provide the Helm install command for Longhorn.

Create a Kubernetes manifest for MetalLB (Namespace, IPAddressPool, and L2Advertisement). The IPAddressPool should use the range 10.43.100.95-10.43.100.99.

Explain how MetalLB's Layer 2 mode will advertise these IPs using ARP."

Operational Directive 4: Traefik Ingress Controller

"Act as a Kubernetes Networking Specialist.

Provide a Helm command to install Traefik v2.

Configure it to use the LoadBalancer service type (so it picks up an IP from MetalLB).

Enable the Traefik Dashboard but ensure it is not exposed insecurely (use a basic CRD Middleware for auth or limit it to internal access)."

6.3 Phase 3: MLOps Platform Deployment
Operational Directive 5: Argo CD and GitOps Setup

"Act as a DevOps Architect.

Provide the manifests to install Argo CD and Argo CD Image Updater.

Create a Secret manifest template for Docker Hub credentials.

Create an Application manifest that points to a target GitHub repository.

Inside that repo, structure a docker-compose style set of manifests for:

PostgreSQL (StatefulSet for MLflow/Airflow).

MinIO (StatefulSet with default bucket creation).

MLflow (Deployment connecting to Postgres/MinIO).

Apache Airflow (Helm Chart dependency).

FastAPI and Streamlit (Deployments)."

6.4 Phase 4: Application Logic
Operational Directive 6: Inference and Visualization Code

"Act as a Python ML Engineer.

Write the main.py for FastAPI. It must:

Initialize mlflow.set_tracking_uri().

Load the model with models:/<ModelName>/Production.

Expose a /predict endpoint.

Write the app.py for Streamlit. It must:

Create input fields matching the 'Realtor' dataset (price, beds, baths, etc.).

Send a POST request to the FastAPI service.

Display the prediction and a SHAP force plot.

Provide the Dockerfiles for both applications."

7. Deep Insights and Nuanced Recommendations
7.1 Insight: The "Why" of Retraining and Drift Detection
The project documentation asks for an explanation of "Why" a new training occurs. In a naïve implementation, retraining happens whenever new data arrives. However, this is computationally wasteful and potentially destabilizing.

The Nuance: Retraining should be triggered by Concept Drift or Data Drift.

Drift Mechanism: Using libraries like EvidentlyAI or Alibi Detect within the Airflow pipeline allows the system to compare the statistical distribution of the new data batch against the training baseline.

Recommendation: Implement a conditional step in the Airflow DAG. If Drift_Score > Threshold, trigger training. If not, append data to the "Raw" store and skip training. This demonstrates a sophisticated understanding of MLOps economics.

7.2 Insight: The Fragility of Layer 2 Load Balancing
While MetalLB Layer 2 mode is the correct choice for this environment, it utilizes Gratuitous ARP (GARP) to announce IP ownership.

The Nuance: Some older routers or aggressive switches ignore GARP packets to prevent ARP spoofing. This can lead to a situation where the cluster works, but external clients cannot connect because the router caches the old MAC address.

Recommendation: If connectivity issues arise where the service is "Pending" or unreachable despite correct config, the engineering team should verify the router's ARP table or clear the ARP cache on client machines.

7.3 Insight: Single-Node Storage Risks
The decision to run Longhorn on a single node (Scenario A) creates a Single Point of Failure (SPOF). If the VM's disk corrupts, the Postgres databases (containing MLflow experiment history and Airflow DAG state) are lost irrecoverably.

Recommendation: Even for the single-node setup, configure Longhorn's Backup Target to point to an external S3 bucket (e.g., AWS S3 or a separate NAS on the network). This allows the entire storage state to be restored to a new cluster in minutes, fulfilling the Disaster Recovery requirement of a mature MLOps platform.

8. Conclusion
The architecture defined in this report represents a rigorous, production-aligned approach to the "MLOPS_Proyecto_Final_2025" challenge. By proactively identifying and neutralizing the IP address conflict via custom K3s CIDR flags (10.45.0.0/16), the stability of the cluster is assured. The selection of Longhorn for storage and MetalLB for networking provides a robust foundation that mimics enterprise bare-metal environments, significantly exceeding the "Bonus" requirements.

This deployment is not merely a collection of tools; it is a synchronized ecosystem where data flows from ingestion to inference through a governed, automated pipeline. The integration of GitOps via Argo CD ensures that the platform is maintainable, auditable, and resilient, positioning the project as a high-fidelity simulation of modern machine learning operations.



MLOPS_Proyecto_Final_2025.pdf

docs.k3s.io
Quick-Start Guide - K3s - Lightweight Kubernetes
Opens in a new window

docs.k3s.io
K3s server - K3s - Lightweight Kubernetes
Opens in a new window

docs.k3s.io
Basic Network Options - K3s - Lightweight Kubernetes
Opens in a new window

github.com
Can't access anything on the 10.43.x.x range · Issue #1247 · k3s-io/k3s - GitHub
Opens in a new window

github.com
Intermittent kube-dns Service CIDR IP address conflict · Issue #10611 · k3s-io/k3s - GitHub
Opens in a new window

github.com
Unable to change cluster CIDR · Issue #93 · k3s-io/k3s - GitHub
Opens in a new window

docs.k3s.io
Requirements - K3s - Lightweight Kubernetes
Opens in a new window

medium.com
Setting up K3s on a Linux Virtual machine | by Syed Usman Ahmad - Medium
Opens in a new window

docs.k3s.io
Advanced Options / Configuration - K3s - Lightweight Kubernetes
Opens in a new window

docs.expertflow.com
Longhorn Deployment Guide - Expertflow CX
Opens in a new window

longhorn.io
Documentation - Longhorn
Opens in a new window

docs.k3s.io
Networking Services - K3s - Lightweight Kubernetes
Opens in a new window

blog.kevingomez.fr
Replacing ServiceLB by MetalLB in k3s | Kévin Gomez
Opens in a new window

docs.k3s.io
Configuration Options - K3s - Lightweight Kubernetes
Opens in a new window

anyware.hp.com
Confirming the CIDR for Connector Cluster - HP Anyware
Opens in a new window

ranchermanager.docs.rancher.com
Setting up a High-availability K3s Kubernetes Cluster for Rancher
Opens in a new window

docs.harvesterhci.io
StorageClass - Harvester Overview
Opens in a new window

docs.harvesterhci.io
Single-Node Clusters - Harvester Overview
Opens in a new window

metallb.universe.tf
MetalLB in layer 2 mode :: MetalLB, bare metal load-balancer for Kubernetes
Opens in a new window

docs.redhat.com
Chapter 23. Load balancing with MetalLB | Networking | OpenShift Container Platform | 4.9
Opens in a new window

docs.netscaler.com
NetScaler CPX integration with MetalLB in layer 2 mode for on-premises Kubernetes clusters
Opens in a new window

argo-cd.readthedocs.io
Ingress Configuration - Argo CD - Declarative GitOps CD for Kubernetes - Read the Docs
Opens in a new window

community.traefik.io
Using Traefik as Ingress on different MetalLB loadbalancerIP?
Opens in a new window

argocd-image-updater.readthedocs.io
Configuration of Container Registries - Argo CD Image Updater
Opens in a new window

cncf.io
Mastering Argo CD image updater with Helm: a complete configuration guide | CNCF
