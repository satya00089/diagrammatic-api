"""Create the DynamoDB table used for product feedback."""

import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.config import get_settings


def main() -> None:
    settings = get_settings()
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    try:
        table = dynamodb.create_table(
            TableName=settings.dynamodb_feedback_table,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "createdAt", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-createdAt-index",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "createdAt", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        print(f"Created {settings.dynamodb_feedback_table}")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ResourceInUseException":
            print(f"{settings.dynamodb_feedback_table} already exists")
            return
        raise


if __name__ == "__main__":
    main()
