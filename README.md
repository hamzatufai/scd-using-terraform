# Slowly Changing Dimensions in Snowflake Using Streams and Tasks

A real-time data pipeline for continuous data ingestion and transformation into a
Snowflake data warehouse. It generates synthetic customer records, moves them through
S3 with Apache NiFi, auto-ingests them into Snowflake with Snowpipe, and uses
Snowflake Streams + Tasks to implement Change Data Capture (CDC) and Slowly Changing
Dimensions (SCD Type-1 and Type-2) for historical tracking.

See [`presentation.ipynb`](./presentation.ipynb) for the full walkthrough this project
was built around (data warehouse concepts, facts/dimensions, SCD types, architecture,
and a component-by-component tour of the Snowflake objects used here).

### Architecture

![architecture-diagram](./images/scd-archiecture.drawio.png)

### Tech Stack

| Layer | Technology |
|---|---|
| Languages | Python 3, SQL |
| Infrastructure as Code | Terraform |
| Data Generation | Python `faker` library |
| Data Movement | Apache NiFi (Docker) |
| Cloud Storage | Amazon S3 |
| Compute | Amazon EC2 |
| Data Warehouse | Snowflake |
| Containerization | Docker, Docker Compose |

### Dataset

Customer records are generated with the Python `faker` library (see
[`faker.ipynb`](./faker.ipynb)) and written as timestamped CSV files with the
following fields:

- `customer_id`
- `first_name`
- `last_name`
- `email`
- `street`
- `city`
- `state`
- `country`

---

## Repository layout

```
.
├── README.md
├── presentation.ipynb        Slide-deck walkthrough: DW concepts, SCD, architecture, Snowflake objects
├── faker.ipynb                Generates synthetic customer CSVs
├── docker_exp/
│   └── docker-compose.yml     JupyterLab + Zookeeper + NiFi, run on the EC2 instance
├── notes/
│   ├── ide-setup-commands.sh  SSH/SCP + Docker install commands for the EC2 instance
│   └── nifi-setup.txt         NiFi processor group / flow setup (ListFile → FetchFile → PutS3Object)
├── sql/
│   ├── 01 table_creation.sql  Warehouse, database, schema, customer/customer_history/customer_raw tables, stream
│   ├── 02 data_ingestion.sql  External stage + Snowpipe (S3 → customer_raw)
│   ├── 03 scd_type-1.sql      MERGE-based CDC, stored procedure, scheduled task
│   └── 04 scd_type-2.sql      customer_history view/task implementing full history tracking
├── terraform/
│   ├── main.tf                S3 bucket, IAM role/profile, security group, key pair, EC2 instance
│   ├── outputs.tf              Bucket/instance/security-group/SSH outputs
│   ├── providers.tf            AWS/TLS/local provider setup
│   └── terraform-commands.md   Step-by-step Terraform usage
└── images/                     Diagrams referenced from presentation.ipynb / this README
```

---

## Infrastructure (Terraform)

All AWS resources are provisioned via Terraform. See
[`terraform/terraform-commands.md`](./terraform/terraform-commands.md) for full setup
instructions.

**Resources created:**

| Resource | Name |
|---|---|
| S3 Bucket | `s3-scd-snowflake-us-west-2-tf` |
| EC2 Instance | `ec2-scd-snowflake-us-west-2-tf` |
| IAM Role | `ec2-scd-snowflake-us-west-2-tf-role` |
| Instance Profile | `ec2-scd-snowflake-us-west-2-tf-profile` |
| Security Group | `ec2-scd-snowflake-us-west-2-tf-sg` |
| Key Pair | `ec2-scd-snowflake-us-west-2-tf-key` |

**Quick start:**

```bash
cd terraform
terraform init
terraform apply --auto-approve
```

Fix PEM permissions on Windows after apply:

```
icacls "ec2-scd-snowflake-us-west-2-tf.pem" /inheritance:r
icacls "ec2-scd-snowflake-us-west-2-tf.pem" /grant:r "%USERNAME%:R"
```

The generated `.pem` is written into `terraform/` and is git-ignored — never commit it.

---

## Process Flow

1. **Data Generation (EC2)** — `faker.ipynb` / a Python script generates customer CSV
   files and drops them into a folder watched by NiFi.
2. **Data Movement (Apache NiFi)** — NiFi monitors the folder with a
   `ListFile → FetchFile → PutS3Object` flow (see [`notes/nifi-setup.txt`](./notes/nifi-setup.txt))
   and uploads new files to the S3 bucket.
