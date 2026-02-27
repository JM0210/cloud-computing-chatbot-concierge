import boto3
import json
import random
import urllib3
import base64
from datetime import datetime

REGION = 'us-east-1'
OS_HOST = 'search-restaurant-domain-l3mm4srslyxrindmlnp2ggr4gy.aos.us-east-1.on.aws'
INDEX = 'restaurant_list'
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/898147176601/DiningRequestsQueue'
DYNAMO_TABLE_DATA = 'yelp-restaurants'
SENDER_EMAIL = 'Jamiemai0210@gmail.com'
OS_USERNAME = 'jm11065'
OS_PASSWORD = '****!'

def lambda_handler(event, context):
    sqs = boto3.client('sqs')
    
    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20, 
        AttributeNames=['All']
    )
    
    if 'Messages' not in response or not response['Messages']:
        return {"statusCode": 200, "body": "No messages found"}
    
    message = response['Messages'][0]
    
    try:
        body = json.loads(message['Body'])
        
        cuisine = body.get('Cuisine', 'Japanese')
        email = body.get('Email')
        count = body.get('GuestCount', '2')
        date = body.get('Date', 'today')
        time = body.get('Time', '7 pm')
        
        if not email:
            return

        business_ids = get_ids_from_opensearch(cuisine)
        
        if business_ids:
            restaurants = get_details_from_dynamo(business_ids)
            if restaurants:
                send_email(email, cuisine, count, date, time, restaurants)
            
        receipt_handle = message['ReceiptHandle']
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)

    except Exception as e:
        print(f"Error: {str(e)}")
        
    return {"statusCode": 200, "body": "Process completed"}

def get_ids_from_opensearch(cuisine):
    auth_str = f"{OS_USERNAME}:{OS_PASSWORD}"
    encoded_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
    
    clean_host = OS_HOST.replace('https://', '').replace('http://', '')
    url = f"https://{clean_host}/{INDEX}/_search"
    
    query = {
        "size": 15,
        "query": {
            "match": {
                "Cuisine": cuisine.lower() 
            }
        }
    }
    
    http = urllib3.PoolManager()
    encoded_data = json.dumps(query).encode('utf-8')
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {encoded_auth}'
        }
        r = http.request('POST', url, body=encoded_data, headers=headers)
        if r.status != 200:
            return []

        res_json = json.loads(r.data.decode('utf-8'))
        hits = res_json.get('hits', {}).get('hits', [])
        
        all_ids = [h.get('_source', {}).get('BusinessID') for h in hits if h.get('_source', {}).get('BusinessID')]
        return random.sample(all_ids, min(len(all_ids), 3))
        
    except Exception:
        return []

def get_details_from_dynamo(ids):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(DYNAMO_TABLE_DATA)
    results = []
    
    for bid in ids:
        try:
            response = table.get_item(Key={'BusinessID': bid})
            item = response.get('Item')
            if item:
                results.append(item)
        except Exception:
            continue
    return results

def send_email(to_email, cuisine, count, date, time, restaurants):
    ses = boto3.client('ses', region_name=REGION)
    
    recommendations = ""
    for i, r in enumerate(restaurants, 1):
        name = r.get('Name', 'Unknown Restaurant')
        address = r.get('Address', 'No address provided')
        recommendations += f"{i}. {name}, located at {address}\n"
    
    body_text = (
        f"Hello! Here are my {cuisine} restaurant suggestions for {count} people, "
        f"for {date} at {time}:\n\n"
        f"{recommendations}\n"
        f"Enjoy your meal!"
    )

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {'Data': 'Your Restaurant Recommendations'},
            'Body': {'Text': {'Data': body_text}}
        }
    )
