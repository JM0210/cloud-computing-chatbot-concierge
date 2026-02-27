import json
import datetime

# Configuration
ALLOWED_CITIES = ['new york', 'chicago', 'washington dc', 'los angeles', 'miami', 'seattle']

def validate_booking(slots):
    # 1. Validate Location
    if slots.get('Location') and slots['Location'].get('value'):
        user_city = slots['Location']['value']['interpretedValue'].lower()
        if user_city not in ALLOWED_CITIES:
            return {
                'isValid': False,
                'violatedSlot': 'Location',
                'message': f"Sorry, we only have restaurants in {', '.join(ALLOWED_CITIES).title()}. Which one would you like?"
            }

    # 2. Validate Date
    if slots.get('Date') and slots['Date'].get('value'):
        booking_date_str = slots['Date']['value']['interpretedValue']
        booking_date = datetime.datetime.strptime(booking_date_str, '%Y-%m-%d').date()
        if booking_date < datetime.date.today():
            return {
                'isValid': False,
                'violatedSlot': 'Date',
                'message': 'We cannot book for a past date. Please pick a future date.'
            }

    # 3. Validate Guest Count
    if slots.get('GuestCount') and slots['GuestCount'].get('value'):
        count = int(slots['GuestCount']['value']['interpretedValue'])
        if count <= 0 or count > 10:
            return {
                'isValid': False,
                'violatedSlot': 'GuestCount',
                'message': 'We can only accommodate 1 to 10 guests. How many people are in your party?'
            }

    return {'isValid': True}

def lambda_handler(event, context):
    intent_name = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent']['slots']
    source = event['invocationSource'] 
    
    if source == 'DialogCodeHook':
        validation_result = validate_booking(slots)
        
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

        return {
            "sessionState": {
                "dialogAction": {"type": "Delegate"},
                "intent": {"name": intent_name, "slots": slots}
            }
        }

    if source == 'FulfillmentCodeHook':
        return {
            "sessionState": {
                "dialogAction": {"type": "Close"},
                "intent": {"name": intent_name, "slots": slots, "state": "Fulfilled"}
            },
            "messages": [{"contentType": "PlainText", "content": "Your reservation is confirmed. See you soon!"}]
        }