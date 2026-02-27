import boto3
import json
import time
from decimal import Decimal
from botocore.exceptions import ClientError

# --- CONFIGURATION ---
TABLE_NAME = "yelp-restaurants" # Must match assignment [cite: 68]
REGION = "us-east-1"
DATA_FILE = "restaurants_data.json"

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# Helper function to convert floats to Decimal (Required for DynamoDB)
def decimal_convert(obj):
    if isinstance(obj, list):
        return [decimal_convert(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_convert(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj

def setup_and_upload():
    # 1. CREATE TABLE (if it doesn't exist)
    try:
        print(f"Checking if table {TABLE_NAME} exists...")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            # Assignment Requirement: BusinessID as key 
            KeySchema=[{'AttributeName': 'BusinessID', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'BusinessID', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        print("Table creating... please wait.")
        table.meta.client.get_waiter('table_exists').wait(TableName=TABLE_NAME)
        print("Table created successfully!")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("Table already exists. Moving to next step.")
            table = dynamodb.Table(TABLE_NAME)
        else:
            raise

    # 2. LOAD AND UPLOAD DATA
    print(f"Loading data from {DATA_FILE}...")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        restaurants = json.load(f)

    print(f"Starting batch upload of {len(restaurants)} items...")
    
    # Use batch_writer for much faster performance 
    with table.batch_writer() as batch:
        for i, restaurant in enumerate(restaurants):
            # Convert any floats (like Rating or Coordinates) to Decimal
            clean_item = decimal_convert(restaurant)
            
            # Ensure insertedAtTimestamp is present 
            if 'insertedAtTimestamp' not in clean_item:
                clean_item['insertedAtTimestamp'] = str(time.time())
            
            batch.put_item(Item=clean_item)
            
            if (i + 1) % 100 == 0:
                print(f"Uploaded {i + 1} items...")

    print("--- SUCCESS: All data uploaded to DynamoDB ---")

if __name__ == "__main__":
    setup_and_upload()