# Terraform Setup — SCD with Snowflake and Apache Airflow

This Terraform configuration provisions the AWS infrastructure required to run the **Slowly Changing Dimension (SCD) pipeline** using **Apache Airflow, Docker, Amazon S3, and Snowflake**.

## Architecture

```text
Terraform
    │
    ├── S3 Bucket
    │
    ├── IAM Role + Instance Profile
    │
    ├── Security Group
    │
    ├── SSH Key Pair
    │
    └── EC2 Instance
          │
          └── Docker
                │
                └── Apache Airflow
                      │
                      ├── S3
                      │
                      └── Snowflake
```

## Resources Created

* **S3 Bucket** (`s3-scd-snowflake-us-west-2-tf`) — stores pipeline data and files used by the SCD workflow.
* **EC2 Instance** — Amazon Linux 2023 instance used to run Docker and Apache Airflow.
* **IAM Role + Instance Profile** — provides the EC2 instance with restricted access to the project S3 bucket without requiring AWS access keys on the server.
* **Security Group** — allows SSH access only. Airflow is accessed securely through SSH port forwarding.
* **SSH Key Pair** — automatically generates an RSA 4096-bit key pair. The private key is saved locally as `scd-snowflake-airflow.pem`.
* **EBS Volume** — encrypted 30 GB GP3 root volume for the EC2 instance.
* **Docker** — automatically installed during EC2 initialization.
* **Docker Compose** — installed automatically for running the Airflow services.

---

# Prerequisites

## 1. AWS CLI

Install the AWS CLI and configure your AWS credentials.

Official AWS CLI documentation:

https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

Configure your AWS credentials:

```bash
aws configure
```

Enter:

```text
AWS Access Key ID:     YOUR_ACCESS_KEY
AWS Secret Access Key: YOUR_SECRET_KEY
Default region name:  us-west-2
Default output format: json
```

Verify that your AWS credentials are working:

```bash
aws sts get-caller-identity
```

The command should return your AWS account and identity information.

---

## 2. Terraform

Install Terraform:

https://developer.hashicorp.com/terraform/downloads

Verify the installation:

```bash
terraform version
```

---

## 3. Verify the Project Directory

Make sure you are inside the Terraform project directory containing files such as:

```text
terraform/
├── main.tf
├── provider.tf
├── variables.tf
├── output.tf
└── .cmd.md
```

---

# Step 1 — Initialize Terraform

Initialize the Terraform working directory.

This downloads the required providers:

* AWS
* TLS
* Local

Run:

```bash
terraform init
```

You should see a successful initialization message.

---

# Step 2 — Format Terraform Files

Format all Terraform configuration files using Terraform's standard formatting.

```bash
terraform fmt
```

To verify which files were formatted:

```bash
terraform fmt -check
```

---

# Step 3 — Validate Configuration

Validate the Terraform configuration before creating any AWS resources.

```bash
terraform validate
```

Expected result:

```text
Success! The configuration is valid.
```

---

# Step 4 — Preview Infrastructure Changes

Create an execution plan to see what Terraform will create.

```bash
terraform plan
```

Review the resources carefully before applying the configuration.

Terraform should create resources including:

```text
S3 Bucket
IAM Role
IAM Policy
IAM Instance Profile
Security Group
SSH Key Pair
EC2 Instance
EBS Volume
```

---

# Step 5 — Apply Terraform Configuration

Create the AWS infrastructure.

For an interactive deployment:

```bash
terraform apply
```

Terraform will ask for confirmation.

Enter:

```text
yes
```

Alternatively, for automated deployment:

```bash
terraform apply --auto-approve
```

After successful deployment, Terraform will display outputs including:

```text
ec2_instance_id
ec2_public_ip
ec2_public_dns
s3_bucket_name
iam_role_name
ssh_private_key_path
ssh_connection_command
airflow_tunnel_command
```

---

# Step 6 — Fix PEM Permissions on Windows

Terraform automatically generates the private SSH key.

The file will be created in the Terraform project directory:

```text
scd-snowflake-airflow.pem
```

On Windows, restrict the permissions on the key:

```powershell
icacls "scd-snowflake-airflow.pem" /inheritance:r
```

Then grant the current Windows user read access:

```powershell
icacls "scd-snowflake-airflow.pem" /grant:r "$env:USERNAME:R"
```

Verify the permissions:

```powershell
icacls "scd-snowflake-airflow.pem"
```

---

# Step 7 — Connect to the EC2 Instance

Use the Terraform output:

```bash
terraform output ssh_connection_command
```

Or connect manually:

```bash
ssh -i "scd-snowflake-airflow.pem" ec2-user@<EC2_PUBLIC_IP>
```

Example:

```bash
ssh -i "scd-snowflake-airflow.pem" ec2-user@54.123.456.789
```

---

# Step 8 — Verify Docker Installation

Docker is automatically installed by the EC2 `user_data` script.

After connecting to EC2:

```bash
docker --version
```

