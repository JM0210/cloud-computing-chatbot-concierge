import boto3
import uuid
import json

lex_client = boto3.client('lexv2-runtime', region_name='us-east-1')

def lambda_handler(event, context):
    # 1. Parse Input
    try:
        if 'body' in event and isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event
        user_input = body.get('message')
    except Exception as e:
        user_input = None

    if not user_input:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Message missing'}) # Stringify this!
        }

    # 2. Call Lex
    try:
        response = lex_client.recognize_text(
            botId='RCXMTJ5CLQ',
            botAlias_id='TSTALIASID',
            localeId='en_US',
            sessionId="default-user",
            text=user_input
        )

        bot_messages = response.get('messages', [])
        final_text = bot_messages[0]['content'] if bot_messages else "No response"

        # 3. CONSTRUCT THE RESPONSE (The Fix)
        # The entire response is a dict, but the 'body' MUST be a string
        result_payload = {
            'botResponse': final_text,
            'intent': response['sessionState']['intent']['name']
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # Added for CORS if needed
            },
            'body': json.dumps(result_payload)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}) # Stringify this too!
        }