3. **Data Ingestion (Snowpipe)** — Snowpipe auto-ingests CSVs from S3 into the
   `customer_raw` staging table (`sql/02 data_ingestion.sql`).
4. **Data Transformation (Snowflake Task + Stored Procedure)** — a scheduled task runs
   every minute and calls a stored procedure that:
   - Merges `customer_raw` into `customer` (CDC: insert / update)
   - Truncates `customer_raw` to prepare for the next batch
5. **Change Capture (Snowflake Stream)** — a stream on `customer` captures all
   row-level changes.
6. **Historical Data (SCD)** — captured changes populate `customer_history` using
   SCD Type-1 (`sql/03 scd_type-1.sql`) and Type-2 (`sql/04 scd_type-2.sql`) techniques.

---

## Snowflake Objects

| Object | Name | Purpose |
|---|---|---|
| Database | `scd_demo` | Project database |
| Schema | `scd2` | Project schema |
| Warehouse | `COMPUTE_WH` | XSMALL, auto-suspends after 120s |
| Table | `customer_raw` | Staging table (Snowpipe target) |
| Table | `customer` | Current-state table |
| Table | `customer_history` | Historical SCD table |
| Stream | `customer_table_changes` | Captures changes on `customer` |
| Pipe | `customer_s3_pipe` | Auto-ingest from S3 |
| View | `v_customer_change_data` | Derives insert/update/delete rows for history |
| Task | `tsk_scd_raw` | Runs `pdr_scd_demo()` every minute (raw → customer) |
| Task | `tsk_scd_hist` | Merges change data into `customer_history` every minute |

### SCD Types

- **Type 1** — overwrites existing data with the latest values. No history is kept.
- **Type 2** — preserves full history. Each change closes the current record
  (`end_time`, `is_current = FALSE`) and inserts a new active record.

---

## Docker Services

NiFi and JupyterLab run on the EC2 instance via Docker Compose, accessed locally via
SSH port forwarding (no extra security group rules needed beyond SSH).

```bash
# Transfer docker-compose to EC2 and start services
scp -r -i "ec2-scd-snowflake-us-west-2-tf.pem" docker_exp ec2-user@<EC2_PUBLIC_DNS>:/home/ec2-user/docker_exp
ssh -i "ec2-scd-snowflake-us-west-2-tf.pem" ec2-user@<EC2_PUBLIC_DNS> -L 2080:localhost:2080 -L 4888:localhost:4888

cd docker_exp && docker-compose up -d
```

- NiFi UI: `http://localhost:2080/nifi/`
- JupyterLab: `http://localhost:4888/lab`

Full EC2/Docker bootstrap commands live in
[`notes/ide-setup-commands.sh`](./notes/ide-setup-commands.sh).

---

## Usage

### 1. Configure AWS Credentials

```bash
aws configure
# Access Key ID, Secret, region (us-west-2), output format
```

### 2. Provision Infrastructure

```bash
cd terraform
terraform init
terraform apply --auto-approve
```

### 3. Deploy Docker Services on EC2

See [Docker Services](#docker-services) above.

### 4. Set Up Snowflake

Run the scripts in [`sql/`](./sql) **in order** (`01` → `04`) to create the warehouse,
database, schema, tables and stream, the external stage and Snowpipe, and the SCD
Type-1 / Type-2 merge logic, stored procedure, view, and tasks.

### 5. Generate & Push Data

Use [`faker.ipynb`](./faker.ipynb) to generate customer CSVs, then let the NiFi flow
(`notes/nifi-setup.txt`) push them to S3, where Snowpipe picks them up automatically.

### 6. Tear Down

```bash
cd terraform
terraform destroy --auto-approve
```

---

## Security notes

- `terraform apply` writes a `.pem` private key into `terraform/` — it's git-ignored;
  never commit it.
- The EC2 security group opens SSH (and the NiFi/JupyterLab port range) to
  `0.0.0.0/0` — restrict to your own IP for anything beyond a throwaway dev box.
- `sql/02 data_ingestion.sql` embeds placeholder AWS credentials for the external
  stage — replace with a storage integration (IAM role) rather than static keys for
  anything beyond a demo.

---

## Key Takeaways

- End-to-end cloud data pipeline from synthetic data generation to historical storage
- Infrastructure as Code with Terraform for repeatable AWS provisioning
- Change Data Capture (CDC) using Snowflake `MERGE` and Streams
- SCD Type-1 and Type-2 implementation in Snowflake
- Apache NiFi for automated file-to-S3 data movement
- Docker for portable service deployment on EC2
=======
# slowly-changing-dimensions-with-snowflake