Check Docker Compose:

```bash
docker compose version
```

Check Docker service:

```bash
sudo systemctl status docker
```

If Docker is running, you should see:

```text
Active: active (running)
```

---

# Step 9 — Verify the Airflow Project Directory

Terraform creates the Airflow project directory automatically.

Run:

```bash
cd ~/airflow-project
```

Check the directory:

```bash
ls -la
```

The directory structure will contain:

```text
airflow-project/
├── dags/
├── logs/
├── plugins/
└── config/
```

The Docker Compose configuration and Airflow application files will be added in the next stage of the project setup.

---

# Step 10 — Access Airflow Through SSH Tunnel

Airflow will run inside Docker on the EC2 instance.

The Airflow webserver will listen internally on:

```text
localhost:8080
```

Port `8080` does **not** need to be publicly exposed through the AWS Security Group.

Create an SSH tunnel from your local Windows machine:

```bash
ssh -i "scd-snowflake-airflow.pem" ^
  -L 8080:localhost:8080 ^
  ec2-user@<EC2_PUBLIC_IP>
```

If using Git Bash, use:

```bash
ssh -i "scd-snowflake-airflow.pem" \
  -L 8080:localhost:8080 \
  ec2-user@<EC2_PUBLIC_IP>
```

Keep this SSH session running.

Then open your browser:

```text
http://localhost:8080
```

This securely forwards:

```text
Your Computer
     │
     │ SSH Tunnel
     │
     ▼
EC2 :8080
     │
     ▼
Docker
     │
     ▼
Airflow
```

---

# Step 11 — Verify AWS S3 Access from EC2

The EC2 instance receives AWS permissions through its IAM Instance Profile.

No AWS access keys should be stored inside the EC2 server or Airflow `.env` file.

From EC2, run:

```bash
aws sts get-caller-identity
```

Then test the S3 bucket:

```bash
aws s3 ls s3://s3-scd-snowflake-us-west-2-tf
```

The AWS identity should correspond to the IAM role attached to the EC2 instance.

---

# Step 12 — Start Airflow

Once the Airflow Docker Compose configuration has been added, go to:

```bash
cd ~/airflow-project
```

Start the Airflow services:

```bash
docker compose up -d
```

Check running containers:

```bash
docker compose ps
```

View Airflow logs:

```bash
docker compose logs -f
```

To view only the scheduler logs:

```bash
docker compose logs -f scheduler
```

To view the webserver logs:

```bash
docker compose logs -f webserver
```

---

# Step 13 — Verify the Complete Pipeline

The final SCD pipeline will be orchestrated by Airflow.

The expected workflow is:

```text
Airflow DAG
    │
    ▼
Extract / Generate Data
    │
    ▼
Raw Data
    │
    ▼
Amazon S3
    │
    ▼
Snowflake
    │
    ▼
Staging
    │
    ▼
SCD Transformation
    │
    ▼
Dimension Table
```

Airflow is responsible for scheduling and orchestrating these tasks.

S3 is used for object/file storage.

Snowflake is used for data loading, transformation, and the final analytical tables.

---

# Step 14 — Destroy AWS Resources

To remove all resources managed by Terraform:

```bash
terraform destroy
```

Terraform will ask for confirmation.

Enter:

```text
yes
```

For automatic destruction:

```bash
terraform destroy --auto-approve
```

> **Warning:** Destroying the infrastructure can permanently remove AWS resources and data. Make sure any important S3 or Snowflake data has been backed up before running this command.

---

# Important Security Notes

### Do not store AWS access keys on EC2

Do **not** create:

```text
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

for the EC2/Airflow workload.

The EC2 Instance Profile provides temporary AWS credentials automatically.

### Do not expose Airflow publicly

The security group only exposes:

```text
Port 22 — SSH
```

Airflow's port:

```text
8080
```

is accessed through an SSH tunnel.

### S3 access is restricted

The EC2 IAM role should only have the permissions required for the project's S3 bucket rather than unrestricted `AmazonS3FullAccess`.

### Infrastructure is managed by Terraform

AWS infrastructure changes should be made through Terraform rather than manually modifying the EC2 instance whenever possible.

---

# Useful Commands

### Check Terraform state

```bash
terraform show
```

### Show Terraform outputs

```bash
terraform output
```

### Show EC2 IP

```bash
terraform output ec2_public_ip
```

### Show SSH command

```bash
terraform output ssh_connection_command
```

### Show Airflow tunnel command

```bash
terraform output airflow_tunnel_command
```

### SSH into EC2

```bash
ssh -i "scd-snowflake-airflow.pem" ec2-user@<EC2_PUBLIC_IP>
```

### Check Docker

```bash
docker --version
docker compose version
```

### Check Airflow containers

```bash
cd ~/airflow-project
docker compose ps
```

### Stop Airflow

```bash
docker compose down
```

### Start Airflow

```bash
docker compose up -d
```

### View Airflow logs

```bash
docker compose logs -f
```
