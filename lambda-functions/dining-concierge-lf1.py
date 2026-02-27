import json
import datetime
import boto3
# Configuration
ALLOWED_CITIES = ['new york']
ALLOWED_CUISINES = ['chinese', 'italian', 'japanese', 'mexican', 'indian', 'american']

def validate_booking(event, slots):
    user_id = event.get('sessionId')
    print(f"Validating booking for user {user_id}")

    # 1. Validate Location
    if slots.get('Location') and slots['Location'].get('value'):
        user_city = slots['Location']['value']['interpretedValue'].lower()
        if user_city not in ALLOWED_CITIES:
            return {
                'isValid': False,
                'violatedSlot': 'Location',
                'message': f"Sorry, we only have restaurants in {', '.join(ALLOWED_CITIES).title()}. "
            }

    # 2. Validate Cuisine 
    if slots.get('Cuisine') and slots['Cuisine'].get('value'):
        user_cuisine = slots['Cuisine']['value']['interpretedValue'].lower()
        if user_cuisine not in ALLOWED_CUISINES:
            return {
                'isValid': False,
                'violatedSlot': 'Cuisine',
                'message': f"I don't have recommendations for {user_cuisine} yet. How about {', '.join(ALLOWED_CUISINES)}?"
            }

    # 3. Validate Date
    if slots.get('Date') and slots['Date'].get('value'):
        booking_date_str = slots['Date']['value']['interpretedValue']
        try:
            booking_date = datetime.datetime.strptime(booking_date_str, '%Y-%m-%d').date()
            if booking_date < datetime.date.today():
                return {
                    'isValid': False,
                    'violatedSlot': 'Date',
                    'message': 'We cannot book for a past date. Please pick a future date.'
                }
        except ValueError:
            return {
                'isValid': False,
                'violatedSlot': 'Date',
                'message': 'That date format seems wrong. Could you provide it again?'
            }

    # # 4. Validate Time 
    # if slots.get('Time') and slots['Time'].get('value'):
    #     user_time = slots['Time']['value']['interpretedValue']
    #     if len(user_time) != 5: 
    #         return {
    #             'isValid': False,
    #             'violatedSlot': 'Time',
    #             'message': 'Could you please specify the time again? (e.g., 18:30)'
    #         }
    # 4. Validate Time 
    if slots.get('Time') and slots['Time'].get('value'):
        user_time = slots['Time']['value'].get('interpretedValue')

        if user_time is None:
            return {
                'isValid': False,
                'violatedSlot': 'Time',
                'message': 'Please use the 24-hour format (e.g., 18:30)'
            }
        
        if len(user_time) != 5: 
            return {
                'isValid': False,
                'violatedSlot': 'Time',
                'message': 'Please use the 24-hour format (e.g., 18:30).'
            }
    # 5. Validate Guest Count
    if slots.get('GuestCount') and slots['GuestCount'].get('value'):
        count_val = slots['GuestCount']['value']['interpretedValue']
        try:
            count = int(count_val)
            if count <= 0 or count > 10:
                return {
                    'isValid': False,
                    'violatedSlot': 'GuestCount',
                    'message': 'We can only accommodate 1 to 10 guests. How many people are in your party?'
                }
        except ValueError:
            return {
                'isValid': False,
                'violatedSlot': 'GuestCount',
                'message': 'Please provide the number of guests as a digit (e.g., 4).'
            }

    return {'isValid': True}

def lambda_handler(event, context):
    print("FULL EVENT FROM API GATEWAY:", json.dumps(event))
    intent_name = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent']['slots']
    source = event['invocationSource'] 
    
    # print log in CloudWatch from Lex 
    print(f"Received event from {source} for intent {intent_name}")
    
    if source == 'DialogCodeHook':
        validation_result = validate_booking(event, slots)
        
        if not validation_result['isValid']:
            return {
                "sessionState": {
                    "dialogAction": {
                        "slotToElicit": validation_result['violatedSlot'],
                        "type": "ElicitSlot"
                    },
                    "intent": {"name": intent_name, "slots": slots}
                },
                "messages": [{"contentType": "PlainText", "content": validation_result['message']}]
            }

        # return delegate to Lex
        return {
            "sessionState": {
                "dialogAction": {"type": "Delegate"},
                "intent": {"name": intent_name, "slots": slots}
            }
        }


    sqs = boto3.client('sqs')
    QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/898147176601/DiningRequestsQueue'

    if source == 'FulfillmentCodeHook':
        booking_data = {
            'Cuisine': slots['Cuisine']['value']['interpretedValue'],
            'Location': slots['Location']['value']['interpretedValue'],
            'Date': slots['Date']['value']['interpretedValue'],
            'Time': slots['Time']['value']['interpretedValue'],
            'GuestCount': slots['GuestCount']['value']['interpretedValue'],
            'Email': slots['Email']['value']['interpretedValue'] 
        }

        # 2. Push to SQS
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(booking_data)
        )

        return {
            "sessionState": {
                "dialogAction": {"type": "Close"},
                "intent": {"name": intent_name, "slots": slots, "state": "Fulfilled"}
            },
            "messages": [{"contentType": "PlainText", "content": "I've received your request. I'll search for the best options and email you shortly!"}]
        }