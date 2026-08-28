"""
SCD Type 2 synthetic customer generator.

Generates synthetic customer data with Faker and uploads
SCD Type 2 test batches to Amazon S3.

Behavior:
- Creates an initial customer population.
- Retains existing customer history.
- Randomly selects existing customers for updates.
- Updated customers keep their old version and receive a new version.
- Unchanged customers remain unchanged.
- Generates new customer IDs.
- Produces duplicate customer_ids intentionally for SCD2 testing.
- Maintains effective dates, version numbers, and current flags.
- Upload failures are raised to Airflow.
- Temporary CSV files are always cleaned up.
"""

from datetime import datetime, timedelta, timezone
import csv
import json
import logging
import os
import random

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from faker import Faker

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

S3_BUCKET = os.environ.get(
    "SCD_S3_BUCKET",
    "s3-scd-snowflake-airflow-2026",
)

S3_PREFIX = os.environ.get(
    "SCD_S3_PREFIX",
    "scd",
)

# IMPORTANT:
# This directory should be mounted as an Airflow volume.
LOCAL_DATA_DIR = os.environ.get(
    "SCD_LOCAL_DATA_DIR",
    "/opt/airflow/data",
)

RECORD_COUNT = int(
    os.environ.get(
        "SCD_RECORD_COUNT",
        "100",
    )
)

UPDATE_PERCENTAGE = int(
    os.environ.get(
        "SCD_UPDATE_PERCENTAGE",
        "20",
    )
)

NEW_CUSTOMER_PERCENTAGE = int(
    os.environ.get(
        "SCD_NEW_CUSTOMER_PERCENTAGE",
        "10",
    )
)

STATE_FILE = os.path.join(
    LOCAL_DATA_DIR,
    "customer_state.json",
)


# ============================================================
# CSV SCHEMA
# ============================================================

FIELDNAMES = [
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "street",
    "city",
    "state",
    "country",
    "version",
    "is_current",
    "effective_start_date",
    "effective_end_date",
]


# ============================================================
# CUSTOMER GENERATOR
# ============================================================


def generate_customer(fake, customer_id):
    """
    Generate a new customer version.
    """

    return {
        "customer_id": customer_id,
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.email(),
        "street": fake.street_address(),
        "city": fake.city(),
        "state": fake.state(),
        "country": fake.country(),
    }


# ============================================================
# CREATE CUSTOMER VERSION
# ============================================================


def create_customer_version(
    customer,
    version,
    effective_start_date,
    is_current=True,
    effective_end_date=None,
):
    """
    Create an SCD Type 2 version of a customer.
    """

    return {
        "customer_id": customer["customer_id"],
        "first_name": customer["first_name"],
        "last_name": customer["last_name"],
        "email": customer["email"],
        "street": customer["street"],
        "city": customer["city"],
        "state": customer["state"],
        "country": customer["country"],
        "version": version,
        "is_current": is_current,
        "effective_start_date": effective_start_date,
        "effective_end_date": effective_end_date,
    }


# ============================================================
# MAIN AIRFLOW TASK
# ============================================================


