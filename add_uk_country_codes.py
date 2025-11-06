import logging
import requests
import json
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from icecream import ic


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""Script to add country codes to UK phone numbers in Halo user records. Numbers starting with '07' will be updated to '+44'."""

site_id = 496  # Replace with actual site ID

def retrieve_secrets():
    """Retrieve secrets from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name="us-west-1"
    )
    try:
        logger.info("Attempting to retrieve secrets from AWS Secrets Manager")
        get_secret_value_response_halo = client.get_secret_value(
            SecretId='halo_oauth_token'
        )
        secrets_halo = json.loads(get_secret_value_response_halo['SecretString'])
        logger.info("Successfully retrieved secrets")
        logger.debug(f"Access token: {secrets_halo['access_token']}")
        return secrets_halo['access_token']
    except BotoCoreError as e:
        logger.error(f"BotoCoreError retrieving secrets: {e}")
        raise Exception(f"Failed to retrieve secrets from AWS Secrets Manager: {str(e)}")
    except ClientError as e:
        logger.error(f"ClientError retrieving secrets: {e}")
        raise Exception(f"Failed to retrieve secrets from AWS Secrets Manager: {str(e)}")
    except KeyError as e:
        logger.error(f"KeyError: 'access_token' not found in secrets: {e}")
        raise Exception("Access token not found in secrets")
    
def get_users(site_id):
    token = retrieve_secrets()
    url = f"https://synergy.halopsa.com/api/Users"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    params = {
        "site_id": site_id,
        "count": 500
    }

    # Add debug logging for request details
    # logger.info(f"Making request to: {url}")
    # logger.info(f"With parameters: {params}")

    try:
        response = requests.get(url, headers=headers, params=params)
        # logger.info(f"Raw response: {response.text}")
        response.raise_for_status()
    

        if response.status_code == 200:
            raw_data = response.json()
            users = raw_data.get('users', [])
            site_name = users[0].get('site_name', 'Unknown Site') if users else 'Unknown Site'
            logger.info(f"Successfully received {len(users)} users from site: {site_name}")
            
            for user in users:
                user_name = user.get('name', 'Unknown User')
                phone_fields = {
                    'phonenumber': user.get('phonenumber', ''),
                    'mobilenumber': user.get('mobilenumber', ''),
                    'mobilenumber2': user.get('mobilenumber2', '')
                }
                
                # Log each user's phone numbers
                logger.info(f"User {user_name} phone numbers: {phone_fields}")

                updates = {}
                for field, number in phone_fields.items():
                    if number and number.startswith('07'):
                        updates[field] = '+44' + number[2:]
                        logger.info(f"Prepared update for {user_name}: {field} from {number} to {updates[field]}")
                
                if updates:
                    payload = [{
                        "id": user['id'],
                        **updates
                    }]
                    update_user_phone(user['id'], user_name, payload, headers)
                    logger.info(f"Updated {user_name} (ID: {user['id']}): {updates}")
            
            return users

        else:
            logger.error(f"Failed to get users: {response.status_code} - {response.text}")
            return response.status_code, response.text

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get users: {str(e)}")
        raise

def update_user_phone(user_id, user_name, payload, headers):
    """Update user's phone numbers in Halo."""
    url = f"https://synergy.halopsa.com/api/Users"
    
    try:
        logger.info(f"Updating phone numbers for {user_name}")
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload)
        logger.debug(f"Response Status: {response.status_code}")
        logger.debug(f"Response Body: {response.text}")
        
        response.raise_for_status()
        
        if response.status_code in [200, 201]:
            logger.info(f"Successfully updated phone numbers for {user_name} (ID: {user_id})")
        else:
            logger.error(f"Failed to update phone numbers for {user_name} (ID: {user_id}): {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating phone numbers for {user_name} (ID: {user_id}): {str(e)}")
        raise

if __name__ == "__main__":
    try:
        get_users(site_id)
    except Exception as e:
        logger.error(f"Script failed: {e}")