def generate_and_upload_customers(**context):

    fake = Faker()

    os.makedirs(
        LOCAL_DATA_DIR,
        exist_ok=True,
    )

    file_path = None

    try:

        logger.info("==================================================")

        logger.info("Starting SCD Type 2 customer generation")

        logger.info(
            "S3 bucket: %s",
            S3_BUCKET,
        )

        logger.info(
            "S3 prefix: %s",
            S3_PREFIX,
        )

        logger.info(
            "Record count: %d",
            RECORD_COUNT,
        )

        logger.info(
            "Update percentage: %d%%",
            UPDATE_PERCENTAGE,
        )

        logger.info(
            "New customer percentage: %d%%",
            NEW_CUSTOMER_PERCENTAGE,
        )

        # ====================================================
        # LOAD STATE
        # ====================================================

        if os.path.exists(STATE_FILE):

            logger.info(
                "Loading previous customer state: %s",
                STATE_FILE,
            )

            with open(
                STATE_FILE,
                "r",
                encoding="utf-8",
            ) as state_file:

                state = json.load(state_file)

        else:

            logger.info("No previous state found.")

            state = {
                "customers": {},
                "next_customer_id": 1,
            }

        customers = state.get(
            "customers",
            {},
        )

        next_customer_id = int(
            state.get(
                "next_customer_id",
                1,
            )
        )

        # JSON dictionary keys are strings.
        customers = {
            str(customer_id): versions for customer_id, versions in customers.items()
        }

        logger.info(
            "Existing customer IDs: %d",
            len(customers),
        )

        # ====================================================
        # CURRENT CUSTOMER IDs
        # ====================================================

        existing_ids = list(customers.keys())

        # ====================================================
        # SELECT CUSTOMERS FOR UPDATE
        # ====================================================

        update_count = 0

        if existing_ids:

            update_count = max(
                1,
                int(len(existing_ids) * UPDATE_PERCENTAGE / 100),
            )

            update_ids = random.sample(
                existing_ids,
                min(
                    update_count,
                    len(existing_ids),
                ),
            )

        else:

            update_ids = []

        logger.info(
            "Customers selected for SCD2 updates: %d",
            len(update_ids),
        )

        # ====================================================
        # CURRENT BATCH
        # ====================================================

        batch_records = []

        # ====================================================
        # UPDATE EXISTING CUSTOMERS
        # ====================================================

        for customer_id in update_ids:

            versions = customers[customer_id]

            # -----------------------------------------------
            # Get current version
            # -----------------------------------------------

            current_version = next(
                version for version in versions if version["is_current"] is True
            )

            old_version_number = int(current_version["version"])

            new_version_number = old_version_number + 1

            now = datetime.now(timezone.utc)

            effective_start = now.strftime("%Y-%m-%d %H:%M:%S")

            effective_end = now.strftime("%Y-%m-%d %H:%M:%S")

            # -----------------------------------------------
            # KEEP OLD VERSION
            # -----------------------------------------------

            current_version["is_current"] = False

            current_version["effective_end_date"] = effective_end

            # -----------------------------------------------
            # GENERATE NEW VERSION
            # -----------------------------------------------

            new_customer = generate_customer(
                fake,
                int(customer_id),
            )

            new_version = create_customer_version(
                new_customer,
                new_version_number,
                effective_start,
                is_current=True,
                effective_end_date=None,
            )

            versions.append(new_version)

            # -----------------------------------------------
            # ADD ONLY NEW VERSION TO CURRENT BATCH
            # -----------------------------------------------

            batch_records.append(new_version.copy())

            logger.info(
                "SCD2 UPDATE: customer_id=%s " "version=%d -> version=%d",
                customer_id,
                old_version_number,
                new_version_number,
            )

        # ====================================================
        # GENERATE NEW CUSTOMERS
        # ====================================================

        new_customer_count = max(
            1,
            int(RECORD_COUNT * NEW_CUSTOMER_PERCENTAGE / 100),
        )

        logger.info(
            "Generating %d new customers",
            new_customer_count,
        )

        for _ in range(new_customer_count):

            customer_id = str(next_customer_id)

            new_customer = generate_customer(
                fake,
                int(customer_id),
            )

            new_version = create_customer_version(
                new_customer,
                version=1,
                effective_start_date=datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                is_current=True,
                effective_end_date=None,
            )

            customers[customer_id] = [new_version]

            batch_records.append(new_version.copy())

            next_customer_id += 1

            logger.info(
                "NEW CUSTOMER: customer_id=%s",
                customer_id,
            )

        # ====================================================
        # ADD UNCHANGED CUSTOMERS
        # ====================================================

        current_customer_versions = []

        for customer_id, versions in customers.items():

            current_version = next(
                version for version in versions if version["is_current"] is True
            )

            current_customer_versions.append(current_version)

        # ====================================================
        # MAKE SURE BATCH HAS RECORDS
        # ====================================================

        if not batch_records:

            logger.warning(
                "No updated or new customers generated. "
                "Selecting existing current customers."
            )

            batch_records = random.sample(
                current_customer_versions,
                min(
                    RECORD_COUNT,
                    len(current_customer_versions),
                ),
            )

        # ====================================================
        # LIMIT BATCH SIZE
        # ====================================================

        if len(batch_records) > RECORD_COUNT:

            batch_records = random.sample(
                batch_records,
                RECORD_COUNT,
            )

        logger.info(
            "Final CSV record count: %d",
            len(batch_records),
        )

        # ====================================================
        # SAVE STATE
        # ====================================================

        state = {
            "customers": customers,
            "next_customer_id": next_customer_id,
        }

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8",
        ) as state_file:

            json.dump(
                state,
                state_file,
                indent=2,
            )

        logger.info(
            "Customer state saved: %s",
            STATE_FILE,
        )

        # ====================================================
        # CREATE CSV
        # ====================================================

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        filename = f"customer_{timestamp}.csv"

        file_path = os.path.join(
            LOCAL_DATA_DIR,
            filename,
        )

        with open(
            file_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as csvfile:

            writer = csv.DictWriter(
                csvfile,
                fieldnames=FIELDNAMES,
            )

            writer.writeheader()

            writer.writerows(batch_records)

        logger.info(
            "CSV created: %s",
            file_path,
        )

        # ====================================================
        # BUILD S3 KEY
        # ====================================================

        if S3_PREFIX:

            s3_key = f"{S3_PREFIX.rstrip('/')}" f"/{filename}"

        else:

            s3_key = filename

        # ====================================================
        # UPLOAD TO S3
        # ====================================================

        logger.info(
            "Uploading file to s3://%s/%s",
            S3_BUCKET,
            s3_key,
        )

        s3 = boto3.client("s3")

        s3.upload_file(
            file_path,
            S3_BUCKET,
            s3_key,
        )

        logger.info("==================================================")

        logger.info("SUCCESS: S3 upload completed")

        logger.info(
            "s3://%s/%s",
            S3_BUCKET,
            s3_key,
        )

        logger.info(
            "SCD2 customers updated: %d",
            len(update_ids),
        )

        logger.info(
            "New customers: %d",
            new_customer_count,
        )

        logger.info("==================================================")

    except (
        ClientError,
        BotoCoreError,
    ) as error:

        logger.exception(
            "AWS/S3 ERROR: %s",
            error,
        )

        raise

    except Exception as error:

        logger.exception(
            "PIPELINE ERROR: %s",
            error,
        )

        raise

    finally:

        # ====================================================
        # CLEAN TEMPORARY CSV
        # ====================================================

        if file_path and os.path.exists(file_path):

            try:

                os.remove(file_path)

                logger.info(
                    "Temporary CSV removed: %s",
                    file_path,
                )

            except OSError as cleanup_error:

                logger.warning(
                    "Could not remove temporary file %s: %s",
                    file_path,
                    cleanup_error,
                )


# ============================================================
# AIRFLOW DAG
# ============================================================

default_args = {
    "owner": "Hamza Tufail",
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
}


with DAG(
    dag_id="customer_data_to_s3_assignment",
    description=("Generate SCD Type 2 synthetic " "customer data and upload to S3"),
    default_args=default_args,
    schedule=timedelta(minutes=1),
    start_date=datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    ),
    catchup=False,
    max_active_runs=1,
    tags=[
        "scd",
        "scd2",
        "snowflake",
        "s3",
        "faker",
    ],
) as dag:

    generate_and_upload = PythonOperator(
        task_id=("generate_and_upload_customers"),
        python_callable=(generate_and_upload_customers),
    )
